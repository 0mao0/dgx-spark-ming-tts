#!/usr/bin/env python3
"""Wait for the TTS server, then send one request to absorb cold compile.

The first batch after a restart pays graph capture and weight paging (tens of
seconds). One warmup request moves that cost off the first real caller.

Environment:
  MING_BASE            default http://127.0.0.1:8094
  MING_MODEL           default ming3
  MING_READY_TIMEOUT   default 600 seconds
  MING_REF_AUDIO       optional data: audio URL; omit to use the default voice
  MING_REF_TEXT        transcript of MING_REF_AUDIO (required when set)
"""
import json
import os
import time
import urllib.request

BASE = os.environ.get("MING_BASE", "http://127.0.0.1:8094")
MODEL = os.environ.get("MING_MODEL", "ming3")
READY_TIMEOUT = int(os.environ.get("MING_READY_TIMEOUT", "600"))


def wait_ready() -> None:
    deadline = time.time() + READY_TIMEOUT
    while time.time() < deadline:
        try:
            urllib.request.urlopen(BASE + "/v1/models", timeout=3)
            return
        except Exception:
            time.sleep(5)
    raise SystemExit(f"model not ready after {READY_TIMEOUT}s")


wait_ready()

payload = {
    "model": MODEL,
    "input": "Warmup request. This audio can be discarded.",
    "response_format": "pcm",
    "stream": True,
    "stream_format": "audio",
    "language": "Chinese",
}
ref_audio = os.environ.get("MING_REF_AUDIO")
if ref_audio:
    payload["ref_audio"] = ref_audio
    payload["ref_text"] = os.environ.get("MING_REF_TEXT", "")

body = json.dumps(payload).encode()
req = urllib.request.Request(
    BASE + "/v1/audio/speech", data=body, headers={"Content-Type": "application/json"}
)
t0 = time.time()
resp = urllib.request.urlopen(req, timeout=300)
first = None
total = 0
for chunk in iter(lambda: resp.read(65536), b""):
    if first is None:
        first = time.time() - t0
    total += len(chunk)
print(f"warmup done ttft={first:.2f}s wall={time.time() - t0:.2f}s bytes={total}")
