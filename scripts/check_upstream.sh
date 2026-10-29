#!/bin/bash
# Read-only check of upstream versions. Changes nothing.
set -euo pipefail

echo "pinned in this repo: overlay c0b1351e  vllm 0.32.0  weights 8cf79a89"

PY=$(command -v python3 || command -v python || true)

if command -v gh >/dev/null 2>&1; then
  rel=$(gh api repos/vllm-project/vllm-omni/releases/latest \
        --jq '.tag_name + "  " + .published_at' 2>/dev/null || true)
  echo "vllm-omni release : ${rel:-unavailable}"
  pr=$(gh api repos/vllm-project/vllm-omni/pulls/9198 \
       --jq '"state=" + .state + "  draft=" + (.draft|tostring) + "  head=" + .head.sha' 2>/dev/null || true)
  echo "PR #9198          : ${pr:-unavailable}"
else
  echo "vllm-omni release : install gh to query"
  echo "PR #9198          : install gh to query"
fi

if [ -n "$PY" ]; then
  pypi_json=$(curl -s -m 20 https://pypi.org/pypi/vllm-omni/json || true)
  pypi=$(printf '%s' "$pypi_json" \
    | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["info"]["version"])' 2>/dev/null || true)
else
  pypi="need python3"
fi
echo "PyPI vllm-omni    : ${pypi:-unavailable}"

if [ -n "$PY" ]; then
  ms_json=$(curl -s -m 30 \
    "https://modelscope.cn/api/v1/models/inclusionAI/Ming-3.0-tts-tiny/repo/files?Revision=master" || true)
  weights=$(printf '%s' "$ms_json" | "$PY" -c '
import json, sys
files = json.load(sys.stdin)["Data"]["Files"]
head = max(files, key=lambda f: f.get("CommittedDate", 0))
print(head["Revision"][:8], head.get("CommitMessage", ""))
' 2>/dev/null || true)
else
  weights="need python3"
fi
echo "weights head      : ${weights:-unavailable}"
