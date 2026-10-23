# dgx-spark-ming-tts

Ming-3.0-TTS tiny on one DGX Spark (GB10): 44.1 kHz streaming, ten concurrent
streams, one container, one command.

## Result

| Metric | Value |
|---|---|
| first audio, single stream, warm | 0.53 s |
| ten concurrent streams (302 characters) | 10/10, first audio 3.5–3.8 s, wall 16.9 s |
| aggregate text rate | ≈ 18 characters/s |
| output | 44100 Hz mono PCM16, rate reported in response headers |
| footprint | 17 GiB weights, ≈33 GiB reservation on a 121 GiB unified pool |

![topology](assets/architecture.png)

![10 concurrent streams](assets/10-way-gantt.png)

## Call the hosted API

Base URL: `https://tts.angineer.cn/api/ming/v1` — ask the operator for a key.

```bash
curl -s https://tts.angineer.cn/api/ming/v1/audio/speech \
  -H "Authorization: Bearer $MING_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"ming3","input":"你好，世界。","response_format":"wav"}' \
  -o out.wav
```

Streaming PCM: add `"response_format":"pcm","stream":true,"stream_format":"audio"`.
Read `X-Audio-Sample-Rate` (44100) before playing raw PCM.

## Deploy your own

Prerequisites: DGX Spark (GB10), Docker with NVIDIA runtime, `docker compose`,
ports 8094 and 8101 free, about 40 GiB free disk, internet access.

```bash
git clone <this-repo> dgx-spark-ming-tts
cd dgx-spark-ming-tts
./deploy.sh
```

`deploy.sh` downloads the 17 GiB weights on first run, builds the image
(vLLM 0.32.0 + the pinned vLLM-Omni overlay), starts the container, and waits
until the API answers. A cold start takes about 190 s. When it prints `ready`,
the API is at `http://<spark>:8094/v1` and the streaming proxy at
`http://<spark>:8101/v1`.

Slow network in mainland China: pass a mirror to the build.

```bash
PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple ./deploy.sh
```

## API

`POST /v1/audio/speech`

| Field | Value |
|---|---|
| `model` | `ming3` |
| `input` | text, keep a single request at or below ~300 Chinese characters |
| `response_format` | `wav` or `pcm` |
| `stream` / `stream_format` | `true` / `audio` for chunked PCM |
| `language` | `Chinese` |
| `ref_audio` | optional http(s) or `data:` URL; omit for the default voice |
| `ref_text` | transcript of `ref_audio`; must match exactly |

## Notes

- **44.1 kHz, not 24 kHz.** Playing this stream as 24 kHz makes it 1.8× slow,
  one octave down, and muffled.
- **Cold start.** First batch after a restart can show a 45 s TTFT; the image
  runs a warmup request in the background to absorb it.
- **Pinned overlay.** vLLM-Omni PR #9198 (`091f7363`) is still a draft. The
  Dockerfile pins that commit; replace it with a released package once merged.
- **0.5B is a different model branch.** `Ming-3.0-tts-0.5B` is Qwen2.5 dense +
  DiT with patch size 1 and does not load in this pipeline (patch size 4).
- **`sample_rate` is rejected** by the current adapter for every value. Omit
  it; resample client-side if you need 24 kHz.
- **Voice cloning:** keep `ref_text` in a file next to the reference audio. A
  mismatched transcript shifts prosody and can sound like a dialect.

## Operations

```bash
docker compose logs -f          # engine and proxy logs
docker compose restart          # restart the service
docker compose down             # stop; weights and image stay
./deploy.sh                     # idempotent re-deploy / update
```

Public HTTPS with a bearer token (optional): run `deploy/vps/install.sh` on a
VPS, as described in its header. The engine itself has no authentication; do
not expose 8094 or 8101 directly.

## Credits

Model: `inclusionAI/Ming-3.0-tts-tiny`, MIT. Engine: vLLM-Omni, Apache-2.0,
PRs #9119 and #9198. Container, configs, probes, and charts: this repository,
Apache-2.0. Unofficial; not endorsed by inclusionAI or the vLLM-Omni authors.

## License

Apache-2.0, see [LICENSE](LICENSE) and [NOTICE](NOTICE).
