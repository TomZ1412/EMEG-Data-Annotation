#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-10000}"
ANNO_PROFILE="${ANNO_PROFILE:-not_used}"

export ANNO_PROFILE
python -m uvicorn main:app --host "$HOST" --port "$PORT"
