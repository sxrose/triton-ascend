#!/usr/bin/env python3
"""Convert recursively discovered comptime.json files into an XLSX table."""

import argparse
import json
from pathlib import Path
from typing import Any


def flatten_record(value: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten nested dictionaries using underscores between key components."""
    flattened: dict[str, Any] = {}
    for key, item in value.items():
        name = f"{prefix}_{key}" if prefix else str(key)
        if isinstance(item, dict):
            flattened.update(flatten_record(item, name))
        elif isinstance(item, (list, tuple)):
            # Excel cells do not have a native list type.
            flattened[name] = json.dumps(item, ensure_ascii=True)
        else:
            flattened[name] = item
    return flattened


def load_records(input_dir: Path) -> list[dict[str, Any]]:
    """Load and flatten every comptime.json below input_dir."""
    records = []
    for source_path in sorted(input_dir.rglob("comptime.json")):
        try:
            with source_path.open(encoding="utf-8") as source_file:
                data = json.load(source_file)
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"failed to read {source_path}: {error}") from error

        if not isinstance(data, dict):
            raise ValueError(f"expected a JSON object in {source_path}")

        record = flatten_record(data)
        record["source_file"] = str(source_path)
        records.append(record)
    return records


def write_xlsx(records: list[dict[str, Any]], output_path: Path) -> None:
    try:
        import pandas as pd
    except ImportError as error:
        raise RuntimeError("writing XLSX requires pandas") from error

    columns = sorted({column for record in records for column in record})
    if "source_file" in columns:
        columns.remove("source_file")
        columns.append("source_file")

    frame = pd.DataFrame(records, columns=columns)
    try:
        frame.to_excel(output_path, index=False)
    except ImportError as error:
        raise RuntimeError("writing XLSX requires an Excel engine such as openpyxl") from error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path, help="Directory to search recursively")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output XLSX path (default: INPUT_DIR/comptime.xlsx)",
    )
    args = parser.parse_args()

    input_dir = args.input_dir.expanduser().resolve()
    if not input_dir.is_dir():
        parser.error(f"input directory does not exist or is not a directory: {input_dir}")

    output_path = (args.output or input_dir / "comptime.xlsx").expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = load_records(input_dir)
    write_xlsx(records, output_path)
    print(f"Wrote {len(records)} records from comptime.json files to {output_path}")


if __name__ == "__main__":
    main()
