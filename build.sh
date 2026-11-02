#!/bin/bash
# Build the engine image only (dgx-spark-ming-tts:0.1): no weights, no
# container start. All arguments are forwarded to `docker compose build`
# (e.g. --no-cache, --pull).
# Mirror: PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple ./build.sh
# Base image: BASE_IMAGE=<ref> ./build.sh (default nvidia/cuda:13.0.3-devel-ubuntu24.04)
# GitHub proxy: GH_PROXY=https://gh-proxy.com/ ./build.sh (for the vLLM-Omni tarball)
set -euo pipefail
cd "$(dirname "$0")"
BASE_IMAGE=${BASE_IMAGE:-nvidia/cuda:13.0.3-devel-ubuntu24.04}


echo "building image (vLLM 0.32.0 + pinned vLLM-Omni overlay)"
docker compose build "$@"
echo "built: dgx-spark-ming-tts:0.1"
