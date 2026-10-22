#!/usr/bin/env bash
# Usage: bash scripts/render.sh [out.mp4]   (run from finance-shorts/)
# Set BROWSER_EXECUTABLE if Remotion can't find Chrome (e.g. headless_shell in sandboxes).
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-out/finance-short.mp4}"
mkdir -p "$(dirname "$OUT")"
ARGS=()
[ -n "${BROWSER_EXECUTABLE:-}" ] && ARGS+=(--browser-executable="$BROWSER_EXECUTABLE")
npx remotion render src/index.ts FinanceShort "$OUT" "${ARGS[@]}"
