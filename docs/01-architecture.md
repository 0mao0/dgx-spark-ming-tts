# Architecture

![topology](../assets/architecture.png)

| Hop | Process | Port | Role |
|---|---|---|---|
| 1 | client | — | `POST /api/ming/v1/audio/speech` over HTTPS |
| 2 | nginx on the VPS | 443 | TLS, bearer-token gate, strips `Authorization`, streams the body |
| 3 | Tailscale | — | VPS → Spark private path; no inbound port on the home router |
| 4 | nginx in the `omni` container | 8101 | streaming proxy; `proxy_buffering off`; hides `/docs`, `/redoc`, `/openapi.json` |
| 5 | `vllm serve --omni` | 8094 | two-stage pipeline, OpenAI-compatible speech API |
| 6 | model | — | `/models/Ming-3.0-tts-tiny`, 17 GiB on disk |

## Request path

The VPS hop is optional; steps 4–6 are the whole service. The inner proxy exists
for three reasons: it is a stable port when the engine restarts, it disables
buffering on both directions, and it closes the engine's debug pages. The engine
itself binds `0.0.0.0:8094` because the container uses host networking.

## Pipeline

`ming3_tts` splits the model into two stages that share GPU 0 and a
shared-memory connector:

| Stage | Work | Seqs | Memory | Runtime notes |
|---|---|---|---|---|
| 0 | autoregressive Ling V3 MoE → audio latents | 10 | `gpu_memory_utilization: 0.22` | `FULL_AND_PIECEWISE` CUDA graphs, capture sizes 1…4096, `max_model_len 4096`, `max_tokens 801` |
| 1 | flow decoder → PCM | 10 | `gpu_memory_utilization: 0.05` | eager, `max_model_len 4096`, `max_tokens 1` |

The connector feeds stage 1 with 25-latent chunks after a 4-latent initial
chunk (`latent_chunk_ramp: true`). Admission batching starts a prefill when
four requests are waiting, six are running, or 300 ms have elapsed
(`min_batch 4`, `min_running 6`, `max_wait_ms 300`). Sampling is deterministic
(`temperature 0`, `top_p 1`, `top_k -1`).

`max_model_len 4096` covers the text prompt plus generated audio tokens. Keep a
single request at or below roughly 300 Chinese characters; split longer text
into concurrent requests, which the engine handles better than one long stream.

## Memory

The GB10 exposes a single 121 GiB unified pool.

| Item | Size |
|---|---|
| weights on disk | 17 GiB |
| stage 0 reservation (`0.22 × 121`) | ≈ 26.6 GiB |
| stage 1 reservation (`0.05 × 121`) | ≈ 6.1 GiB |
| observed host use with MinerU + Popo resident | 87 GiB |
| available at that moment | 34 GiB |

Both stages share the same GPU; the two utilization values are reservations for
KV cache and graph memory, not independent devices.

## Supervision

| Unit | Type | Behavior |
|---|---|---|
| `ming-tts.service` | simple | starts the container if needed, runs `serve_ming9198.sh`, restarts after 15 s, triggers warmup |
| `ming-tts-proxy.service` | simple | runs nginx in the container on 8101, restarts after 5 s |
| `ming-tts-warmup.service` | oneshot | waits for `/v1/models` (up to 600 s), sends one speech request |

All three are `enable`d. The warmup unit is what keeps the first real caller
from paying graph capture; see [05-pitfalls.md](05-pitfalls.md).
