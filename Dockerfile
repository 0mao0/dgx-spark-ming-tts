# Pure vLLM stack for Ming-3.0-TTS on DGX Spark (GB10, aarch64, CUDA 13).
# Base: NVIDIA's own CUDA image (public, multi-arch). Nothing here comes from
# another inference framework — vLLM 0.32 + the vLLM-Omni overlay only.
FROM nvidia/cuda:13.0.3-devel-ubuntu24.04

ARG PIP_INDEX_URL=https://pypi.org/simple
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cu130

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    PYTHONUNBUFFERED=1

# Python 3.12 (Ubuntu 24.04 default), nginx for the streaming proxy, and the
# shared libraries the serving path loads: ffmpeg for torchcodec, libsndfile
# for soundfile, libgl/libglib for opencv.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3.12 python3-pip python3-dev ninja-build cmake build-essential \
      nginx curl ca-certificates git \
      libgl1 libglib2.0-0 libsndfile1 ffmpeg libgomp1 \
 && rm -rf /var/lib/apt/lists/*

# Torch stack from the CUDA 13 index (aarch64 wheels exist for cp312).
RUN pip install --no-cache-dir --index-url "${TORCH_INDEX_URL}" \
      torch==2.13.0 torchvision==0.28.0 torchaudio==2.11.0

# vLLM 0.32 with its declared dependencies, torch pinned so the resolver never
# replaces the CUDA 13 build installed above.
RUN pip install --no-cache-dir \
      --extra-index-url "${TORCH_INDEX_URL}" --index-url "${PIP_INDEX_URL}" \
      vllm==0.32.0 "torch==2.13.0" "torchvision==0.28.0" "torchaudio==2.11.0"

# vLLM-Omni source overlay pinned to PR #9198 head (open review, not merged).
# The retries matter: codeload drops connections often enough to fail builds.
RUN mkdir -p /opt/pr9198 \
 && curl -fsSL --retry 10 --retry-all-errors --retry-delay 4 --retry-max-time 900 -m 1200 \
      https://codeload.github.com/vllm-project/vllm-omni/tar.gz/c0b1351ef54d85a2a860f7bdf75c4dbcfa08c472 \
    | tar -xz -C /opt/pr9198 --strip-components=1

# The overlay validates per-request max_new_tokens against a hard-coded
# MAX_DECODE_STEPS=800 (~64 s of audio). Raise it to 2400 so callers can ask
# for longer generations; the default still comes from the model config,
# which deploy.sh patches.
RUN sed -i 's/^MAX_DECODE_STEPS = 800$/MAX_DECODE_STEPS = 2400/' \
    /opt/pr9198/vllm_omni/model_executor/models/ming3_tts/constants.py

# Three extras the bare CUDA base lacks but the overlay/serving path imports:
# omegaconf (yaml configs), soundfile + av (audio IO). Everything else arrives
# with vLLM's own dependency graph above.
RUN pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" omegaconf soundfile av aenum prettytable janus einx s3tokenizer sse-starlette diffusers==0.40.0 x_transformers==2.31.8

# Engine startup needs vLLM-Omni's installed dist-info and plugin registration;
# the source overlay on PYTHONPATH only shadows the modules.
RUN pip install --no-cache-dir --no-deps --ignore-installed \
      --index-url "${PIP_INDEX_URL}" vllm-omni==0.30.0

# Pin the exact transformers/tokenizers pair from the tested deployment:
# vLLM's dependency graph resolves transformers 5.19 (whose tokenizers floor
# is higher), but the overlay's compat shims and the reference deployment run
# 5.14.1 + tokenizers 0.22.2.
RUN pip install --no-cache-dir --no-deps --ignore-installed \
      --index-url "${PIP_INDEX_URL}" transformers==5.14.1 tokenizers==0.22.2 huggingface_hub==1.33.0

COPY deploy/ming3_9198_gb10.yaml /opt/ming/deploy.yaml
COPY deploy/nginx_ming_proxy.conf /opt/ming/nginx.conf
COPY deploy/warm_ming.py /opt/ming/warm_ming.py
COPY entrypoint.sh /opt/ming/entrypoint.sh
RUN chmod +x /opt/ming/entrypoint.sh

ENV PYTHONPATH=/opt/pr9198 \
    VLLM_USE_V1=1

EXPOSE 8094 8101
ENTRYPOINT ["/opt/ming/entrypoint.sh"]
