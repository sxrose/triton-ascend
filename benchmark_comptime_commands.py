#!/usr/bin/env python3
"""Benchmark compile commands from recursively discovered comptime.json files."""

import argparse
import json
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any


def remove_outliers(samples: list[float]) -> list[float]:
    """Discard timings whose MAD-based modified Z-score exceeds 3.5."""
    median = statistics.median(samples)
    deviations = [abs(sample - median) for sample in samples]
    median_absolute_deviation = statistics.median(deviations)
    if median_absolute_deviation == 0:
        return samples

    return [
        sample for sample in samples
        if 0.6745 * abs(sample - median) / median_absolute_deviation <= 3.5
    ]


def benchmark_command(command: str, runs: int) -> float:
    """Run command repeatedly and return the mean after removing outliers."""
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        subprocess.run(command, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        samples.append(time.perf_counter() - start)

    filtered_samples = remove_outliers(samples)
    return statistics.mean(filtered_samples)


def load_benchmark_records(input_dir: Path, runs: int) -> list[dict[str, Any]]:
    """Load comptime records and benchmark each recorded compile command."""
    records = []
    for source_path in sorted(input_dir.rglob("comptime.json")):
        try:
            with source_path.open(encoding="utf-8") as source_file:
                data = json.load(source_file)
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"failed to read {source_path}: {error}") from error

        if not isinstance(data, dict):
            raise ValueError(f"expected a JSON object in {source_path}")

        signature = data.get("constexpr_signature")
        command = data.get("compile_command")
        if not isinstance(signature, str) or not isinstance(command, str):
            raise ValueError(f"expected string constexpr_signature and compile_command in {source_path}")

        try:
            average_time = benchmark_command(command, runs)
        except subprocess.CalledProcessError as error:
            raise RuntimeError(
                f"compile command failed for {source_path} with exit code {error.returncode}: {command}\n{error.stderr}"
            ) from error

        records.append({
            "json_source": str(source_path),
            "kernel_signature": signature,
            "command": command,
            "command_average_time": average_time,
        })
    return records


def write_xlsx(records: list[dict[str, Any]], output_path: Path) -> None:
    try:
        import pandas as pd
    except ImportError as error:
        raise RuntimeError("writing XLSX requires pandas") from error

    try:
        pd.DataFrame(records, columns=[
            "json_source",
            "kernel_signature",
            "command",
            "command_average_time",
        ]).to_excel(output_path, index=False)
    except ImportError as error:
        raise RuntimeError("writing XLSX requires an Excel engine such as openpyxl") from error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path, help="Directory to search recursively")
    parser.add_argument("--runs", type=int, default=30, help="Command executions per record (default: 30)")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output XLSX path (default: INPUT_DIR/comptime_benchmarks.xlsx)",
    )
    args = parser.parse_args()

    input_dir = args.input_dir.expanduser().resolve()
    if not input_dir.is_dir():
        parser.error(f"input directory does not exist or is not a directory: {input_dir}")
    if args.runs < 1:
        parser.error("--runs must be at least 1")

    output_path = (args.output or input_dir / "comptime_benchmarks.xlsx").expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = load_benchmark_records(input_dir, args.runs)
    write_xlsx(records, output_path)
    print(f"Wrote {len(records)} benchmark records to {output_path}")


if __name__ == "__main__":
    main()
