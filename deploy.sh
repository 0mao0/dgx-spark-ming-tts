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

# The checkpoint ships tts_config.maximum_decode_steps=250, i.e. every request
# is cut at exactly 20.00 s (250 decode steps x 12.5 steps/s) no matter how long
# the text is. Raise it to 1000 (80 s). The YAML "max_tokens: 801" does NOT
# bound speech length: the adapter overwrites it per request.
echo "[2/4] patching generation-length cap (250 -> 1000 steps / 80 s)"
docker run --rm -v "$PWD/models:/models" python:3.12-slim python - <<'PY'
import json
p = "/models/Ming-3.0-tts-tiny/config.json"
c = json.load(open(p))
t = c.setdefault("tts_config", {})
if int(t.get("maximum_decode_steps", 0)) < 1000:
    t["maximum_decode_steps"] = 1000
    json.dump(c, open(p, "w"), indent=4, ensure_ascii=False)
    print("[patch] maximum_decode_steps -> 1000")
else:
    print("[patch] maximum_decode_steps already >= 1000")
PY

echo "[3/4] building and starting"
docker compose up -d --build

echo "[4/4] waiting for readiness (cold start ~190 s)"
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
