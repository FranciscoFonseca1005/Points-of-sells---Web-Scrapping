"""Validación del contrato de salida y deduplicación conservadora."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from src.constants import OUTPUT_COLUMNS, TEXT_OUTPUT_COLUMNS
from src.exceptions import OutputValidationError
from src.normalization import clean_text, normalize_identifier


StoreRecord = dict[str, Any]


def validate_record(record: Mapping[str, Any]) -> StoreRecord:
    """Valida las siete llaves y limpia únicamente los campos de texto."""

    if set(record) != set(OUTPUT_COLUMNS):
        missing = sorted(set(OUTPUT_COLUMNS) - set(record))
        extra = sorted(set(record) - set(OUTPUT_COLUMNS))
        raise OutputValidationError(
            f"Fila inválida. Faltantes: {missing}. Adicionales: {extra}."
        )

    validated = {column: record[column] for column in OUTPUT_COLUMNS}

    for column in TEXT_OUTPUT_COLUMNS:
        validated[column] = clean_text(validated[column])

    for column, minimum, maximum in (
        ("latitude", -90.0, 90.0),
        ("longitude", -180.0, 180.0),
    ):
        value = validated[column]

        if value == "":
            continue

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise OutputValidationError(
                f"{column} debe ser numérica o estar vacía: {value!r}"
            )

        if not minimum <= float(value) <= maximum:
            raise OutputValidationError(
                f"{column} está fuera de rango: {value!r}"
            )

    return validated


def validate_records(records: Iterable[Mapping[str, Any]]) -> list[StoreRecord]:
    """Valida todas las filas entregadas por un adaptador."""

    return [validate_record(record) for record in records]


def _deduplication_key(record: Mapping[str, Any]) -> tuple[Any, ...] | None:
    chain_name = normalize_identifier(record["chain_name"])
    source_url = clean_text(record["url"])
    point_of_sale = normalize_identifier(record["point_of_sale"])
    address_text = normalize_identifier(record["address_text"])
    address_link = clean_text(record["address_link"])
    latitude = record["latitude"]
    longitude = record["longitude"]

    if address_link:
        return (chain_name, source_url, "link", address_link)

    if point_of_sale and address_text:
        return (
            chain_name,
            source_url,
            "name_address",
            point_of_sale,
            address_text,
        )

    if point_of_sale and latitude != "" and longitude != "":
        return (
            chain_name,
            source_url,
            "name_coordinates",
            point_of_sale,
            float(latitude),
            float(longitude),
        )

    return None


def deduplicate_evident(records: Iterable[StoreRecord]) -> list[StoreRecord]:
    """Elimina solo duplicados con enlace o identidad evidente coincidente."""

    unique_records: list[StoreRecord] = []
    seen: set[tuple[Any, ...]] = set()

    for record in records:
        key = _deduplication_key(record)

        if key is not None and key in seen:
            continue

        if key is not None:
            seen.add(key)

        unique_records.append(record)

    return unique_records
