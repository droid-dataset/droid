# Policy hosting commands

The bench eval script (`scripts/evaluation/evaluate_bench.py`) is a websocket **client only** — it does not load policies itself. You need a separately-running [openpi](./submodules/openpi/) policy server, which the eval script connects to via `--remote-host` / `--remote-port` (default `0.0.0.0:8000`).

The server can run on the same machine as the eval script (loopback `0.0.0.0`) or on a different GPU box reachable over the network. Inference needs a ~4090-class GPU.

## One-time openpi setup

openpi is vendored under `submodules/openpi/`. The condensed install (excerpted from the [openpi README](./submodules/openpi/README.md)):

```bash
cd submodules/openpi

# Install (GIT_LFS_SKIP_SMUDGE=1 is required to pull LeRobot as a dep)
GIT_LFS_SKIP_SMUDGE=1 uv sync
GIT_LFS_SKIP_SMUDGE=1 uv pip install -e .
```

> Tested only on Ubuntu 22.04 per the upstream README.

Checkpoints are downloaded on demand from `s3://openpi-assets` and cached under `~/.cache/openpi`. Override with `OPENPI_DATA_HOME=/path/to/cache`.

---

## Policy Hosting Commands

### MolmoAct2-DROID

The Docker path in [`docker/molmoact2/`](./docker/molmoact2/) serves MolmoAct2-DROID through the OpenPI websocket protocol expected by `scripts/evaluation/evaluate_bench.py`.

```bash
docker build -t molmoact2-droid:latest -f docker/molmoact2/Dockerfile .
docker run --rm --gpus all --ipc=host --shm-size=8g -p 8000:8000 -v $HOME/.cache/huggingface:/root/.cache/huggingface molmoact2-droid:latest
```

Use `--remote-host <policy-server-host> --remote-port 8000` from the eval client.

---

```bash
# Pi0.5 DROID Jointpos
XLA_PYTHON_CLIENT_MEM_FRACTION=0.95 uv run scripts/serve_policy.py policy:checkpoint --policy.config pi05_droid_jointpos_polaris --policy.dir gs://openpi-assets/checkpoints/pi05_droid_jointpos

# Pi0-FAST DROID Jointpos
XLA_PYTHON_CLIENT_MEM_FRACTION=0.95 uv run scripts/serve_policy.py policy:checkpoint --policy.config pi0_fast_droid_jointpos_polaris --policy.dir gs://openpi-assets/checkpoints/pi0_fast_droid_jointpos

# Pi0 DROID Jointpos
XLA_PYTHON_CLIENT_MEM_FRACTION=0.95 uv run scripts/serve_policy.py policy:checkpoint --policy.config pi0_droid_jointpos_polaris --policy.dir gs://openpi-assets/checkpoints/pi0_droid_jointpos

# Paligemma Binning DROID Jointpos
XLA_PYTHON_CLIENT_MEM_FRACTION=0.95 uv run scripts/serve_policy.py policy:checkpoint --policy.config paligemma_binning_droid_jointpos --policy.dir gs://openpi-assets/checkpoints/paligemma_binning_droid_jointpos

# Others policies - MolmoAct2? Pi07?
```
