# dgx-spark-ming-tts

Serve **Ming-3.0-TTS tiny** on a DGX Spark (GB10) with vLLM-Omni: streaming
44.1 kHz PCM, ten concurrent streams on one box, and an optional
token-protected HTTPS entry.

## Effect

A warm single stream returns its first audio in **0.53 s** at RTF 0.235.
Ten concurrent streams (13–43 Chinese characters each, 302 total) all succeed:
first audio **3.49–3.80 s**, whole batch **16.6–17.6 s**, about **18
characters/s** aggregate. Output is model-native **44100 Hz mono PCM16** and the
response states it in `X-Audio-Sample-Rate` / `X-Audio-Channels`.

The ten-stream profile reserves 0.22 + 0.05 of the 121 GiB unified memory pool
(≈33 GiB) on top of 17 GiB of weights. It runs beside MinerU and Popo on the
same box (87 GiB in use with both resident). An optional public path adds TLS
and a bearer token; measured first byte over HTTPS was 0.29 s.

![topology](assets/architecture.png)

![10 concurrent streams](assets/10-way-gantt.png)

## Models

| Model | Weights | Size | License |
|---|---|---|---|
| Ming-3.0-tts-tiny (Ling V3 MoE, 7.9B total / 1.3B active) | [Hugging Face](https://huggingface.co/inclusionAI/Ming-3.0-tts-tiny) · [ModelScope](https://modelscope.cn/models/inclusionAI/Ming-3.0-tts-tiny) | 17 GiB | MIT |

A reference voice is optional. Omit `ref_audio` and the built-in default voice
is used. To clone a voice, send 5–15 s of audio plus its exact transcript
(`ref_text`); a mismatched transcript shifts prosody.

## Usage

The full runbook is [docs/02-deploy.md](docs/02-deploy.md). The short path:

```bash
# 1. Image and container (ships torch 2.13.0+cu130, CUDA 13.0, Python 3.12)
docker pull lmsysorg/sglang:qwen38-27b
docker run -d --name omni --gpus all --network host --ipc host --privileged \
  --shm-size 16g --restart unless-stopped \
  -v /home/$USER/models:/models -v /home/$USER/omni-out:/out \
  lmsysorg/sglang:qwen38-27b sleep infinity

# --no-deps keeps the image's torch/CUDA stack intact
docker exec omni pip install --no-deps vllm==0.32.0

# 2. vLLM-Omni overlay: PR #9198 head (Ming itself is in main since #9119)
curl -L -o /tmp/pr9198.tgz \
  https://codeload.github.com/vllm-project/vllm-omni/tar.gz/refs/pull/9198/head
mkdir -p /home/$USER/omni-out/pr9198
tar -xzf /tmp/pr9198.tgz -C /home/$USER/omni-out/pr9198 --strip-components=1

# 3. Weights
docker exec -it omni bash -lc '
  pip install -q --no-deps modelscope &&
  modelscope download --model inclusionAI/Ming-3.0-tts-tiny \
    --local_dir /models/Ming-3.0-tts-tiny'
# Hugging Face alternative:
# docker exec -it omni bash -lc '
#   pip install -q --no-deps huggingface_hub hf_transfer &&
#   HF_HUB_ENABLE_HF_TRANSFER=1 hf download inclusionAI/Ming-3.0-tts-tiny \
#     --local-dir /models/Ming-3.0-tts-tiny'

# 4. Configs
cp deploy/ming3_9198_gb10.yaml deploy/serve_ming9198.sh deploy/warm_ming.py \
   deploy/nginx_ming_proxy.conf /home/$USER/omni-out/

# 5. Serve (logs to /out/serve.log)
docker exec -d omni bash -c 'bash /out/serve_ming9198.sh >/out/serve.log 2>&1'

# 6. Verify
curl -s localhost:8094/v1/models
curl -s localhost:8094/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"model":"ming3","input":"你好，世界。","response_format":"wav"}' -o out.wav
```

Systemd units (server, streaming proxy, warmup) live in
[deploy/systemd](deploy/systemd). They assume `/out` is the bind mount shown
above and start in the right order after a reboot.

## API

`POST /v1/audio/speech`

| Field | Value |
|---|---|
| `model` | `ming3` |
| `input` | text; keep single requests at or below ~300 Chinese characters |
| `response_format` | `wav` or `pcm` |
| `stream` / `stream_format` | `true` / `audio` for chunked PCM |
| `language` | `Chinese` |
| `ref_audio` | optional http(s) URL, `data:` URL, or `file://` (the last needs `--allowed-local-media-path`) |
| `ref_text` | transcript of `ref_audio`; must match exactly |

A streaming PCM response is `audio/pcm` with `X-Audio-Sample-Rate: 44100` and
`X-Audio-Channels: 1`. A WAV response carries the rate in its header.

## Docs

- [01 Architecture](docs/01-architecture.md) — hops, pipeline stages, memory, supervision
- [02 Deploy](docs/02-deploy.md) — full runbook and verification
- [03 Public endpoint](docs/03-public-endpoint.md) — VPS route, token, rotation
- [04 Benchmarks](docs/04-benchmarks.md) — method and per-request numbers
- [05 Pitfalls](docs/05-pitfalls.md) — ten failures and their fixes
- [06 Rollback](docs/06-rollback.md) — layered shutdown

## Notes

- **44.1 kHz, not 24 kHz.** Clients that apply the OpenAI `pcm` convention
  (24 kHz) play this stream 1.8× slow, one octave down, and it sounds muffled.
- **Cold start.** After a reboot the server needs about 190 s to load. The
  first concurrent batch can show a 45 s TTFT; the warmup unit sends one
  request to absorb graph capture before callers arrive.
- **Pinned overlay.** Ming landed in vLLM-Omni main through PR #9119 (merge
  `524f04c`). PR #9198 (head `091f736`, still draft) carries the ten-stream
  optimizations; until it merges, run it as a `PYTHONPATH` overlay. The latest
  vLLM-Omni release (v0.32.0rc1) predates both.
- **The 0.5B model is a different branch.** `Ming-3.0-tts-0.5B` is Qwen2.5
  dense plus a DiT head with patch size 1; this pipeline pins patch size 4, so
  it does not load. It is not a smaller drop-in.
- **Unofficial.** Not endorsed by inclusionAI or the vLLM-Omni authors.

## Credits

Model: `inclusionAI/Ming-3.0-tts-tiny`, MIT. Engine: vLLM-Omni, Apache-2.0,
PRs #9119 and #9198. Deployment configs, units, proxy config, probes and charts
in this repository are original work.

## License

Apache-2.0, see [LICENSE](LICENSE) and [NOTICE](NOTICE).
