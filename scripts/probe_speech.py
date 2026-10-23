#!/usr/bin/env python3
"""Single speech request with timing and response headers.

Examples:
  python probe_speech.py --format wav --out out.wav
  python probe_speech.py --format pcm --stream --out out.pcm
  MING_TOKEN=... python probe_speech.py --url https://tts.example.com/api/ming/v1/audio/speech
"""
import argparse
import json
import os
import time
import urllib.error
import urllib.request

DEFAULT_TEXT = "这是流式语音合成接口的测试文本，用来检查首包延迟和采样率。"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("MING_URL", "http://127.0.0.1:8094/v1/audio/speech"))
    ap.add_argument("--model", default=os.environ.get("MING_MODEL", "ming3"))
    ap.add_argument("--text", default=DEFAULT_TEXT)
    ap.add_argument("--format", choices=["wav", "pcm"], default="wav")
    ap.add_argument("--stream", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    payload = {
        "model": args.model,
        "input": args.text,
        "response_format": args.format,
        "language": "Chinese",
    }
    if args.stream:
        payload["stream"] = True
        payload["stream_format"] = "audio"
    ref_audio = os.environ.get("MING_REF_AUDIO")
    if ref_audio:
        payload["ref_audio"] = ref_audio
        payload["ref_text"] = os.environ.get("MING_REF_TEXT", "")

    headers = {"Content-Type": "application/json"}
    token = os.environ.get("MING_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token

    req = urllib.request.Request(args.url, data=json.dumps(payload).encode(), headers=headers)
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=180)
    except urllib.error.HTTPError as exc:
        print("HTTP", exc.code, exc.read()[:300].decode("utf-8", "replace"))
        return 1

    first = None
    data = bytearray()
    while True:
        chunk = resp.read(65536)
        if not chunk:
            break
        if first is None:
            first = time.time() - t0
        data.extend(chunk)

    headers = {k.lower(): v for k, v in resp.getheaders()}
    print(
        json.dumps(
            {
                "status": resp.status,
                "ttfb_s": round(first or 0, 3),
                "total_s": round(time.time() - t0, 3),
                "bytes": len(data),
                "content_type": headers.get("content-type"),
                "sample_rate": headers.get("x-audio-sample-rate"),
                "channels": headers.get("x-audio-channels"),
            }
        )
    )
    if args.out:
        with open(args.out, "wb") as fh:
            fh.write(data)
        print("saved", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
