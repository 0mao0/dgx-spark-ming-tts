#!/bin/bash
# One-command deployment: weights -> image -> container -> readiness check.
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p models
MODEL_REVISION=${MODEL_REVISION:-8cf79a893e4c244e7acdc2699271dd84fe04d45f}
if [ ! -f models/Ming-3.0-tts-tiny/config.json ]; then
  echo "[1/3] downloading weights (~17 GiB, revision ${MODEL_REVISION:0:8})"
  docker run --rm -e MODEL_REVISION="$MODEL_REVISION" -v "$PWD/models:/models" python:3.12-slim bash -lc '
    pip install -q modelscope &&
    modelscope download --model inclusionAI/Ming-3.0-tts-tiny \
      --revision "$MODEL_REVISION" \
      --local_dir /models/Ming-3.0-tts-tiny'
else
  echo "[1/3] weights present (pinned; delete models/Ming-3.0-tts-tiny to change revision)"
fi

echo "[2/3] building and starting"
docker compose up -d --build

echo "[3/3] waiting for readiness (cold start ~190 s)"
ready=0
for _ in $(seq 1 180); do
  if curl -sf http://127.0.0.1:8094/v1/models >/dev/null; then ready=1; break; fi
  sleep 5
done
if [ "$ready" != 1 ]; then
  echo "service did not become ready in 15 minutes; last logs:" >&2
  docker compose logs --tail=80 >&2 || true
  exit 1
fi

curl -s http://127.0.0.1:8094/v1/models; echo
curl -s http://127.0.0.1:8094/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"model":"ming3","input":"部署完成，这是一段测试音频。","response_format":"wav"}' \
  -o demo.wav
python3 - <<'PY' 2>/dev/null || true
import wave
w = wave.open("demo.wav")
print(f"demo.wav: {w.getframerate()} Hz, {w.getnchannels()} ch, {w.getnframes()/w.getframerate():.2f} s")
PY

echo "ready: http://<this-host>:8094/v1  (proxy :8101)"
