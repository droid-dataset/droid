"""Smoke-test client for the MolmoAct2 OpenPI-compatible websocket server."""

from __future__ import annotations

import argparse
import functools

import msgpack
import numpy as np


def _pack_array(obj):
    if isinstance(obj, np.ndarray):
        return {
            b"__ndarray__": True,
            b"data": obj.tobytes(),
            b"dtype": obj.dtype.str,
            b"shape": obj.shape,
        }
    if isinstance(obj, np.generic):
        return {b"__npgeneric__": True, b"data": obj.item(), b"dtype": obj.dtype.str}
    return obj


def _unpack_array(obj):
    if b"__ndarray__" in obj:
        return np.ndarray(buffer=obj[b"data"], dtype=np.dtype(obj[b"dtype"]), shape=obj[b"shape"])
    if b"__npgeneric__" in obj:
        return np.dtype(obj[b"dtype"]).type(obj[b"data"])
    return obj


Packer = functools.partial(msgpack.Packer, default=_pack_array)
unpackb = functools.partial(msgpack.unpackb, object_hook=_unpack_array)


def _dummy_obs() -> dict:
    return {
        "observation/exterior_image_1_left": np.zeros((1, 224, 224, 3), dtype=np.uint8),
        "observation/wrist_image_left": np.zeros((1, 224, 224, 3), dtype=np.uint8),
        "observation/joint_position": np.zeros((1, 7), dtype=np.float32),
        "observation/gripper_position": np.zeros((1, 1), dtype=np.float32),
        "prompt": ["pick up the red block"],
    }


def _infer_with_openpi_client(host: str, port: int) -> dict:
    from openpi_client.websocket_client_policy import WebsocketClientPolicy

    client = WebsocketClientPolicy(host=host, port=port)
    print(f"server metadata: {client.get_server_metadata()}")
    return client.infer(_dummy_obs())


def _infer_with_direct_websocket(host: str, port: int) -> dict:
    import websockets.sync.client

    uri = f"ws://{host}:{port}"
    packer = Packer()
    with websockets.sync.client.connect(uri, compression=None, max_size=None) as websocket:
        metadata = unpackb(websocket.recv())
        print(f"server metadata: {metadata}")
        websocket.send(packer.pack(_dummy_obs()))
        response = websocket.recv()
    if isinstance(response, str):
        raise RuntimeError(response)
    return unpackb(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Use a direct websocket client instead of openpi_client.WebsocketClientPolicy.",
    )
    args = parser.parse_args()

    if args.direct:
        result = _infer_with_direct_websocket(args.host, args.port)
    else:
        try:
            result = _infer_with_openpi_client(args.host, args.port)
        except ImportError:
            print("openpi_client is not installed; falling back to direct websocket protocol client.")
            result = _infer_with_direct_websocket(args.host, args.port)

    actions = np.asarray(result["actions"])
    print(f"actions shape: {actions.shape}")
    if actions.ndim != 3 or actions.shape[0] != 1 or actions.shape[-1] != 8:
        raise SystemExit(f"unexpected actions shape: {actions.shape}")
    if actions.shape[1] < 8:
        raise SystemExit(f"expected at least 8 action steps, got {actions.shape[1]}")
    print("OK")


if __name__ == "__main__":
    main()
