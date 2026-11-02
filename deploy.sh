#!/bin/bash
# One-command deployment: weights -> image -> container -> readiness check.
# --no-start: prepare weights only (steps 1-2), skip build/start/readiness.
set -euo pipefail
cd "$(dirname "$0")"

START=1
PORT=${PORT:-8094}
for arg in "$@"; do
  case "$arg" in
    --no-start) START=0 ;;
    -h|--help)
      echo "usage: ./deploy.sh [--no-start]"
      echo "  --no-start   download + patch weights only; skip build, start, readiness check"
      exit 0 ;;
    *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

mkdir -p models
MODEL_REVISION=${MODEL_REVISION:-8cf79a893e4c244e7acdc2699271dd84fe04d45f}
if [ ! -f models/Ming-3.0-tts-tiny/config.json ]; then
  echo "[1/4] downloading weights via modelscope (~17 GiB, revision ${MODEL_REVISION:0:8})"
  uv run --frozen modelscope download inclusionAI/Ming-3.0-tts-tiny \
    --revision "$MODEL_REVISION" \
    --local-dir models/Ming-3.0-tts-tiny
else
  echo "[1/4] weights present (pinned; delete models/Ming-3.0-tts-tiny to change revision)"
fi

# The checkpoint ships tts_config.maximum_decode_steps=250, i.e. every request
# is cut at exactly 20.00 s (250 decode steps x 12.5 steps/s) no matter how long
# the text is. Raise it to 1000 (80 s). The YAML "max_tokens: 801" does NOT
# bound speech length: the adapter overwrites it per request.
echo "[2/4] patching generation-length cap (250 -> 1000 steps / 80 s)"
python3 - <<'PY'
import json
p = "models/Ming-3.0-tts-tiny/config.json"
c = json.load(open(p))
t = c.setdefault("tts_config", {})
if int(t.get("maximum_decode_steps", 0)) < 1000:
    t["maximum_decode_steps"] = 1000
    json.dump(c, open(p, "w"), indent=4, ensure_ascii=False)
    print("[patch] maximum_decode_steps -> 1000")
else:
    print("[patch] maximum_decode_steps already >= 1000")
PY

if [ "$START" != 1 ]; then
  echo "done (--no-start): weights ready in models/Ming-3.0-tts-tiny; run ./deploy.sh to build and start"
  exit 0
fi

echo "[3/4] building and starting"
docker compose up -d --build

echo "[4/4] waiting for readiness (cold start ~190 s)"
ready=0
for _ in $(seq 1 180); do
  if curl -sf "http://127.0.0.1:$PORT/v1/models" >/dev/null; then ready=1; break; fi
  sleep 5
done
if [ "$ready" != 1 ]; then
  echo "service did not become ready in 15 minutes; last logs:" >&2
  docker compose logs --tail=80 >&2 || true
  exit 1
fi

curl -s "http://127.0.0.1:$PORT/v1/models"; echo
curl -s "http://127.0.0.1:$PORT/v1/audio/speech" \
  -H 'Content-Type: application/json' \
  -d '{"model":"ming3","input":"部署完成，这是一段测试音频。","response_format":"wav"}' \
  -o demo.wav
python3 - <<'PY' 2>/dev/null || true
import wave
w = wave.open("demo.wav")
print(f"demo.wav: {w.getframerate()} Hz, {w.getnchannels()} ch, {w.getnframes()/w.getframerate():.2f} s")
PY

echo "ready: http://<this-host>:$PORT/v1"
