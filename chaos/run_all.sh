#!/usr/bin/env bash
# Run both chaos experiments and print artifact paths.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate

echo ">>> Chaos A: concurrency overbooking"
python chaos/chaos_a_concurrency.py || true

echo
echo ">>> Chaos B: naive unique_together"
python chaos/chaos_b_unique_together.py || true

echo
echo "Artifacts:"
ls -la chaos/artifacts/
