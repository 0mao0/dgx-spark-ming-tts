#!/usr/bin/env python3
"""Ten concurrent streaming requests against a Ming TTS endpoint.

Environment:
  MING_URL          default http://127.0.0.1:8094/v1/audio/speech
  MING_MODEL        default ming3
  MING_TOKEN        optional Bearer token
  MING_REF_AUDIO    optional data: URL; omit to use the default voice
  MING_REF_TEXT     transcript for MING_REF_AUDIO

Prints one JSON line per request plus a summary line. Exit code 1 if any
request fails.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request

URL = os.environ.get("MING_URL", "http://127.0.0.1:8094/v1/audio/speech")
MODEL = os.environ.get("MING_MODEL", "ming3")
TOKEN = os.environ.get("MING_TOKEN", "")
REF_AUDIO = os.environ.get("MING_REF_AUDIO", "")
REF_TEXT = os.environ.get("MING_REF_TEXT", "")

TEXTS = [
    "今天汇报三个点：第一，Q3 营收 12.8 亿元，同比增长 23.5 percent。",
    "第二，vLLM-Omni 版本 0.32.0 已合入主线。",
    "用户数突破 210 万，Token 消耗下降 18 percent。",
    "天气不错，我们出去走走吧。",
    "请尽快确认这份合同的付款条款，尤其是分期付款和违约金的部分。",
    "人工智能技术在近年来取得了长足的进展，大语言模型的出现更是改变了整个行业的格局。",
    "从自然语言处理到计算机视觉，从代码生成到科学发现，这些模型展现出了惊人的通用能力。",
    "卫星绕地球运行，每九十分钟向地面站回传一次遥测数据。",
    "请在下周一之前给我答复，包括预算和时间表。",
    "感谢各位同事参加今天的施工例会，会后把材料交给我。",
]

results = [None] * len(TEXTS)


def one(i: int) -> None:
    payload = {
        "model": MODEL,
        "input": TEXTS[i],
        "response_format": "pcm",
        "stream": True,
        "stream_format": "audio",
        "language": "Chinese",
    }
    if REF_AUDIO:
        payload["ref_audio"] = REF_AUDIO
        payload["ref_text"] = REF_TEXT
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN

    t0 = time.time()
    first = None
    size = 0
    try:
        req = urllib.request.Request(URL, data=json.dumps(payload).encode(), headers=headers)
        resp = urllib.request.urlopen(req, timeout=180)
        for chunk in iter(lambda: resp.read(65536), b""):
            if first is None:
                first = time.time() - t0
            size += len(chunk)
        results[i] = {
            "id": i + 1,
            "ttft": round(first, 2) if first else None,
            "wall": round(time.time() - t0, 2),
            "bytes": size,
            "chars": len(TEXTS[i]),
        }
    except urllib.error.HTTPError as exc:
        results[i] = {"id": i + 1, "error": f"HTTP {exc.code}", "body": exc.read()[:200].decode("utf-8", "replace")}
    except Exception as exc:  # noqa: BLE001 - report any transport failure per request
        results[i] = {"id": i + 1, "error": type(exc).__name__, "body": str(exc)[:200]}


threads = [threading.Thread(target=one, args=(i,)) for i in range(len(TEXTS))]
t0 = time.time()
for t in threads:
    t.start()
for t in threads:
    t.join()

for row in results:
    print(json.dumps(row, ensure_ascii=False), flush=True)

ok = [r for r in results if r and "error" not in r]
summary = {
    "ok": len(ok),
    "total": len(results),
    "wall": round(time.time() - t0, 2),
    "ttft_min": min((r["ttft"] for r in ok), default=None),
    "ttft_max": max((r["ttft"] for r in ok), default=None),
}
print(json.dumps(summary), flush=True)
raise SystemExit(0 if len(ok) == len(results) else 1)
