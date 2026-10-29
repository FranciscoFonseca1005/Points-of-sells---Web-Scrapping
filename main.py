"""Punto de entrada del extractor modular."""

from __future__ import annotations

import argparse
from pathlib import Path

import truststore

# Usa los certificados confiables de Windows antes de importar requests.
truststore.inject_into_ssl()

from src.exceptions import InputValidationError
from src.export import export_records, export_run_report
from src.input_reader import read_chain_requests
from src.pipeline import run_pipeline


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = PROJECT_ROOT / "input" / "chains.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extrae puntos de venta mediante adaptadores por cadena."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Ruta al archivo chains.csv.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Carpeta de salida para stores.csv y stores.xlsx.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Desactiva el respaldo de Chromium para páginas dinámicas.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Muestra Chromium cuando sea necesario para diagnóstico.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    try:
        chains = read_chain_requests(args.input)
    except InputValidationError as error:
        print(f"ERROR DE ENTRADA: {error}")
        return 2

    report = run_pipeline(
        chains,
        allow_browser=not args.no_browser,
        headless=not args.headed,
    )

    print("\nEXTRACCIÓN FINALIZADA")

    for success in report.successes:
        print(
            f"OK - {success.chain_name}: {success.store_count} sucursales "
            f"[{success.strategy}]"
        )

    for failure in report.failures:
        print(
            f"ERROR - {failure.chain_name} [{failure.strategy}]: "
            f"{failure.message}"
        )

    report_path = export_run_report(report, args.output_dir)
    print(f"\nReporte: {report_path}")

    if report.failures and not report.successes:
        print(
            "\nNo se modificaron los archivos de salida porque todas las "
            "cadenas fallaron."
        )
        return 1

    csv_path, xlsx_path = export_records(report.records, args.output_dir)

    print(f"\nFilas exportadas: {len(report.records)}")
    print(f"CSV: {csv_path}")
    print(f"Excel: {xlsx_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
