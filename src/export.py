"""Exportación de las siete columnas contractuales."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from src.constants import OUTPUT_COLUMNS


REPORT_COLUMNS = (
    "chain_name",
    "url",
    "status",
    "strategy",
    "store_count",
    "message",
)


def records_to_frame(records: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    """Construye un DataFrame con orden de columnas estable."""

    return pd.DataFrame(list(records), columns=OUTPUT_COLUMNS).fillna("")


def export_records(
    records: Iterable[Mapping[str, Any]],
    output_dir: Path,
) -> tuple[Path, Path]:
    """Genera stores.csv y stores.xlsx."""

    output_dir.mkdir(parents=True, exist_ok=True)
    frame = records_to_frame(records)
    csv_path = output_dir / "stores.csv"
    xlsx_path = output_dir / "stores.xlsx"

    frame.to_csv(csv_path, index=False, encoding="utf-8-sig", na_rep="")
    frame.to_excel(xlsx_path, index=False)

    return csv_path, xlsx_path


def export_run_report(report: Any, output_dir: Path) -> Path:
    """Exporta el diagnóstico por cadena sin alterar ``stores``."""

    rows: list[dict[str, Any]] = []

    for success in report.successes:
        rows.append(
            {
                "chain_name": success.chain_name,
                "url": success.url,
                "status": "OK",
                "strategy": success.strategy,
                "store_count": success.store_count,
                "message": "",
            }
        )

    for failure in report.failures:
        rows.append(
            {
                "chain_name": failure.chain_name,
                "url": failure.url,
                "status": "ERROR",
                "strategy": failure.strategy,
                "store_count": 0,
                "message": failure.message,
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "extraction_report.csv"
    pd.DataFrame(rows, columns=REPORT_COLUMNS).to_csv(
        report_path,
        index=False,
        encoding="utf-8-sig",
    )
    return report_path
