# Benchmarks

All numbers below are from one DGX Spark (GB10, 121 GiB unified) running the
ten-stream profile in `deploy/ming3_9198_gb10.yaml`. MinerU and Popo were also
resident; 87 GiB of unified memory was in use and 34 GiB available.

## Method

- Ten fixed Chinese/mixed texts, 13–43 characters each, **302 characters
  total**. All ten requests start at the same time.
- `response_format: pcm`, `stream: true`, `stream_format: audio`.
- TTFT = time from request write to the first non-empty read. Wall = time to
  the last byte.
- Warm cache: the service had already served traffic (see cold-start note).
- ASR check: raw PCM wrapped as 44.1 kHz mono WAV, transcribed by a
  SenseVoice-compatible endpoint; all ten transcripts matched the input text.

## Ten concurrent streams

| # | Characters | TTFT (s) | Wall (s) |
|---|---|---|---|
| 1 | 43 | 3.80 | 16.77 |
| 2 | 29 | 3.80 | 15.03 |
| 3 | 34 | 3.80 | 14.86 |
| 4 | 13 | 3.80 | 9.50 |
| 5 | 30 | 3.49 | 15.82 |
| 6 | 40 | 3.76 | 16.81 |
| 7 | 41 | 3.79 | 16.90 |
| 8 | 26 | 3.76 | 15.51 |
| 9 | 21 | 3.79 | 14.51 |
| 10 | 25 | 3.79 | 14.79 |

| Metric | Value |
|---|---|
| success | 10/10 |
| TTFT range | 3.49–3.80 s |
| batch wall | 16.91 s |
| aggregate text rate | ≈ 17.9 characters/s |
| ASR match | 10/10 |

The TTFT plateau is the admission-batching design: all ten prefills are let
in together and finish within ~0.3 s of each other, so short and long requests
start audio at nearly the same time.

![10 concurrent streams](../assets/10-way-gantt.png)

## Single stream

| Metric | Value |
|---|---|
| first audio, warm | 0.53 s |
| RTF (wall / audio duration) | 0.235 |

## Public HTTPS path (short text)

| Metric | Value |
|---|---|
| first byte over TLS | 0.29 s |
| wav, 35 characters | 3.6 s audio, 317 KB |
| five concurrent requests | 5/5, 2.8–6.6 s |

The public numbers use a single short sentence and are not comparable with the
302-character batch above.

## Reading the numbers

- **Compare like-for-like.** Text length dominates wall time; a 13-character
  request finished in 9.5 s while a 43-character one took 16.8 s in the same
  batch.
- **Cold cache changes everything.** The first batch after a restart can show a
  45 s TTFT. The warmup unit exists to prevent that; if you disable it, measure
  twice and use the second run.
- **The box is shared.** Adding MinerU or Popo load moves these numbers; they
  are not an isolated synthetic ceiling.
- **Deterministic sampling** (`temperature 0`) makes repeated runs comparable,
  but not bit-identical across graph re-captures.
