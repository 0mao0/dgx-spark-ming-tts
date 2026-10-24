FROM lmsysorg/sglang:qwen38-27b

ARG PIP_INDEX_URL=https://pypi.org/simple

# The base image has no nginx; the streaming proxy needs it.
RUN apt-get update \
 && apt-get install -y --no-install-recommends nginx \
 && rm -rf /var/lib/apt/lists/*

# vLLM 0.32.0 is the tested runtime; --no-deps keeps the image's torch 2.13.
RUN pip install --no-cache-dir --no-deps --index-url "${PIP_INDEX_URL}" vllm==0.32.0

# vLLM-Omni overlay pinned to PR #9198 head (still a draft).
RUN mkdir -p /opt/pr9198 \
 && curl -fsSL https://codeload.github.com/vllm-project/vllm-omni/tar.gz/091f736324bd347d19282840d0d1298180f3ae6b \
    | tar -xz -C /opt/pr9198 --strip-components=1

# The overlay validates per-request max_new_tokens against a hard-coded
# MAX_DECODE_STEPS=800 (~64 s of audio). Raise it to 2400 so callers can ask
# for longer generations; the default still comes from the model config,
# which deploy.sh patches.
RUN sed -i 's/^MAX_DECODE_STEPS = 800$/MAX_DECODE_STEPS = 2400/' \
    /opt/pr9198/vllm_omni/model_executor/models/ming3_tts/constants.py

# vllm is installed --no-deps to keep the base image's torch 2.13, so its own
# dependencies and the overlay's imports have to be installed explicitly.
# Without this the container dies at import time (aenum, cbor2, httpx2, ...).
COPY deploy/tested-pip-freeze.txt /opt/ming/tested-pip-freeze.txt
# --ignore-installed: the base image ships packages without RECORD files
# (e.g. PyJWT 2.7.0), so pip cannot uninstall them before installing the pins.
RUN pip install --no-cache-dir --no-deps --ignore-installed \
      --index-url "${PIP_INDEX_URL}" -r /opt/ming/tested-pip-freeze.txt

# Engine startup needs vLLM-Omni's installed dist-info and plugin registration;
# the source overlay on PYTHONPATH only shadows the modules. Without this the
# stage engine cores die during initialization with a silent
# "Engine core initialization failed".
RUN pip install --no-cache-dir --no-deps --ignore-installed \
      --index-url "${PIP_INDEX_URL}" vllm-omni==0.30.0

COPY deploy/ming3_9198_gb10.yaml /opt/ming/deploy.yaml
COPY deploy/nginx_ming_proxy.conf /opt/ming/nginx.conf
COPY deploy/warm_ming.py /opt/ming/warm_ming.py
COPY entrypoint.sh /opt/ming/entrypoint.sh
RUN chmod +x /opt/ming/entrypoint.sh

ENV PYTHONPATH=/opt/pr9198 \
    VLLM_USE_V1=1

EXPOSE 8094 8101
ENTRYPOINT ["/opt/ming/entrypoint.sh"]
