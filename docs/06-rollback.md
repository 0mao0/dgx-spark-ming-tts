# Rollback

Rollback is layered. Stop at the layer that matches the problem; the model,
the proxy, and the public route are independent.

## 1. Close the public route only

On the VPS:

```bash
# revoke every caller (401 everywhere, engine unaffected)
sudo vi /etc/nginx/conf.d/ming-token.conf     # set the map body to default 0
sudo nginx -t && sudo systemctl reload nginx

# or remove the route entirely
sudo cp /etc/nginx/ai-proxy-locations.conf.bak-<stamp> /etc/nginx/ai-proxy-locations.conf
sudo nginx -t && sudo systemctl reload nginx
```

The Spark keeps serving on `:8101` for LAN callers.

## 2. Stop the streaming proxy

```bash
sudo systemctl disable --now ming-tts-proxy
```

Port 8101 closes; port 8094 stays available for local tests.

## 3. Stop the model

```bash
sudo systemctl disable --now ming-tts-warmup ming-tts
docker stop omni          # explicit stop; the restart policy will not revive it
```

Memory returns. The container and weights stay on disk, so restarting is one
command:

```bash
sudo systemctl enable --now ming-tts ming-tts-proxy
```

## 4. Remove the deployment

```bash
sudo systemctl disable --now ming-tts-proxy ming-tts-warmup ming-tts
sudo rm /etc/systemd/system/ming-tts.service \
        /etc/systemd/system/ming-tts-proxy.service \
        /etc/systemd/system/ming-tts-warmup.service
sudo systemctl daemon-reload
docker rm -f omni
rm -rf /home/$USER/omni-out/pr9198          # overlay
rm -rf /models/Ming-3.0-tts-tiny            # 17 GiB
```

Keep `omni-out/*.log` and any benchmark output until the replacement is
verified.

## 5. Revert to a previous TTS service

If a CosyVoice unit still exists on the same host:

```bash
sudo systemctl enable --now cosy-api
curl -s localhost:8003/healthz
```

Then repoint whatever proxy or gateway used to front it. The old public
prefixes (`/api/tts2`, `/api/cosy`) are not automatically restored by starting
CosyVoice; they were left pointing at their original upstreams. Do not assume
they work until you test them.

## 6. Revert an engine upgrade

If a future release replaces the overlay and fails:

```bash
docker exec omni pip install --no-deps vllm==0.32.0
# restore PYTHONPATH=/out/pr9198 in /out/serve_ming9198.sh
docker exec omni bash /out/serve_ming9198.sh
```

The overlay tree is independent of pip, so both can coexist while you compare.
