# Deploy

Target: one DGX Spark (GB10), 121 GiB unified memory, Docker with the NVIDIA
container runtime. The recipe was verified on Ubuntu with CUDA 13.0 and
`lmsysorg/sglang:qwen38-27b`.

## 0. Prerequisites

| Item | Requirement |
|---|---|
| GPU | GB10, compute capability 12.1 |
| Docker | NVIDIA runtime enabled (`docker run --gpus all` works) |
| Disk | ≥ 40 GiB for image, overlay, and weights |
| Memory | 121 GiB unified; the service reserves ≈33 GiB |
| Network | outbound for image, overlay, and weights |
| Privileges | root or docker group; systemd unit installation needs root |

## 1. Container

```bash
docker pull lmsysorg/sglang:qwen38-27b
mkdir -p /home/$USER/models /home/$USER/omni-out
docker run -d --name omni --gpus all --network host --ipc host --privileged \
  --shm-size 16g --restart unless-stopped \
  -v /home/$USER/models:/models -v /home/$USER/omni-out:/out \
  lmsysorg/sglang:qwen38-27b sleep infinity
docker exec omni nvidia-smi -L
```

The verified container runs `--privileged`. A narrower capability set was not
tested; if you tighten it, keep `/dev` access and shared memory.

## 2. Engine and overlay

The image ships torch 2.13.0+cu130 and Python 3.12. Add vLLM 0.32.0 without
letting pip replace torch:

```bash
docker exec omni pip install --no-deps vllm==0.32.0
docker exec omni python3 -c "import vllm, torch; print(vllm.__version__, torch.__version__)"
# 0.32.0 2.13.0+cu130
```

Ming is in vLLM-Omni main since PR #9119, but the ten-stream behavior comes
from draft PR #9198. Run that head as an overlay:

```bash
curl -L -o /tmp/pr9198.tgz \
  https://codeload.github.com/vllm-project/vllm-omni/tar.gz/refs/pull/9198/head
mkdir -p /home/$USER/omni-out/pr9198
tar -xzf /tmp/pr9198.tgz -C /home/$USER/omni-out/pr9198 --strip-components=1
```

This is the exact tree the service ran: PR #9198 head `091f7363`, still a
draft. Pin it; a force-push changes the tarball silently. Replace the overlay
with a released package once #9198 merges (see §9).

## 3. Weights

```bash
# ModelScope (mainland China)
docker exec -it omni bash -lc '
  pip install -q --no-deps modelscope &&
  modelscope download --model inclusionAI/Ming-3.0-tts-tiny \
    --local_dir /models/Ming-3.0-tts-tiny'

# Hugging Face alternative
docker exec -it omni bash -lc '
  pip install -q --no-deps huggingface_hub hf_transfer &&
  HF_HUB_ENABLE_HF_TRANSFER=1 hf download inclusionAI/Ming-3.0-tts-tiny \
    --local-dir /models/Ming-3.0-tts-tiny'
```

Expect ≈17 GiB. Do not substitute `Ming-3.0-tts-0.5B`; see
[05-pitfalls.md](05-pitfalls.md).

## 4. Configs

```bash
cp deploy/ming3_9198_gb10.yaml deploy/serve_ming9198.sh deploy/warm_ming.py \
   deploy/nginx_ming_proxy.conf /home/$USER/omni-out/
chmod +x /home/$USER/omni-out/serve_ming9198.sh
```

The paths inside the scripts assume `/out` and `/models`, which the bind mounts
above provide.

## 5. First run

```bash
docker exec -d omni bash -c 'bash /out/serve_ming9198.sh >/out/serve.log 2>&1'
docker exec omni tail -f /out/serve.log

# readiness poll (about 190 s on a cold start)
until curl -sf localhost:8094/v1/models >/dev/null; do sleep 5; done; echo ready
```

First load takes about 190 s. Wait for readiness, then check the contract:

```bash
curl -s localhost:8094/v1/models
# {"object":"list","data":[{"id":"ming3",...,"max_model_len":4096,...}]}

curl -s localhost:8094/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"model":"ming3","input":"公网接口冒烟测试。","response_format":"wav"}' \
  -o out.wav
```

`out.wav` must report 44100 Hz, mono, 16-bit. On Linux:

```bash
python3 -c "import wave; w=wave.open('out.wav'); print(w.getframerate(), w.getnchannels())"
```

Streaming check:

```bash
curl -sN localhost:8094/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"model":"ming3","input":"这是流式测试。","response_format":"pcm","stream":true,"stream_format":"audio"}' \
  -D - -o stream.pcm | grep -i x-audio
# x-audio-sample-rate: 44100
# x-audio-channels: 1
```

## 6. The ten-stream profile

Load this before measuring throughput: the first batch after a cold start pays
graph capture and can show a 45 s TTFT.

```bash
python3 scripts/probe10.py
```

From another host, point it at the proxy:

```bash
MING_URL=http://<spark>:8101/v1/audio/speech python3 scripts/probe10.py
```

Expected shape on an idle box: 10/10 success, TTFT 3.5–3.8 s, wall 16–18 s.
Numbers are text-dependent; compare like-for-like.

## 7. Systemd

```bash
sudo cp deploy/systemd/ming-tts.service \
        deploy/systemd/ming-tts-proxy.service \
        deploy/systemd/ming-tts-warmup.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ming-tts.service ming-tts-proxy.service
```

`ming-tts.service` starts the container (`ExecStartPre=-docker start omni`),
runs the engine, and triggers `ming-tts-warmup.service` after start. The proxy
unit starts nginx inside the same container on 8101.

Verify after a reboot:

```bash
systemctl is-active ming-tts ming-tts-proxy
journalctl -u ming-tts-warmup -n 5
# warmup done ttft=0.53s wall=1.81s bytes=...
curl -s localhost:8101/v1/models
```

## 8. Public HTTPS (optional)

See [03-public-endpoint.md](03-public-endpoint.md). Skip it for LAN-only use;
`http://<spark>:8101/v1` already works inside the trusted network.

## 9. Upgrade path

Replace the overlay when both conditions hold:

1. PR #9198 is merged (or equivalent behavior is in a release).
2. A vLLM-Omni release after the merge is on PyPI.

Then:

```bash
docker exec omni pip install vllm-omni==<version>
docker exec omni pip show vllm vllm-omni | grep -E '^(Name|Version)'
# if pip moved vllm off 0.32.0, reinstall it with --no-deps and retest
# remove PYTHONPATH=/out/pr9198 from serve_ming9198.sh
```

Keep the old overlay directory until the new path passes the same checks
(44.1 kHz header, 10/10 concurrency, ASR text match). Rollback is restoring the
`PYTHONPATH` line; see [06-rollback.md](06-rollback.md).
