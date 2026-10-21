#!/usr/bin/env bash
set -euo pipefail
benchmark_script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$benchmark_script_dir/.env" ]]; then
  set -a
  source "$benchmark_script_dir/.env"
  set +a
fi
if [[ $# -eq 0 ]]; then set -- 1; fi
python3 ../../benchmark/benchmark.py "$@"
