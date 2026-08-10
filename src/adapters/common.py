"""Utilidades compartidas por adaptadores HTML y JSON."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from src.normalization import clean_text, normalize_coordinate, normalize_identifier
from src.validation import StoreRecord


ADDRESS_START_PATTERN = re.compile(
    r"\b(?:"
    r"calle|cl\.?|carrera|cra\.?|avenida|av\.?|"
    r"diagonal|transversal|autopista|kil[oó]metro|"
    r"circular|circunvalar|carretera"
    r")\b",
    flags=re.IGNORECASE,
)
COORDINATE_PAIR_PATTERN = re.compile(
    r"(?<!\d)(-?\d{1,2}(?:\.\d+)?)[,\s]+"
    r"(-?\d{1,3}(?:\.\d+)?)(?!\d)"
)
AT_COORDINATE_PATTERN = re.compile(
    r"@(-?\d{1,2}(?:\.\d+)?),(-?\d{1,3}(?:\.\d+)?)"
)
MAP_HOST_MARKERS = (
    "google.com",
    "maps.app.goo.gl",
    "goo.gl",
    "waze.com",
    "openstreetmap.org",
)


def make_record(
    *,
    chain_name: str,
    source_url: str,
    point_of_sale: Any,
    address_text: Any,
    address_link: Any = "",
    latitude: Any = "",
    longitude: Any = "",
) -> StoreRecord:
    """Construye una fila con las siete columnas contractuales."""

    return {
        "chain_name": chain_name,
        "url": source_url,
        "point_of_sale": clean_text(point_of_sale),
        "address_text": clean_text(address_text),
        "address_link": clean_text(address_link),
        "latitude": normalize_coordinate(latitude, -90.0, 90.0),
        "longitude": normalize_coordinate(longitude, -180.0, 180.0),
    }


def strip_address_label(value: Any) -> str:
    """Retira únicamente la etiqueta explícita ``Dirección``."""

    text = clean_text(value)
    return clean_text(
        re.sub(
            r"^\s*(?:📍\s*)?direcci[oó]n\s*:\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
    ).strip(" -–—")


def address_before_phone(value: Any) -> str:
    """Conserva la dirección publicada y excluye el teléfono adyacente."""

    text = strip_address_label(value)
    address = re.split(
        r"\s*(?:[-–—]\s*)?tel[eé]fono\s*:\s*",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return clean_text(address).strip(" -–—")


def is_map_url(url: str) -> bool:
    """Reconoce enlaces que la página presenta como mapas."""

    host = urlsplit(url).netloc.casefold()
    return any(marker in host for marker in MAP_HOST_MARKERS)


def coordinates_from_url(url: str) -> tuple[float | str, float | str]:
    """Lee coordenadas literales de un enlace sin geocodificarlo."""

    decoded = unquote(clean_text(url))
    match = AT_COORDINATE_PATTERN.search(decoded)

    if match is None:
        query = parse_qs(urlsplit(decoded).query)
        candidates: list[str] = []

        for key in ("q", "query", "destination", "ll", "center"):
            candidates.extend(query.get(key, []))

        for candidate in candidates:
            match = COORDINATE_PAIR_PATTERN.search(candidate)
            if match is not None:
                break

    if match is None:
        return "", ""

    latitude = normalize_coordinate(match.group(1), -90.0, 90.0)
    longitude = normalize_coordinate(match.group(2), -180.0, 180.0)

    if latitude == "" or longitude == "":
        return "", ""

    return latitude, longitude


def _map_links(container: Tag, base_url: str) -> list[tuple[Tag, str]]:
    links: list[tuple[Tag, str]] = []

    for anchor in container.find_all("a", href=True):
        href = urljoin(base_url, clean_text(anchor.get("href")))
        scheme = urlsplit(href).scheme.casefold()
        link_text = normalize_identifier(anchor.get_text(" ", strip=True))

        if scheme in {"http", "https"} and (
            is_map_url(href) or "ver mapa" in link_text
        ):
            links.append((anchor, href))

    return links


def _address_line(lines: list[str]) -> tuple[int, str] | None:
    for index, line in enumerate(lines):
        if ADDRESS_START_PATTERN.search(line) and any(
            character.isdigit() for character in line
        ):
            return index, line

    return None


def _point_name(container: Tag, lines: list[str], address_index: int) -> str:
    headings = container.find_all(["h2", "h3", "h4", "h5", "h6"])

    for heading in reversed(headings):
        candidate = clean_text(heading.get_text(" ", strip=True))
        normalized = normalize_identifier(candidate)

        if candidate and normalized not in {
            "puntos de venta",
            "ubicaciones y horarios",
        }:
            return candidate

    for candidate in reversed(lines[:address_index]):
        normalized = normalize_identifier(candidate)

        if (
            candidate
            and "@" not in candidate
            and "ver mapa" not in normalized
            and not ADDRESS_START_PATTERN.search(candidate)
            and len(candidate) <= 100
        ):
            return candidate

    return ""


def extract_map_cards(
    soup: BeautifulSoup,
    base_url: str,
) -> list[dict[str, Any]]:
    """Extrae tarjetas que publican nombre, dirección y un enlace de mapa."""

    results: list[dict[str, Any]] = []
    processed_links: set[str] = set()

    for anchor, link in _map_links(soup, base_url):
        if link in processed_links:
            continue

        selected: tuple[Tag, list[str], int, str] | None = None

        for ancestor in anchor.parents:
            if not isinstance(ancestor, Tag) or ancestor.name in {"body", "html"}:
                break

            links = _map_links(ancestor, base_url)
            lines = [clean_text(line) for line in ancestor.stripped_strings]
            address = _address_line(lines)

            if len(links) == 1 and address is not None:
                address_index, address_text = address
                selected = (ancestor, lines, address_index, address_text)
                break

        if selected is None:
            continue

        container, lines, address_index, address_text = selected
        point_of_sale = _point_name(container, lines, address_index)

        if not point_of_sale:
            continue

        latitude, longitude = coordinates_from_url(link)
        results.append(
            {
                "point_of_sale": point_of_sale,
                "address_text": address_text,
                "address_link": link,
                "latitude": latitude,
                "longitude": longitude,
            }
        )
        processed_links.add(link)

    return results


def iter_json_nodes(value: Any):
    """Recorre objetos JSON-LD anidados."""

    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from iter_json_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_json_nodes(child)


MYMAPS_HOSTS = {"www.google.com", "google.com"}
MYMAPS_PATH_MARKER = "/maps/d/"


def google_mymaps_mid(url: str) -> str:
    """Extrae el identificador público ``mid`` de una URL de Google My Maps."""

    cleaned = clean_text(url)
    parsed = urlsplit(cleaned)

    if parsed.netloc.casefold() not in MYMAPS_HOSTS:
        return ""

    if MYMAPS_PATH_MARKER not in parsed.path.casefold():
        return ""

    return clean_text(parse_qs(parsed.query).get("mid", [""])[0])


def find_google_mymaps_mid(soup: BeautifulSoup, base_url: str) -> str:
    """Encuentra un Google My Maps embebido o enlazado en la página."""

    candidates: list[str] = []

    for iframe in soup.find_all("iframe", src=True):
        candidates.append(urljoin(base_url, clean_text(iframe.get("src"))))

    for anchor in soup.find_all("a", href=True):
        candidates.append(urljoin(base_url, clean_text(anchor.get("href"))))

    for candidate in candidates:
        mid = google_mymaps_mid(candidate)
        if mid:
            return mid

    return ""


def google_mymaps_kml_url(mid: str) -> str:
    """Construye la exportación KML pública de un mapa de Google My Maps."""

    query = urlencode({"mid": clean_text(mid), "forcekml": "1"})
    return f"https://www.google.com/maps/d/kml?{query}"


def _kml_local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]


def _kml_child_text(element: Any, name: str) -> str:
    for child in list(element):
        if _kml_local_name(child.tag) == name:
            return clean_text(child.text)
    return ""


def _kml_descendant_text(element: Any, name: str) -> str:
    for child in element.iter():
        if _kml_local_name(child.tag) == name:
            return clean_text(child.text)
    return ""


def _kml_extended_data(placemark: Any) -> dict[str, str]:
    values: dict[str, str] = {}

    for element in placemark.iter():
        local = _kml_local_name(element.tag)

        if local == "Data":
            key = normalize_identifier(element.attrib.get("name"))
            value = _kml_descendant_text(element, "value")
        elif local == "SimpleData":
            key = normalize_identifier(element.attrib.get("name"))
            value = clean_text(element.text)
        else:
            continue

        if key and value:
            values[key] = value

    return values


def _kml_description_text(value: str) -> str:
    """Convierte descripciones HTML de My Maps a texto legible."""

    if not value:
        return ""

    return clean_text(BeautifulSoup(value, "html.parser").get_text(" ", strip=True))


def _kml_address(placemark: Any) -> str:
    extended = _kml_extended_data(placemark)

    for key in (
        "address",
        "direccion",
        "dirección",
        "dirección completa",
        "direccion completa",
        "ubicacion",
        "ubicación",
    ):
        normalized = normalize_identifier(key)
        if extended.get(normalized):
            return extended[normalized]

    direct_address = _kml_child_text(placemark, "address")
    if direct_address:
        return direct_address

    description = _kml_description_text(_kml_child_text(placemark, "description"))
    return description


def parse_google_mymaps_kml(
    kml_text: str,
    *,
    chain_name: str,
    source_url: str,
) -> list[StoreRecord]:
    """Convierte puntos de un KML de My Maps al contrato de tiendas."""

    from xml.etree import ElementTree as ET

    try:
        root = ET.fromstring(kml_text)
    except ET.ParseError as error:
        raise ValueError("Google My Maps no devolvió KML/XML válido") from error

    stores: list[StoreRecord] = []

    for placemark in root.iter():
        if _kml_local_name(placemark.tag) != "Placemark":
            continue

        name = _kml_child_text(placemark, "name")
        coordinates = _kml_descendant_text(placemark, "coordinates")

        if not name or not coordinates:
            continue

        first_coordinate = coordinates.split()[0].strip()
        parts = [part.strip() for part in first_coordinate.split(",")]
        if len(parts) < 2:
            continue

        longitude = normalize_coordinate(parts[0], -180.0, 180.0)
        latitude = normalize_coordinate(parts[1], -90.0, 90.0)

        if latitude == "" or longitude == "":
            continue

        stores.append(
            make_record(
                chain_name=chain_name,
                source_url=source_url,
                point_of_sale=name,
                address_text=_kml_address(placemark),
                latitude=latitude,
                longitude=longitude,
            )
        )

    return stores
