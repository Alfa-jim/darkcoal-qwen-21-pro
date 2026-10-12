FROM nvidia/cuda:13.0.2-runtime-ubuntu24.04@sha256:6a0e31b59e70890446f2c17356d6efc0d54260090a8c63d6ca7c2ad049db95d2
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PATH=/opt/venv/bin:$PATH \
    MODEL_VOLUME_ROOT=/runpod-volume COMFYUI_ROOT=/opt/ComfyUI \
    WORK_ROOT=/tmp/qwen-pro ENGINE_PORT=8188 ENGINE_START_TIMEOUT=300 JOB_TIMEOUT_SECONDS=1800 \
    HF_HOME=/runpod-volume/models/qwen-21-pro/.cache/huggingface \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3.12 python3.12-venv ca-certificates git tini libgomp1 libgl1 \
    && rm -rf /var/lib/apt/lists/* && python3.12 -m venv /opt/venv
ARG COMFY_COMMIT=e8665ca8e4089ab917567cdb491308e1397663d4
ARG GGUF_COMMIT=373048b8403a7820620065210a691263d4da0a61
RUN git init /opt/ComfyUI && cd /opt/ComfyUI \
    && git remote add origin https://github.com/Comfy-Org/ComfyUI.git \
    && git fetch --depth 1 origin ${COMFY_COMMIT} && git checkout --detach FETCH_HEAD \
    && git init custom_nodes/ComfyUI-GGUF && cd custom_nodes/ComfyUI-GGUF \
    && git remote add origin https://github.com/leejet/ComfyUI-GGUF.git \
    && git fetch --depth 1 origin ${GGUF_COMMIT} && git checkout --detach FETCH_HEAD
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir torch==2.10.0 torchvision==0.25.0 --index-url https://download.pytorch.org/whl/cu130 \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip check && python -m pip freeze > /app/installed-requirements.txt
COPY custom_nodes/pro_nodes /opt/ComfyUI/custom_nodes/pro_nodes
COPY handler.py model-lock.json ./
COPY worker ./worker
COPY scripts/smoke.py ./scripts/smoke.py
RUN python scripts/smoke.py
LABEL org.opencontainers.image.source="https://github.com/Alfa-jim/darkcoal-qwen-21-pro" \
      org.opencontainers.image.description="Qwen Image 2.1 Pro Q4_K_M RunPod worker with configurable ComfyUI sampling"
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-u", "handler.py"]
