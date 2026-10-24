#!/bin/bash
set -euo pipefail

MODEL_DIR=${MODEL_DIR:-/models/Ming-3.0-tts-tiny}
SERVED_NAME=${SERVED_NAME:-ming3}

if [ ! -f "$MODEL_DIR/config.json" ]; then
  echo "weights missing at $MODEL_DIR; run ./deploy.sh or mount a checkpoint" >&2
  exit 1
fi

# Streaming proxy on :8101 in front of the engine on :8094.
/usr/sbin/nginx -c /opt/ming/nginx.conf

# Absorb cold graph capture before real traffic arrives.
MING_MODEL="$SERVED_NAME" python3 /opt/ming/warm_ming.py &

exec vllm serve "$MODEL_DIR" \
  --served-model-name "$SERVED_NAME" \
  --host 0.0.0.0 --port 8094 \
  --omni --stage-init-timeout 1800 --init-timeout 2400 --deploy-config /opt/ming/deploy.yaml
