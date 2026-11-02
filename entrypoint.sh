#!/bin/bash
set -euo pipefail

MODEL_DIR=${MODEL_DIR:-/models/Ming-3.0-tts-tiny}
SERVED_NAME=${SERVED_NAME:-ming3}
PORT=${PORT:-8094}
# Default to no Swagger/ReDoc/OpenAPI endpoints; set DISABLE_DOCS=0 to expose them.
DISABLE_DOCS=${DISABLE_DOCS:-1}

if [ ! -f "$MODEL_DIR/config.json" ]; then
  echo "weights missing at $MODEL_DIR; run ./deploy.sh or mount a checkpoint" >&2
  exit 1
fi

# Absorb cold graph capture before real traffic arrives.
MING_MODEL="$SERVED_NAME" MING_BASE="http://127.0.0.1:$PORT" python3 /opt/ming/warm_ming.py &

EXTRA_ARGS=()
if [ "$DISABLE_DOCS" = "1" ]; then
  EXTRA_ARGS+=(--disable-fastapi-docs)
fi

exec vllm serve "$MODEL_DIR" \
  --served-model-name "$SERVED_NAME" \
  --host 0.0.0.0 --port "$PORT" \
  --omni --stage-init-timeout 1800 --init-timeout 2400 --deploy-config /opt/ming/deploy.yaml \
  "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"
