"""Descubrimiento conservador para URLs nuevas con datos estructurados."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from bs4 import BeautifulSoup

from src.adapters.base import BaseAdapter, SourceClient
from src.adapters.common import (
    extract_map_cards,
    find_google_mymaps_mid,
    google_mymaps_kml_url,
    is_map_url,
    iter_json_nodes,
    make_record,
    parse_google_mymaps_kml,
)
from src.exceptions import SourceResponseError
from src.input_reader import ChainRequest
from src.normalization import clean_text, normalize_identifier
from src.validation import StoreRecord


STORE_TYPES = {
    "localbusiness",
    "store",
    "pharmacy",
    "grocerystore",
    "medicalbusiness",
    "departmentstore",
    "conveniencestore",
    "shoppingcenter",
}


def _types(node: Mapping[str, Any]) -> set[str]:
    raw_types = node.get("@type", [])

    if not isinstance(raw_types, list):
        raw_types = [raw_types]

    return {
        normalize_identifier(clean_text(value).rsplit("/", maxsplit=1)[-1])
        for value in raw_types
    }


def _address(value: Any) -> str:
    if isinstance(value, str):
        return clean_text(value)

    if not isinstance(value, Mapping):
        return ""

    parts = [
        clean_text(value.get(field))
        for field in (
            "streetAddress",
            "addressLocality",
            "addressRegion",
            "postalCode",
            "addressCountry",
        )
    ]
    return ", ".join(part for part in parts if part)


def _geo(node: Mapping[str, Any]) -> tuple[Any, Any]:
    geo = node.get("geo")

    if not isinstance(geo, Mapping):
        return "", ""

    return geo.get("latitude", ""), geo.get("longitude", "")


def _map_link(node: Mapping[str, Any]) -> str:
    for key in ("hasMap", "map"):
        value = node.get(key)

        if isinstance(value, Mapping):
            value = value.get("@id") or value.get("url")

        link = clean_text(value)

        if link and is_map_url(link):
            return link

    return ""


class GenericStructuredAdapter(BaseAdapter):
    """Acepta cualquier URL, pero solo exporta evidencia estructurada."""

    strategy = "descubrimiento_automatico_conservador"

    def supports(self, chain_name: str, url: str = "") -> bool:
        del chain_name, url
        return True

    def _json_ld_records(
        self,
        soup: BeautifulSoup,
        chain: ChainRequest,
    ) -> list[StoreRecord]:
        stores: list[StoreRecord] = []

        for script in soup.find_all("script", type="application/ld+json"):
            raw_json = script.string or script.get_text()

            try:
                payload = json.loads(raw_json)
            except (TypeError, json.JSONDecodeError):
                continue

            for node in iter_json_nodes(payload):
                if not (_types(node) & STORE_TYPES):
                    continue

                point_of_sale = clean_text(node.get("name"))
                address_text = _address(node.get("address"))
                latitude, longitude = _geo(node)
                address_link = _map_link(node)

                if not point_of_sale or not (
                    address_text or address_link or latitude != "" or longitude != ""
                ):
                    continue

                stores.append(
                    make_record(
                        chain_name=chain.chain_name,
                        source_url=chain.url,
                        point_of_sale=point_of_sale,
                        address_text=address_text,
                        address_link=address_link,
                        latitude=latitude,
                        longitude=longitude,
                    )
                )

        return stores

    def extract(
        self,
        chain: ChainRequest,
        client: SourceClient,
    ) -> list[StoreRecord]:
        soup = BeautifulSoup(client.get_html(chain.url), "html.parser")
        stores = self._json_ld_records(soup, chain)

        if not stores:
            stores = [
                make_record(
                    chain_name=chain.chain_name,
                    source_url=chain.url,
                    **card,
                )
                for card in extract_map_cards(soup, chain.url)
            ]

        if not stores:
            mid = find_google_mymaps_mid(soup, chain.url)

            if mid:
                kml_url = google_mymaps_kml_url(mid)
                kml_text = client.get_text(
                    kml_url,
                    "application/vnd.google-earth.kml+xml, "
                    "application/xml;q=0.9, text/xml;q=0.8, */*;q=0.7",
                )
                stores = parse_google_mymaps_kml(
                    kml_text,
                    chain_name=chain.chain_name,
                    source_url=chain.url,
                )

        if not stores:
            raise SourceResponseError(
                "La URL no contiene puntos de venta en JSON-LD, tarjetas "
                "con nombre/dirección/mapa ni un Google My Maps público con "
                "puntos exportables. Se requiere diagnosticar esta fuente y "
                "agregar una estrategia."
            )

        return stores
