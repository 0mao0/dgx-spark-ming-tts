#!/bin/bash
# Serve Ming-3.0-TTS tiny through vLLM-Omni.
# Requires the PR #9198 overlay at /out/pr9198 and vllm 0.32.0 in the image.
export PYTHONPATH=/out/pr9198
export VLLM_USE_V1=1
exec vllm serve /models/Ming-3.0-tts-tiny \
  --served-model-name ming3 \
  --host 0.0.0.0 --port 8094 \
  --omni --deploy-config /out/ming3_9198_gb10.yaml
