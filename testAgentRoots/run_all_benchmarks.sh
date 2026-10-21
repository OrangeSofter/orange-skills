#!/usr/bin/env bash
set -euo pipefail

roots_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

for root in "$roots_dir"/*/; do
    [[ -f "$root/benchmark_config.toml" ]] || continue
    (
        cd -- "$root"
        printf '\nRunning benchmark: %s\n' "$(basename "$PWD")"
        bash "$roots_dir/run_benchmark.sh" "$@"
    )
done
