# MolmoAct2-DROID Policy Server

This image serves `allenai/MolmoAct2-DROID` through an OpenPI-compatible websocket server on port `8000`. That is the default path for `scripts/evaluation/evaluate_bench.py` via `--remote-host` and `--remote-port`.

The first real run downloads the MolmoAct2-DROID checkpoint from Hugging Face, which is large. Use a persistent Hugging Face cache mount so later runs reuse it. No robot hardware is required to start the policy server or run the dummy websocket smoke test; full eval still requires a DROID robot setup.

## Build

```bash
docker build -t molmoact2-droid:latest -f docker/molmoact2/Dockerfile .
```

## Run With GPU

```bash
docker run --rm --gpus all \
  --ipc=host \
  --shm-size=8g \
  -p 8000:8000 \
  -e HF_HUB_ENABLE_HF_TRANSFER=1 \
  -e HF_HOME=/root/.cache/huggingface \
  -v $HOME/.cache/huggingface:/root/.cache/huggingface \
  molmoact2-droid:latest
```

Health check:

```bash
curl http://localhost:8000/healthz
```

Dummy websocket client check from another shell:

```bash
docker exec -it <container-id> python /opt/droid/scripts/policies/test_molmoact2_openpi_client.py --host 127.0.0.1 --port 8000 --direct
```

Expected output includes `actions shape: (1, N, 8)` with `N >= 8` and `OK`.

## DROID Eval Client

Run the eval client against the policy host and port:

```bash
python scripts/evaluation/evaluate_bench.py \
  --task-config tasks/example_institution/pick_red_block.yaml \
  --policy-name molmoact2_droid \
  --operator <name> \
  --n-episodes 5 \
  --external-camera left \
  --remote-host <policy-server-host> \
  --remote-port 8000
```

Only these connection args matter for the server:

```bash
--remote-host <policy-server-host> --remote-port 8000
```

## DockerHub Template

```bash
docker tag molmoact2-droid:latest <dockerhub-user>/molmoact2-droid:latest
docker push <dockerhub-user>/molmoact2-droid:latest
docker pull <dockerhub-user>/molmoact2-droid:latest
```

Then run:

```bash
docker run --rm --gpus all \
  --ipc=host \
  --shm-size=8g \
  -p 8000:8000 \
  -v $HOME/.cache/huggingface:/root/.cache/huggingface \
  <dockerhub-user>/molmoact2-droid:latest
```

## Optional FastAPI Mode

The default server is the OpenPI-compatible websocket server. For MolmoAct2's original FastAPI `/act` server, override the container command:

```bash
docker run --rm --gpus all \
  --ipc=host \
  --shm-size=8g \
  -p 8000:8000 \
  -v $HOME/.cache/huggingface:/root/.cache/huggingface \
  molmoact2-droid:latest \
  python /opt/molmoact2/examples/droid/host_server_droid.py --host 0.0.0.0 --port 8000 --dtype bfloat16
```

FastAPI health checks:

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/act
```

FastAPI `/act` is useful for direct MolmoAct2 HTTP clients, but it is not what `evaluate_bench.py` uses.

## Mock Protocol Smoke Test

To test the websocket path without GPU or checkpoint download:

```bash
docker run --rm \
  -p 8000:8000 \
  molmoact2-droid:latest \
  python /opt/droid/scripts/policies/serve_molmoact2_openpi.py --host 0.0.0.0 --port 8000 --mock
```

Then run:

```bash
curl http://localhost:8000/healthz
docker exec -it <container-id> python /opt/droid/scripts/policies/test_molmoact2_openpi_client.py --host 127.0.0.1 --port 8000 --direct
```
