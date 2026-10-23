#!/bin/bash
# Install the public /api/ming/v1 route on a Debian/Ubuntu nginx host.
# Usage: sudo ./install.sh [/etc/nginx/ai-proxy-locations.conf]
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
LOC=${1:-/etc/nginx/ai-proxy-locations.conf}
TOKEN_FILE=/etc/nginx/conf.d/ming-token.conf

if grep -q '<DGX_TAILSCALE_IP>' "$HERE/ming-upstream.conf"; then
  echo "edit ming-upstream.conf first: replace <DGX_TAILSCALE_IP>" >&2
  exit 1
fi

if grep -q 'REPLACE_WITH_A_RANDOM_TOKEN' "$HERE/ming-token.conf.example"; then
  echo "edit ming-token.conf.example first: replace the placeholder token" >&2
  exit 1
fi

install -m 644 "$HERE/ming-upstream.conf" /etc/nginx/conf.d/ming-upstream.conf
install -m 644 "$HERE/ming-token.conf.example" "$TOKEN_FILE"

if grep -q 'api/ming/v1' "$LOC"; then
  echo "location already present in $LOC"
else
  cp -a "$LOC" "$LOC.bak-$(date +%Y%m%d-%H%M%S)"
  cat "$HERE/ming-location.conf" >> "$LOC"
  echo "appended location block to $LOC"
fi

nginx -t
systemctl reload nginx
echo "reloaded. Test: curl -H 'Authorization: Bearer <token>' https://<your-domain>/api/ming/v1/models"
