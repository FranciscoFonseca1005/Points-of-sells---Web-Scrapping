"""Lectura y validación de input/chains.csv."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from src.constants import INPUT_COLUMNS
from src.exceptions import InputValidationError
from src.normalization import clean_text


@dataclass(frozen=True)
class ChainRequest:
    """Cadena y URL principal proporcionadas por el usuario."""

    chain_name: str
    url: str


def _validate_url(url: str, row_number: int) -> None:
    parsed = urlsplit(url)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise InputValidationError(
            f"La URL de la fila {row_number} no es HTTP o HTTPS: {url!r}"
        )


def read_chain_requests(path: Path) -> list[ChainRequest]:
    """Lee las cadenas y exige exactamente las dos columnas de entrada."""

    if not path.is_file():
        raise InputValidationError(f"No se encontró el archivo de entrada: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)

        if reader.fieldnames is None:
            raise InputValidationError("El archivo de entrada no tiene encabezados")

        headers = tuple(clean_text(header) for header in reader.fieldnames)

        if headers != INPUT_COLUMNS:
            expected = ",".join(INPUT_COLUMNS)
            found = ",".join(headers)
            raise InputValidationError(
                "El archivo debe tener exactamente estos encabezados y en este "
                f"orden: {expected}. Se encontró: {found}"
            )

        chains: list[ChainRequest] = []

        for row_number, row in enumerate(reader, start=2):
            chain_name = clean_text(row.get("chain_name"))
            url = clean_text(row.get("url"))

            if not chain_name and not url:
                continue

            if not chain_name:
                raise InputValidationError(
                    f"Falta chain_name en la fila {row_number}"
                )

            if not url:
                raise InputValidationError(f"Falta url en la fila {row_number}")

            _validate_url(url, row_number)
            chains.append(ChainRequest(chain_name=chain_name, url=url))

    if not chains:
        raise InputValidationError("El archivo de entrada no contiene cadenas")

    return chains
