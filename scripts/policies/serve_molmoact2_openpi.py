"""OpenPI-compatible websocket server for MolmoAct2-DROID.

This is intentionally narrow: it serves the MolmoAct2 DROID/Franka policy to
the PolaRiS/DROID eval client without pulling in the full OpenPI server stack.
The websocket wire protocol matches OpenPI's WebsocketClientPolicy.
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import http
import inspect
import logging
import os
from pathlib import Path
import sys
import time
import traceback
from typing import Any

import msgpack
import numpy as np
import websockets
import websockets.asyncio.server as ws_server
import websockets.frames

DEFAULT_REPO_ID = "allenai/MolmoAct2-DROID"
DEFAULT_NORM_TAG = "franka_droid"
DEFAULT_NUM_STEPS = 10

LOG = logging.getLogger("molmoact2_openpi")


def _pack_array(obj: Any) -> Any:
    if isinstance(obj, (np.ndarray, np.generic)) and obj.dtype.kind in ("V", "O", "c"):
        raise ValueError(f"Unsupported dtype: {obj.dtype}")

    if isinstance(obj, np.ndarray):
        return {
            b"__ndarray__": True,
            b"data": obj.tobytes(),
            b"dtype": obj.dtype.str,
            b"shape": obj.shape,
        }

    if isinstance(obj, np.generic):
        return {
            b"__npgeneric__": True,
            b"data": obj.item(),
            b"dtype": obj.dtype.str,
        }

    return obj


def _unpack_array(obj: dict) -> Any:
    if b"__ndarray__" in obj:
        return np.ndarray(buffer=obj[b"data"], dtype=np.dtype(obj[b"dtype"]), shape=obj[b"shape"])

    if b"__npgeneric__" in obj:
        return np.dtype(obj[b"dtype"]).type(obj[b"data"])

    return obj


Packer = functools.partial(msgpack.Packer, default=_pack_array)
packb = functools.partial(msgpack.packb, default=_pack_array)
unpackb = functools.partial(msgpack.unpackb, object_hook=_unpack_array)


class WebsocketPolicyServer:
    """Small OpenPI-compatible websocket policy server."""

    def __init__(self, policy: Any, host: str, port: int, metadata: dict[str, Any] | None = None) -> None:
        self._policy = policy
        self._host = host
        self._port = port
        self._metadata = metadata or {}
        logging.getLogger("websockets.server").setLevel(logging.INFO)

    def serve_forever(self) -> None:
        asyncio.run(self.run())

    async def run(self) -> None:
        async with ws_server.serve(
            self._handler,
            self._host,
            self._port,
            compression=None,
            max_size=None,
            process_request=_health_check,
        ) as server:
            LOG.info("OpenPI-compatible websocket server listening on %s:%d", self._host, self._port)
            await server.serve_forever()

    async def _handler(self, websocket: ws_server.ServerConnection) -> None:
        LOG.info("Connection from %s opened", websocket.remote_address)
        packer = Packer()
        await websocket.send(packer.pack(self._metadata))

        previous_total_time = None
        while True:
            try:
                start_time = time.monotonic()
                obs = unpackb(await websocket.recv())

                infer_start = time.monotonic()
                response = self._policy.infer(obs)
                infer_ms = (time.monotonic() - infer_start) * 1000.0

                response["server_timing"] = {"infer_ms": infer_ms}
                if previous_total_time is not None:
                    response["server_timing"]["prev_total_ms"] = previous_total_time * 1000.0

                await websocket.send(packer.pack(response))
                previous_total_time = time.monotonic() - start_time
            except websockets.ConnectionClosed:
                LOG.info("Connection from %s closed", websocket.remote_address)
                break
            except Exception:
                await websocket.send(traceback.format_exc())
                await websocket.close(
                    code=websockets.frames.CloseCode.INTERNAL_ERROR,
                    reason="Internal server error. Traceback included in previous frame.",
                )
                raise


def _health_check(connection: ws_server.ServerConnection, request: ws_server.Request) -> ws_server.Response | None:
    if request.path == "/healthz":
        return connection.respond(http.HTTPStatus.OK, "OK\n")
    return None


class MolmoAct2DroidOpenPIPolicy:
    """Adapts DROID eval observations to MolmoAct2's DROID Policy.predict API."""

    def __init__(
        self,
        *,
        repo_id: str,
        device: str,
        dtype: str,
        num_steps: int,
        enable_cuda_graph: bool,
        molmoact2_path: Path,
        no_warmup: bool,
    ) -> None:
        self.repo_id = repo_id
        self.device = device
        self.dtype = dtype
        self.num_steps = num_steps
        self.enable_cuda_graph = enable_cuda_graph

        molmoact2_path = molmoact2_path.resolve()
        if not (molmoact2_path / "examples" / "droid" / "host_server_droid.py").exists():
            raise FileNotFoundError(
                f"Could not find MolmoAct2 DROID server under {molmoact2_path}. "
                "Pass --molmoact2-path or set MOLMOACT2_PATH."
            )
        sys.path.insert(0, str(molmoact2_path))

        import torch
        from examples.droid.host_server_droid import Policy, warmup

        torch_dtype = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }[dtype]

        LOG.info("Loading MolmoAct2 policy repo_id=%s device=%s dtype=%s", repo_id, device, dtype)
        self._policy = Policy(
            repo_id=repo_id,
            device=device,
            dtype=torch_dtype,
            enable_cuda_graph=enable_cuda_graph,
        )
        self._patch_predict_action_kwargs()
        if not no_warmup:
            warmup(self._policy)

    def _patch_predict_action_kwargs(self) -> None:
        """Bridge MolmoAct2 API drift between action_mode and inference_action_mode."""
        original_predict_action = self._policy.model.predict_action
        parameters = inspect.signature(original_predict_action).parameters
        if "action_mode" in parameters or "inference_action_mode" not in parameters:
            return

        def compat_predict_action(*args: Any, **kwargs: Any) -> Any:
            if "action_mode" in kwargs and "inference_action_mode" not in kwargs:
                kwargs["inference_action_mode"] = kwargs.pop("action_mode")
            return original_predict_action(*args, **kwargs)

        self._policy.model.predict_action = compat_predict_action
        LOG.info("Patched MolmoAct2 predict_action kwarg: action_mode -> inference_action_mode")

    def infer(self, obs: dict[str, Any]) -> dict[str, Any]:
        external_cam = _unbatch_required(obs, "observation/exterior_image_1_left")
        wrist_cam = _unbatch_required(obs, "observation/wrist_image_left")
        joint = np.asarray(_unbatch_required(obs, "observation/joint_position"), dtype=np.float32).reshape(-1)
        gripper = np.asarray(_unbatch_required(obs, "observation/gripper_position"), dtype=np.float32).reshape(-1)
        instruction = _first_required(obs, "prompt")
        state = np.concatenate([joint, gripper], axis=-1).astype(np.float32, copy=False)

        if state.shape != (8,):
            raise ValueError(f"Expected 7 joint values plus 1 gripper value, got state shape {state.shape}")

        num_steps = int(_optional_scalar(obs, "num_steps", self.num_steps))
        enable_cuda_graph = bool(_optional_scalar(obs, "enable_cuda_graph", self.enable_cuda_graph))

        actions = self._policy.predict(
            external_cam=external_cam,
            wrist_cam=wrist_cam,
            instruction=str(instruction),
            state=state,
            num_steps=num_steps,
            enable_cuda_graph=enable_cuda_graph,
        )
        actions = np.asarray(actions, dtype=np.float32)
        if actions.ndim == 3 and actions.shape[0] == 1:
            actions = actions[0]
        if actions.ndim != 2 or actions.shape[-1] != 8:
            raise ValueError(f"MolmoAct2 returned actions with unexpected shape {actions.shape}; expected (N, 8)")
        return {"actions": actions[None]}


class MockDroidPolicy:
    """Protocol-only policy for port and websocket smoke tests without a GPU."""

    def __init__(self, num_steps: int) -> None:
        self.num_steps = num_steps

    def infer(self, obs: dict[str, Any]) -> dict[str, Any]:
        _unbatch_required(obs, "observation/exterior_image_1_left")
        _unbatch_required(obs, "observation/wrist_image_left")
        _unbatch_required(obs, "observation/joint_position")
        _unbatch_required(obs, "observation/gripper_position")
        _first_required(obs, "prompt")
        return {"actions": np.zeros((1, self.num_steps, 8), dtype=np.float32)}


def _unbatch_required(obs: dict[str, Any], key: str) -> Any:
    if key not in obs:
        raise KeyError(f"Missing required observation key: {key}")
    value = np.asarray(obs[key])
    if value.ndim == 0:
        raise ValueError(f"{key} must have a leading batch dimension")
    if value.shape[0] != 1:
        raise ValueError(f"{key} must use batch size 1, got shape {value.shape}")
    return value[0]


def _first_required(obs: dict[str, Any], key: str) -> Any:
    if key not in obs:
        raise KeyError(f"Missing required observation key: {key}")
    value = obs[key]
    if isinstance(value, np.ndarray):
        if value.shape[0] != 1:
            raise ValueError(f"{key} must use batch size 1, got shape {value.shape}")
        return value[0].item() if isinstance(value[0], np.generic) else value[0]
    if isinstance(value, (list, tuple)):
        if len(value) != 1:
            raise ValueError(f"{key} must contain exactly one item, got {len(value)}")
        return value[0]
    return value


def _optional_scalar(obs: dict[str, Any], key: str, default: Any) -> Any:
    if key not in obs:
        return default
    value = obs[key]
    if isinstance(value, np.ndarray):
        return value.reshape(-1)[0].item()
    if isinstance(value, (list, tuple)):
        return value[0]
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve MolmoAct2-DROID with the OpenPI websocket protocol")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address. Use 0.0.0.0 for Docker/network access.")
    parser.add_argument("--port", type=int, default=8000, help="Bind port.")
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID, help="Hugging Face repo id for MolmoAct2-DROID.")
    parser.add_argument("--device", default="cuda:0", help="Torch device for the MolmoAct2 model.")
    parser.add_argument("--dtype", choices=["bfloat16", "float16", "float32"], default="bfloat16")
    parser.add_argument("--num-steps", type=int, default=DEFAULT_NUM_STEPS, help="Actions per inference chunk.")
    parser.add_argument("--cuda-graph", action="store_true", help="Enable MolmoAct2 CUDA graph inference.")
    parser.add_argument("--no-warmup", action="store_true", help="Skip MolmoAct2 warmup inference.")
    parser.add_argument(
        "--molmoact2-path",
        type=Path,
        default=Path(os.environ.get("MOLMOACT2_PATH", "/opt/molmoact2")),
        help="Path to a MolmoAct2 checkout.",
    )
    parser.add_argument("--mock", action="store_true", help="Serve zero actions without loading MolmoAct2.")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")
    args = parse_args()

    if args.mock:
        LOG.warning("Starting mock policy. This tests the websocket protocol only; it does not run MolmoAct2.")
        policy = MockDroidPolicy(num_steps=args.num_steps)
    else:
        policy = MolmoAct2DroidOpenPIPolicy(
            repo_id=args.repo_id,
            device=args.device,
            dtype=args.dtype,
            num_steps=args.num_steps,
            enable_cuda_graph=args.cuda_graph,
            molmoact2_path=args.molmoact2_path,
            no_warmup=args.no_warmup,
        )

    metadata = {
        "policy_name": "molmoact2_droid",
        "repo_id": args.repo_id,
        "norm_tag": DEFAULT_NORM_TAG,
        "server": "molmoact2_openpi_websocket",
        "requested_num_steps": args.num_steps,
        "action_shape": [1, "N", 8],
        "min_action_steps": 8,
        "mock": args.mock,
    }
    WebsocketPolicyServer(policy=policy, host=args.host, port=args.port, metadata=metadata).serve_forever()


if __name__ == "__main__":
    main()
