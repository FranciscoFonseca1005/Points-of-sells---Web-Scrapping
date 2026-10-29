"""Extractor nacional de puntos de venta de Droguería Alemana.

Recorre los departamentos y ciudades publicados en el localizador de tiendas.
El prototipo validado de Bucaramanga permanece separado y sin modificaciones.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from playwright.sync_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from drogueria_alemana import (
    CHAIN_KEYWORD,
    DEFAULT_INPUT_PATH,
    DEFAULT_OUTPUT_DIR,
    OUTPUT_COLUMNS,
    STORE_ADDRESS_SELECTOR,
    STORE_LOCATOR_URL,
    STORE_NAME_SELECTOR,
    ChainConfig,
    clean_text,
    load_chain_config,
    normalize_key,
    validate_output,
)


DEFAULT_TIMEOUT_MS = 30_000


@dataclass
class ExtractionResult:
    """Resultado y resumen del recorrido nacional."""

    stores: pd.DataFrame
    processed_cities: int
    failed_locations: list[str]
    excluded_names: set[str]


def wait_for_locator(page: Page) -> None:
    """Espera a que aparezcan los filtros del localizador."""

    page.wait_for_function(
        "document.querySelectorAll('select').length === 2",
        timeout=60_000,
    )

    if page.locator("select").count() != 2:
        raise RuntimeError(
            "La estructura del localizador cambió: no se encontraron "
            "los dos filtros esperados."
        )


def get_select_options(page: Page, select_index: int) -> list[str]:
    """Obtiene las opciones válidas de un selector."""

    selects = page.locator("select")

    if selects.count() != 2:
        raise RuntimeError("No están disponibles los dos filtros esperados")

    options = selects.nth(select_index).locator("option").evaluate_all(
        """
        options => options
            .filter(option => option.value && !option.disabled)
            .map(option => option.textContent.trim())
        """
    )

    return [clean_text(option) for option in options if clean_text(option)]


def wait_for_city_options(page: Page, department: str) -> None:
    """Espera la actualización de ciudades del departamento seleccionado."""

    page.wait_for_function(
        """
        department => {
            const selects = document.querySelectorAll('select');

            if (selects.length !== 2) {
                return false;
            }

            const selectedDepartment = selects[0].value;
            const cities = Array.from(selects[1].options).filter(
                option => option.value && !option.disabled
            );

            return selectedDepartment === department && cities.length > 0;
        }
        """,
        arg=department,
        timeout=DEFAULT_TIMEOUT_MS,
    )


def get_store_signature(page: Page) -> str:
    """Crea una firma del resultado visible para detectar su actualización."""

    return page.evaluate(
        """
        selectors => {
            const names = Array.from(
                document.querySelectorAll(selectors.name)
            ).map(element => element.textContent.trim());

            const addresses = Array.from(
                document.querySelectorAll(selectors.address)
            ).map(element => element.textContent.trim());

            return names.join('\u241e')
                + '\u241f'
                + addresses.join('\u241e');
        }
        """,
        {
            "name": STORE_NAME_SELECTOR,
            "address": STORE_ADDRESS_SELECTOR,
        },
    )


def wait_for_store_update(
    page: Page,
    city: str,
    previous_signature: str,
) -> None:
    """Espera a que los establecimientos correspondan a la nueva ciudad."""

    page.wait_for_function(
        """
        args => {
            const selects = document.querySelectorAll('select');

            if (selects.length !== 2 || selects[1].value !== args.city) {
                return false;
            }

            const names = Array.from(
                document.querySelectorAll(args.nameSelector)
            ).map(element => element.textContent.trim());

            const addresses = Array.from(
                document.querySelectorAll(args.addressSelector)
            ).map(element => element.textContent.trim());

            if (names.length === 0 || names.length !== addresses.length) {
                return false;
            }

            const signature = names.join('\u241e')
                + '\u241f'
                + addresses.join('\u241e');

            return signature !== args.previousSignature;
        }
        """,
        arg={
            "city": city,
            "nameSelector": STORE_NAME_SELECTOR,
            "addressSelector": STORE_ADDRESS_SELECTOR,
            "previousSignature": previous_signature,
        },
        timeout=DEFAULT_TIMEOUT_MS,
    )


def extract_visible_store_pairs(page: Page) -> list[tuple[str, str]]:
    """Extrae los pares de nombre y dirección actualmente publicados."""

    names = page.locator(STORE_NAME_SELECTOR).all_text_contents()
    addresses = page.locator(STORE_ADDRESS_SELECTOR).all_text_contents()

    if len(names) != len(addresses):
        raise RuntimeError(
            "La cantidad de nombres no coincide con la cantidad de "
            "direcciones."
        )

    return [
        (clean_text(name), clean_text(address))
        for name, address in zip(names, addresses, strict=True)
    ]


def create_store_record(
    chain: ChainConfig,
    point_of_sale: str,
    address_text: str,
) -> dict[str, str]:
    """Crea un registro con las siete columnas requeridas."""

    return {
        "chain_name": chain.chain_name,
        "url": chain.url,
        "point_of_sale": point_of_sale,
        "address_text": address_text,
        "address_link": "",
        "latitude": "",
        "longitude": "",
    }


def select_departments(
    available_departments: list[str],
    only_department: str | None,
) -> list[str]:
    """Aplica el filtro opcional para una prueba departamental."""

    if only_department is None:
        return available_departments

    requested_key = normalize_key(only_department)
    selected = [
        department
        for department in available_departments
        if normalize_key(department) == requested_key
    ]

    if not selected:
        raise ValueError(
            f"El departamento '{only_department}' no aparece en el localizador"
        )

    return selected


def extract_all_stores(
    page: Page,
    chain: ChainConfig,
    only_department: str | None = None,
    max_cities: int | None = None,
) -> ExtractionResult:
    """Recorre todos los departamentos y ciudades disponibles."""

    page.goto(
        STORE_LOCATOR_URL,
        wait_until="domcontentloaded",
        timeout=60_000,
    )
    wait_for_locator(page)

    available_departments = get_select_options(page, select_index=0)
    departments = select_departments(
        available_departments,
        only_department,
    )

    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    excluded_names: set[str] = set()
    failed_locations: list[str] = []
    processed_cities = 0

    for department_index, department in enumerate(departments, start=1):
        print(
            f"[{department_index}/{len(departments)}] "
            f"Departamento: {department}"
        )

        try:
            department_select = page.locator("select").nth(0)
            department_select.select_option(label=department)
            wait_for_city_options(page, department)
            cities = get_select_options(page, select_index=1)
        except (PlaywrightTimeoutError, RuntimeError) as error:
            message = f"{department}: {error}"
            failed_locations.append(message)
            print(f"  ERROR: {message}")
            continue

        if max_cities is not None:
            cities = cities[:max_cities]

        print(f"  Ciudades disponibles: {len(cities)}")

        for city_index, city in enumerate(cities, start=1):
            location = f"{department} - {city}"

            try:
                previous_signature = get_store_signature(page)
                city_select = page.locator("select").nth(1)
                city_select.select_option(label=city)
                wait_for_store_update(page, city, previous_signature)
                store_pairs = extract_visible_store_pairs(page)
            except (PlaywrightTimeoutError, RuntimeError) as error:
                message = f"{location}: {error}"
                failed_locations.append(message)
                print(
                    f"    [{city_index}/{len(cities)}] "
                    f"{city}: ERROR"
                )
                continue

            processed_cities += 1
            chain_store_count = 0

            for point_of_sale, address_text in store_pairs:
                if CHAIN_KEYWORD not in point_of_sale.upper():
                    if point_of_sale:
                        excluded_names.add(point_of_sale)
                    continue

                duplicate_key = (
                    normalize_key(point_of_sale),
                    normalize_key(address_text),
                )

                if duplicate_key in seen:
                    continue

                seen.add(duplicate_key)
                records.append(
                    create_store_record(
                        chain=chain,
                        point_of_sale=point_of_sale,
                        address_text=address_text,
                    )
                )
                chain_store_count += 1

            print(
                f"    [{city_index}/{len(cities)}] {city}: "
                f"{chain_store_count} nuevas sucursales"
            )

    stores = pd.DataFrame(records, columns=OUTPUT_COLUMNS)

    if stores.empty:
        raise RuntimeError(
            "El recorrido terminó sin sucursales de Droguería Alemana"
        )

    return ExtractionResult(
        stores=stores,
        processed_cities=processed_cities,
        failed_locations=failed_locations,
        excluded_names=excluded_names,
    )


def export_results(
    stores: pd.DataFrame,
    output_dir: Path,
    partial_run: bool,
) -> tuple[Path, Path]:
    """Exporta el resultado nacional o la prueba parcial."""

    output_dir.mkdir(parents=True, exist_ok=True)

    if partial_run:
        filename = "stores_drogueria_alemana_prueba"
    else:
        filename = "stores_drogueria_alemana_colombia"

    csv_path = output_dir / f"{filename}.csv"
    xlsx_path = output_dir / f"{filename}.xlsx"

    stores.to_csv(csv_path, index=False, encoding="utf-8-sig")
    stores.to_excel(xlsx_path, index=False)

    return csv_path, xlsx_path


def parse_arguments() -> argparse.Namespace:
    """Define los argumentos del extractor nacional."""

    parser = argparse.ArgumentParser(
        description=(
            "Recorre el localizador nacional de Droguería Alemana."
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
        "--only-department",
        help="Procesa únicamente el departamento indicado.",
    )
    parser.add_argument(
        "--max-cities",
        type=int,
        help="Limita las ciudades por departamento para pruebas.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Muestra la ventana del navegador durante la extracción.",
    )
    args = parser.parse_args()

    if args.max_cities is not None and args.max_cities < 1:
        parser.error("--max-cities debe ser mayor que cero")

    return args


def main() -> None:
    """Ejecuta el recorrido y exporta los resultados."""

    args = parse_arguments()
    chain = load_chain_config(args.input)
    partial_run = bool(args.only_department or args.max_cities)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headed)
        context = browser.new_context(locale="es-CO")
        page = context.new_page()

        try:
            result = extract_all_stores(
                page=page,
                chain=chain,
                only_department=args.only_department,
                max_cities=args.max_cities,
            )
        finally:
            context.close()
            browser.close()

    validate_output(result.stores)
    csv_path, xlsx_path = export_results(
        stores=result.stores,
        output_dir=args.output_dir,
        partial_run=partial_run,
    )

    print("\nRECORRIDO FINALIZADO")
    print(f"Ciudades procesadas: {result.processed_cities}")
    print(f"Sucursales únicas: {len(result.stores)}")
    print(f"Otras marcas detectadas: {len(result.excluded_names)}")
    print(f"Ubicaciones con error: {len(result.failed_locations)}")

    if result.failed_locations:
        print("\nATENCIÓN: el resultado es parcial. Revisar:")

        for failed_location in result.failed_locations:
            print(f"- {failed_location}")

    print(f"\nCSV: {csv_path}")
    print(f"Excel: {xlsx_path}")


if __name__ == "__main__":
    main()
