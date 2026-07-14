"""Prototipo de extracción para Droguería Alemana.

Este script valida la estrategia de extracción con una sola combinación:
Santander - Bucaramanga. Todavía no recorre todo Colombia.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from playwright.sync_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_PATH = PROJECT_ROOT / "input" / "chains.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"

TARGET_CHAIN = "DROGERIA ALEMANA"
STORE_LOCATOR_URL = "https://www.tudrogueriavirtual.com/tiendas"
CHAIN_KEYWORD = "ALEMANA"

STORE_NAME_SELECTOR = ".unidrogas-store-locator-0-x-storeName"
STORE_ADDRESS_SELECTOR = ".unidrogas-store-locator-0-x-storeDirection"

OUTPUT_COLUMNS = [
    "chain_name",
    "url",
    "point_of_sale",
    "address_text",
    "address_link",
    "latitude",
    "longitude",
]


@dataclass(frozen=True)
class ChainConfig:
    """Configuración de una cadena tomada del archivo de entrada."""

    chain_name: str
    url: str


def clean_text(value: object) -> str:
    """Aplica únicamente limpieza básica de espacios y saltos de línea."""

    if value is None:
        return ""

    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_key(value: object) -> str:
    """Normaliza texto solo para búsquedas y comparación de duplicados."""

    text = clean_text(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.casefold()


def load_chain_config(
    input_path: Path,
    target_chain: str = TARGET_CHAIN,
) -> ChainConfig:
    """Lee la configuración de Droguería Alemana desde ``chains.csv``."""

    if not input_path.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de entrada: {input_path}"
        )

    chains = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    required_columns = {"chain_name", "url"}
    missing_columns = required_columns.difference(chains.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Faltan columnas en chains.csv: {missing}")

    target_key = normalize_key(target_chain)
    matches = chains[
        chains["chain_name"].map(normalize_key).eq(target_key)
    ]

    if matches.empty:
        raise ValueError(
            f"No se encontró la cadena '{target_chain}' en {input_path}"
        )

    if len(matches) > 1:
        raise ValueError(
            f"La cadena '{target_chain}' aparece más de una vez en {input_path}"
        )

    row = matches.iloc[0]
    chain_name = clean_text(row["chain_name"])
    url = clean_text(row["url"])

    if not chain_name or not url:
        raise ValueError("chain_name y url no pueden estar vacíos")

    return ChainConfig(chain_name=chain_name, url=url)


def wait_for_city_option(page: Page, city: str) -> None:
    """Espera hasta que el sitio cargue la ciudad solicitada."""

    page.wait_for_function(
        """
        city => {
            const selects = document.querySelectorAll('select');
            const citySelect = selects[1];

            if (!citySelect) {
                return false;
            }

            return Array.from(citySelect.options).some(
                option => option.textContent.trim() === city
            );
        }
        """,
        arg=city,
        timeout=30_000,
    )


def extract_city_stores(
    page: Page,
    chain: ChainConfig,
    department: str,
    city: str,
) -> tuple[pd.DataFrame, list[str]]:
    """Extrae las sucursales visibles para un departamento y una ciudad."""

    department = clean_text(department).upper()
    city = clean_text(city).upper()

    page.goto(
        STORE_LOCATOR_URL,
        wait_until="domcontentloaded",
        timeout=60_000,
    )

    page.wait_for_function(
        "document.querySelectorAll('select').length === 2",
        timeout=60_000,
    )

    selects = page.locator("select")

    if selects.count() != 2:
        raise RuntimeError(
            "La estructura del localizador cambió: no se encontraron "
            "los dos filtros esperados."
        )

    selects.nth(0).select_option(label=department)
    wait_for_city_option(page, city)

    selects = page.locator("select")
    selects.nth(1).select_option(label=city)

    page.wait_for_selector(
        STORE_NAME_SELECTOR,
        state="attached",
        timeout=30_000,
    )

    names = page.locator(STORE_NAME_SELECTOR).all_text_contents()
    addresses = page.locator(STORE_ADDRESS_SELECTOR).all_text_contents()

    if len(names) != len(addresses):
        raise RuntimeError(
            "La cantidad de nombres no coincide con la cantidad de "
            "direcciones. Es necesario revisar la página."
        )

    records: list[dict[str, object]] = []
    excluded_names: list[str] = []
    seen: set[tuple[str, str]] = set()

    for raw_name, raw_address in zip(names, addresses, strict=True):
        point_of_sale = clean_text(raw_name)
        address_text = clean_text(raw_address)

        if CHAIN_KEYWORD not in point_of_sale.upper():
            excluded_names.append(point_of_sale)
            continue

        duplicate_key = (
            normalize_key(point_of_sale),
            normalize_key(address_text),
        )

        if duplicate_key in seen:
            continue

        seen.add(duplicate_key)
        records.append(
            {
                "chain_name": chain.chain_name,
                "url": chain.url,
                "point_of_sale": point_of_sale,
                "address_text": address_text,
                "address_link": "",
                "latitude": "",
                "longitude": "",
            }
        )

    stores = pd.DataFrame(records, columns=OUTPUT_COLUMNS)

    if stores.empty:
        raise RuntimeError(
            f"No se encontraron sucursales de {chain.chain_name} "
            f"en {department} - {city}."
        )

    return stores, excluded_names


def validate_output(stores: pd.DataFrame) -> None:
    """Comprueba el esquema mínimo antes de exportar."""

    if stores.columns.tolist() != OUTPUT_COLUMNS:
        raise ValueError("La salida no contiene las siete columnas requeridas")

    if stores["point_of_sale"].eq("").any():
        raise ValueError("Existen registros sin nombre de punto de venta")

    if stores.duplicated(
        subset=["chain_name", "point_of_sale", "address_text"]
    ).any():
        raise ValueError("La salida contiene duplicados evidentes")


def export_results(stores: pd.DataFrame, output_dir: Path) -> tuple[Path, Path]:
    """Exporta la muestra en CSV y Excel."""

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "stores_drogueria_alemana_bucaramanga.csv"
    xlsx_path = output_dir / "stores_drogueria_alemana_bucaramanga.xlsx"

    stores.to_csv(csv_path, index=False, encoding="utf-8-sig")
    stores.to_excel(xlsx_path, index=False)

    return csv_path, xlsx_path


def parse_arguments() -> argparse.Namespace:
    """Define los argumentos disponibles para la prueba controlada."""

    parser = argparse.ArgumentParser(
        description=(
            "Extrae una muestra de Droguería Alemana para una ciudad."
        )
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
        help="Carpeta donde se guardarán los resultados.",
    )
    parser.add_argument(
        "--department",
        default="SANTANDER",
        help="Departamento que se seleccionará en el localizador.",
    )
    parser.add_argument(
        "--city",
        default="BUCARAMANGA",
        help="Ciudad que se seleccionará en el localizador.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Muestra la ventana del navegador durante la extracción.",
    )
    return parser.parse_args()


def main() -> None:
    """Ejecuta el prototipo completo."""

    args = parse_arguments()
    chain = load_chain_config(args.input)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            context = browser.new_context(locale="es-CO")
            page = context.new_page()

            try:
                stores, excluded_names = extract_city_stores(
                    page=page,
                    chain=chain,
                    department=args.department,
                    city=args.city,
                )
            finally:
                context.close()
                browser.close()
    except PlaywrightTimeoutError as error:
        raise RuntimeError(
            "El localizador no terminó de cargar dentro del tiempo esperado. "
            "Comprueba tu conexión y vuelve a ejecutar el prototipo."
        ) from error

    validate_output(stores)
    csv_path, xlsx_path = export_results(stores, args.output_dir)

    print(f"Sucursales extraídas: {len(stores)}")
    print(f"Registros de otras marcas excluidos: {len(excluded_names)}")

    if excluded_names:
        print("Excluidos: " + ", ".join(excluded_names))

    print(f"CSV: {csv_path}")
    print(f"Excel: {xlsx_path}")


if __name__ == "__main__":
    main()
