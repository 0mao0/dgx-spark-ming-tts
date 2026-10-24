#!/usr/bin/env python3
"""Synthesize with a reference voice (zero-shot cloning), streaming to a WAV.

The API takes the reference as a base64 data URL, so this script reads the WAV,
attaches the sibling transcript, and streams PCM frames back into a 44.1 kHz
WAV. Use voices/ref-02-14s.wav to hear the shipped reference, or point --ref at
your own recording (16 kHz mono WAV, 5-15 s, exact transcript in a .txt file).

Examples:
  python tts_with_ref.py --text "你好，世界。" --ref voices/ref-02-14s.wav
  MING_URL=... MING_TOKEN=... python tts_with_ref.py --text "..." --ref my.wav
"""
import argparse
import base64
import json
import os
import re
import struct
import time
import urllib.request

SAMPLE_RATE = 44100
CHANNELS = 1


def wav_header(pcm_len: int) -> bytes:
    return (
        b"RIFF" + struct.pack("<I", 36 + pcm_len) + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, CHANNELS, SAMPLE_RATE,
                      SAMPLE_RATE * CHANNELS * 2, CHANNELS * 2, 16)
        + b"data" + struct.pack("<I", pcm_len)
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("MING_URL", "http://127.0.0.1:8094/v1/audio/speech"))
    ap.add_argument("--model", default=os.environ.get("MING_MODEL", "ming3"))
    ap.add_argument("--text", required=True)
    ap.add_argument("--ref", required=True, help="reference WAV (PCM)")
    ap.add_argument("--ref-text", default="", help="transcript; defaults to the sibling .txt")
    ap.add_argument("--seed", type=int, default=7,
                    help="fixed seed keeps one text stable; some seeds degenerate (see README)")
    ap.add_argument("--max-chars", type=int, default=200,
                    help="split long text into segments of at most this many characters "
                         "(0 disables; the server truncates one request at 80 s of audio)")
    ap.add_argument("--out", default="out.wav")
    args = ap.parse_args()

    ref_text = args.ref_text
    if not ref_text:
        sibling = os.path.splitext(args.ref)[0] + ".txt"
        if not os.path.exists(sibling):
            raise SystemExit(f"no --ref-text and no transcript at {sibling}")
        with open(sibling, encoding="utf-8") as handle:
            ref_text = handle.read().strip()

    with open(args.ref, "rb") as handle:
        ref_b64 = base64.b64encode(handle.read()).decode()

    payload = {
        "model": args.model,
        "input": args.text,
        "response_format": "pcm",
        "stream": True,  # SSE frames; stream_format:"audio" would return raw PCM
        "language": "Chinese",
        "seed": args.seed,
        "ref_audio": "data:audio/wav;base64," + ref_b64,
        "ref_text": ref_text,
    }
    token = os.environ.get("MING_TOKEN")

    def synthesize(text: str, seed: int) -> tuple[bytes, float, float]:
        payload["input"] = text
        payload["seed"] = seed
        req = urllib.request.Request(
            args.url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        if token:
            req.add_header("Authorization", "Bearer " + token)
        started = time.time()
        first = None
        pcm_local = bytearray()
        with urllib.request.urlopen(req, timeout=600) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "ignore").strip()
                if not line.startswith("data:"):
                    continue
                try:
                    event = json.loads(line[5:])
                except json.JSONDecodeError:
                    continue
                if event.get("audio"):
                    if first is None:
                        first = time.time() - started
                    pcm_local += base64.b64decode(event["audio"])
                if event.get("type") == "speech.audio.done":
                    break
        return bytes(pcm_local), first or 0.0, time.time() - started

    # The server truncates every request at tts_config.maximum_decode_steps
    # (20 s stock, 80 s with the deploy patch) and still reports success, so
    # long text has to be split client-side. Segment on sentence boundaries.
    def split_text(text: str, limit: int) -> list[str]:
        units = re.findall(r"[^。！？；\n]+[。！？；\n]?", text) or [text]
        out, cur = [], ""
        for unit in units:
            if cur and len(cur) + len(unit) > limit:
                out.append(cur)
                cur = ""
            if len(unit) > limit:
                out.extend(unit[i:i + limit] for i in range(0, len(unit), limit))
            else:
                cur += unit
        if cur:
            out.append(cur)
        return out or [text]

    segments = split_text(args.text, args.max_chars) if args.max_chars > 0 else [args.text]
    pcm = b""
    first = 0.0
    wall = 0.0
    for index, segment in enumerate(segments, 1):
        label = f"segment {index}/{len(segments)}" if len(segments) > 1 else "request"
        # Unlucky seeds make the model emit the end token after the minimum
        # number of steps: a ~1 s clip instead of the sentence. Retry.
        for attempt in range(3):
            seed = args.seed + attempt
            part, part_first, part_wall = synthesize(segment, seed)
            seconds = len(part) / 2 / SAMPLE_RATE
            if seconds >= 2 or len(segment) <= 8 or attempt == 2:
                print(f"{label}: seed {seed}, {seconds:.2f} s of audio")
                break
            print(f"{label}: seed {seed} degenerate ({seconds:.2f} s), retrying")
        if first == 0.0:
            first = part_first
        wall += part_wall
        pcm += part

    with open(args.out, "wb") as handle:
        handle.write(wav_header(len(pcm)))
        handle.write(pcm)

    print(
        f"{args.out}: {len(pcm) / 2 / SAMPLE_RATE:.2f} s audio in {len(segments)} segment(s), "
        f"first frame {first:.2f} s, wall {wall:.2f} s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
