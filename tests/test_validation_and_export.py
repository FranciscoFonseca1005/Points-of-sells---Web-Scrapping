from pathlib import Path

import pandas as pd

from src.constants import OUTPUT_COLUMNS
from src.export import REPORT_COLUMNS, export_records, export_run_report
from src.pipeline import ChainFailure, ChainSuccess, RunReport
from src.validation import deduplicate_evident, validate_records


def make_record(name: str, address: str) -> dict[str, object]:
    return {
        "chain_name": "DROGERIA ALEMANA",
        "url": "https://www.tudrogueriavirtual.com/",
        "point_of_sale": name,
        "address_text": address,
        "address_link": "",
        "latitude": 7.1,
        "longitude": -73.1,
    }


def test_deduplicates_only_evident_matches() -> None:
    records = validate_records(
        [
            make_record("ALEMANA 01", "CARRERA 1"),
            make_record(" alemana 01 ", " CARRERA 1 "),
            make_record("ALEMANA 02", "CARRERA 1"),
        ]
    )

    unique = deduplicate_evident(records)

    assert len(unique) == 2
    assert [record["point_of_sale"] for record in unique] == [
        "ALEMANA 01",
        "ALEMANA 02",
    ]


def test_exports_exact_columns_and_blank_cells(tmp_path: Path) -> None:
    record = make_record("ALEMANA 01", "")
    record["address_link"] = ""
    record["latitude"] = ""
    record["longitude"] = ""

    csv_path, xlsx_path = export_records([record], tmp_path)
    csv_frame = pd.read_csv(csv_path, keep_default_na=False)
    xlsx_frame = pd.read_excel(xlsx_path, keep_default_na=False)

    assert list(csv_frame.columns) == list(OUTPUT_COLUMNS)
    assert list(xlsx_frame.columns) == list(OUTPUT_COLUMNS)
    assert csv_frame.loc[0, "address_text"] == ""
    assert csv_frame.loc[0, "latitude"] == ""


def test_exports_separate_run_report(tmp_path: Path) -> None:
    report = RunReport(
        records=[],
        successes=[
            ChainSuccess(
                chain_name="CADENA OK",
                url="https://example.com/ok",
                store_count=3,
                strategy="json_ld",
            )
        ],
        failures=[
            ChainFailure(
                chain_name="CADENA ERROR",
                url="https://example.com/error",
                message="Sin datos",
                strategy="generico",
            )
        ],
    )

    report_path = export_run_report(report, tmp_path)
    frame = pd.read_csv(report_path, keep_default_na=False)

    assert list(frame.columns) == list(REPORT_COLUMNS)
    assert frame["status"].tolist() == ["OK", "ERROR"]
    assert frame["store_count"].tolist() == [3, 0]
