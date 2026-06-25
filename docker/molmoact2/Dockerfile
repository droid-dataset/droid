FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    HF_HUB_ENABLE_HF_TRANSFER=1 \
    HF_HOME=/root/.cache/huggingface \
    MOLMOACT2_PATH=/opt/molmoact2 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir --upgrade pip uv

RUN GIT_LFS_SKIP_SMUDGE=1 git clone --depth=1 https://github.com/allenai/molmoact2.git /opt/molmoact2

WORKDIR /opt/molmoact2
RUN uv pip install --system --no-cache \
    --extra-index-url https://download.pytorch.org/whl/cu121 \
    "torch==2.5.1" \
    "torchvision==0.20.1" \
    "transformers>=4.57,<4.58" \
    "accelerate>=1.0" \
    "safetensors>=0.4" \
    "huggingface-hub[cli]>=0.36" \
    "hf-transfer>=0.1.8" \
    "pillow>=10" \
    "numpy>=1.26,<3" \
    "einops>=0.7" \
    "sentencepiece>=0.2" \
    "protobuf>=4.25" \
    "fastapi>=0.116" \
    "uvicorn[standard]>=0.35" \
    "json-numpy>=2.1.0" \
    "websockets>=15.0.1" \
    "msgpack>=1.1.0"

WORKDIR /opt/droid
COPY scripts/policies/serve_molmoact2_openpi.py /opt/droid/scripts/policies/serve_molmoact2_openpi.py
COPY scripts/policies/test_molmoact2_openpi_client.py /opt/droid/scripts/policies/test_molmoact2_openpi_client.py

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

CMD ["python", "/opt/droid/scripts/policies/serve_molmoact2_openpi.py", "--host", "0.0.0.0", "--port", "8000", "--dtype", "bfloat16", "--device", "cuda:0"]
