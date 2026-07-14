"""Limpieza mínima sin completar ni inferir datos."""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Any


WHITESPACE_PATTERN = re.compile(r"\s+")


def clean_text(value: Any) -> str:
    """Limpia espacios y saltos de línea; los faltantes quedan vacíos."""

    if value is None:
        return ""

    return WHITESPACE_PATTERN.sub(" ", str(value)).strip()


def normalize_identifier(value: Any) -> str:
    """Normaliza texto solo para comparar nombres y duplicados."""

    text = unicodedata.normalize("NFKD", clean_text(value))
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    return text.casefold()


def normalize_coordinate(
    value: Any,
    minimum: float,
    maximum: float,
) -> float | str:
    """Devuelve una coordenada explícita válida o una celda vacía."""

    if value is None or isinstance(value, bool):
        return ""

    text = clean_text(value)

    if not text:
        return ""

    try:
        coordinate = float(text)
    except (TypeError, ValueError):
        return ""

    if not math.isfinite(coordinate):
        return ""

    if not minimum <= coordinate <= maximum:
        return ""

    return coordinate
