#!/usr/bin/env python3
"""Process payroll entries from CSV and emit per-employee totals as JSON."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

TWOPLACES = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def parse_decimal(value: str) -> Decimal:
    return Decimal(value.strip())


def process_entries(csv_path: Path) -> dict:
    totals: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {
            "hours": Decimal("0"),
            "gross": Decimal("0"),
            "tax": Decimal("0"),
            "net": Decimal("0"),
        }
    )

    with csv_path.open("r", newline="", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        required = {"employee_id", "hours", "hourly_rate"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise ValueError(
                "CSV must include headers: employee_id,hours,hourly_rate (tax_rate optional)"
            )

        for row in reader:
            employee_id = row["employee_id"].strip()
            hours = parse_decimal(row["hours"])
            hourly_rate = parse_decimal(row["hourly_rate"])
            tax_rate = parse_decimal(row.get("tax_rate", "0") or "0")

            gross = hours * hourly_rate
            tax = gross * tax_rate
            net = gross - tax

            totals[employee_id]["hours"] += hours
            totals[employee_id]["gross"] += gross
            totals[employee_id]["tax"] += tax
            totals[employee_id]["net"] += net

    employees = []
    grand = {"hours": Decimal("0"), "gross": Decimal("0"), "tax": Decimal("0"), "net": Decimal("0")}

    for employee_id in sorted(totals.keys()):
        row = totals[employee_id]
        item = {
            "employee_id": employee_id,
            "hours": str(money(row["hours"])),
            "gross": str(money(row["gross"])),
            "tax": str(money(row["tax"])),
            "net": str(money(row["net"])),
        }
        employees.append(item)
        for key in grand:
            grand[key] += row[key]

    summary = {
        "employees": employees,
        "totals": {key: str(money(value)) for key, value in grand.items()},
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Process payroll entry CSV")
    parser.add_argument("entries_csv", type=Path, help="Path to payroll entries CSV")
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print output JSON"
    )
    args = parser.parse_args()

    summary = process_entries(args.entries_csv)
    if args.pretty:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
