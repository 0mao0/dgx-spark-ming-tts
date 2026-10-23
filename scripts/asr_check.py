#!/usr/bin/env python3
"""Transcribe raw PCM files with a SenseVoice-compatible ASR endpoint.

Ming outputs 44100 Hz mono PCM16. Pass --rate 24000 only for models that
actually emit 24 kHz.

Environment:
  ASR_BASE        default http://127.0.0.1:8001
  ASR_TOKEN       bearer token
  ASR_TOKEN_FILE  file containing the token (used when ASR_TOKEN is unset)

Usage: python asr_check.py 'out/*.pcm'
"""
import glob
import json
import os
import subprocess
import sys
import tempfile
import wave

BASE = os.environ.get("ASR_BASE", "http://127.0.0.1:8001").rstrip("/")
TOKEN = os.environ.get("ASR_TOKEN", "")
if not TOKEN:
    token_file = os.environ.get("ASR_TOKEN_FILE", "")
    if token_file and os.path.exists(token_file):
        TOKEN = open(token_file, encoding="utf-8").read().strip()


def pcm_to_wav(pcm: str, wav: str, rate: int) -> None:
    with wave.open(wav, "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(rate)
        fh.writeframes(open(pcm, "rb").read())


def transcribe(path: str) -> str:
    cmd = [
        "curl", "-s", "--noproxy", "*", "-m", "120",
        "-X", "POST", f"{BASE}/v1/audio/transcriptions",
        "-F", f"file=@{path}",
    ]
    if TOKEN:
        cmd += ["-H", f"Authorization: Bearer {TOKEN}"]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=130).stdout
    try:
        return json.loads(out).get("text", "<no text>")
    except json.JSONDecodeError:
        return f"<ERR {out[:120]}>"


def main() -> int:
    rate = int(os.environ.get("PCM_RATE", "44100"))
    patterns = sys.argv[1:]
    if not patterns:
        print(__doc__)
        return 2
    for pattern in patterns:
        for pcm in sorted(glob.glob(pattern)):
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                wav = tmp.name
            try:
                pcm_to_wav(pcm, wav, rate)
                print(os.path.basename(pcm), "=>", transcribe(wav)[:200], flush=True)
            finally:
                os.unlink(wav)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
