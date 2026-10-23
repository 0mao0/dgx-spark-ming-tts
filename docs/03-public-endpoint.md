# Public HTTPS endpoint

The Spark has no inbound port. Publish through a small VPS that already has
TLS, using a private Tailscale path to the Spark. The route is independent of
any application: it is a gateway prefix, nothing else on the VPS needs to know
about TTS.

```
client ── HTTPS ──> VPS nginx :443 ── Tailscale ──> spark:8101 ──> spark:8094
                    /api/ming/v1                     nginx proxy     vllm-omni
                    bearer token
```

## What is in `deploy/vps/`

| File | Purpose |
|---|---|
| `ming-upstream.conf` | `upstream ming_backend` → `<DGX_TAILSCALE_IP>:8101` |
| `ming-token.conf.example` | bearer-token map; copy to `/etc/nginx/conf.d/ming-token.conf` and replace the placeholder |
| `ming-location.conf` | `/api/ming/v1/` location: token gate, streaming, 64 MiB body, 900 s timeouts |
| `install.sh` | installs the three files, appends the location once, runs `nginx -t`, reloads |

## Install

On the VPS:

```bash
# 1. copy deploy/vps/ here
cd deploy/vps
# 2. edit ming-upstream.conf: replace <DGX_TAILSCALE_IP>
# 3. edit ming-token.conf.example: replace the placeholder
printf 'mng_'; openssl rand -hex 24
# 4. install
sudo ./install.sh /etc/nginx/ai-proxy-locations.conf
```

`install.sh` refuses to run while either placeholder remains. It backs up the
location file before appending, so the change is one block to delete on
rollback.

Requirements already assumed by the script: the domain resolves to the VPS, a
TLS certificate is installed, and port 443 is open. The location block is
included by the existing `server` block that serves your domain.

## Verify

Replace `<token>` and `<domain>`:

| Check | Command | Expected |
|---|---|---|
| no token | `curl -s -o /dev/null -w '%{http_code}' https://<domain>/api/ming/v1/models` | `401` |
| wrong token | same with `-H 'Authorization: Bearer wrong'` | `401` |
| models | `curl -s -H 'Authorization: Bearer <token>' https://<domain>/api/ming/v1/models` | `id: ming3` |
| wav | POST speech with `response_format: wav` | 200, `audio/wav`, 44100 Hz |
| stream | POST with `pcm` + `stream: true` | 200, `x-audio-sample-rate: 44100` |
| concurrency | `MING_URL=https://<domain>/api/ming/v1/audio/speech MING_TOKEN=<token> python3 scripts/probe10.py` | 10/10, ~3.5–3.8 s TTFT |

Measured on this deployment (short text): first byte 0.29 s over HTTPS, wav
3.6 s / 317 KB, five concurrent requests 5/5 in 2.8–6.6 s.

## Authentication model

- The token map lives in `/etc/nginx/conf.d/ming-token.conf`, separate from any
  other route's credentials.
- The location strips `Authorization` before proxying (`proxy_set_header
  Authorization ""`). The engine never sees the token.
- The engine itself has no authentication. Never expose port 8094 or 8101
  directly to the internet.

Rotate one caller without touching others by adding multiple lines to the map:

```nginx
map $http_authorization $ming_ok {
    default 0;
    "~^Bearer mng_aaa..." 1;
    "~^Bearer mng_bbb..." 1;
}
```

Revoke: delete that line and `nginx -t && systemctl reload nginx`. Closing the
entire route: remove the `api/ming/v1` location block and reload.

## Failure modes

| Symptom | Cause | Check |
|---|---|---|
| 401 for a working token | token edited without reload, or wrong scheme | `nginx -t`, reload, confirm `Bearer ` prefix |
| 502 / 504 | home uplink down, Spark off, Tailscale down, engine cold | `curl http://<tailscale-ip>:8101/v1/models` from the VPS |
| 200 then connection resets mid-audio | buffering re-enabled somewhere | `proxy_buffering off` on both proxies |
| Long gaps between chunks | client reads through a buffering proxy of its own | `curl -N`, disable client-side buffering |

There is no rate limiting in this recipe. The bearer token is the only control.
If the endpoint is shared widely, add `limit_req`/`limit_conn` at the VPS or a
per-caller token per consumer.
