# Pitfalls

Each item is a failure that cost time during the build. Symptom → cause → fix.

## 1. Audio plays 1.8× slow and sounds muffled

**Cause:** the stream is 44100 Hz, but the client labels it 24000 Hz (the
OpenAI `pcm` convention). The bytes are correct; the playback rate is wrong.

**Fix:** read `X-Audio-Sample-Rate` from the response, or hard-code 44100 for
this model. WAV responses carry the rate in the header. Do not resample the
server output down to 24 kHz unless the client truly needs it.

## 2. Speech drifts into a dialect (heard as Cantonese)

**Cause:** `ref_text` does not match the reference audio. The model supports
Sichuan and Cantonese output, so a mismatched transcript produces a real
dialect shift rather than noise.

**Fix:** keep the transcript in a file next to the reference audio and read it
at request time. Never reuse another voice's default text. ASR language tags
(`<|yue|>` vs `<|zh|>`) are a useful sentinel.

## 3. First batch after a restart shows a 45 s TTFT

**Cause:** weight paging and CUDA graph capture happen on the first real
requests. A cold engine is not a slow engine; it is an uninitialized one.

**Fix:** keep `ming-tts-warmup.service` enabled. It waits for `/v1/models` and
sends one speech request. If you disable it, send a warmup request yourself
before benchmarking.

## 4. `docker start ming` starts an empty container

**Cause:** an earlier experiment created a container named `ming` without the
engine or `/out` scripts.

**Fix:** the production container is `omni`. Check before debugging:

```bash
docker exec omni ls /out/pr9198 >/dev/null && echo correct-container
```

## 5. `sample_rate` returns 400 for every value

**Cause:** `Ming3TTSAdapter` does not declare `supported_output_sample_rates`,
so the serving layer rejects any requested rate. The native rate is 44100.

**Fix:** omit `sample_rate` and resample client-side if a lower rate is
required. This is a gap in the adapter, not a concurrency limit; it is
independent of the ten-stream profile.

## 6. `Ming-3.0-tts-0.5B` crashes at load

**Cause:** that checkpoint is a different branch: Qwen2.5 dense plus a DiT
head with patch size 1. The `ming3_tts` pipeline pins patch size 4, so stage 0
fails with a patch-size mismatch.

**Fix:** use `Ming-3.0-tts-tiny`. A smaller footprint means a smaller
`max_num_seqs` profile, not a smaller checkpoint.

## 7. `ref_audio` with a local path is rejected

**Cause:** only http(s), `data:` URLs, and `file://` are accepted, and
`file://` is disabled unless the server runs with
`--allowed-local-media-path`.

**Fix:** send a `data:audio/wav;base64,...` URL, an http(s) URL, or enable the
flag. A plain filesystem path is a 400.

## 8. Installing the “latest” vLLM-Omni does not run Ming

**Cause:** the newest release, v0.32.0rc1 (2026-10-19), predates the Ming merge
(#9119, 2026-10-21). PyPI was still at 0.30.0. vLLM 0.30 imports but fails at
runtime with missing symbols.

**Fix:** vLLM 0.32.0 plus the #9198 overlay, as in
[02-deploy.md](02-deploy.md). Wait for a release after #9198 before replacing
the overlay with `pip install`.

## 9. Streaming stalls or arrives in one burst

**Cause:** a buffering proxy between the client and the engine. Both nginx hops
must set `proxy_buffering off`; the inner one also needs
`proxy_request_buffering off` for uploads.

**Fix:** keep the provided proxy config, and test with `curl -N`. A 200 response
that delivers everything at the end is a buffering symptom, not a model
problem.

## 10. Long inputs fail or degrade

**Cause:** `max_model_len` is 4096 and the ten-stream profile sets
`max_tokens: 801` for stage 0. Very long text does not fit the same budget.

**Fix:** keep one request at or below ~300 Chinese characters and split longer
documents into concurrent requests. Ten parallel short requests are the
intended load, not one giant request.
