"""Adaptador del directorio público de Farmacia Torres."""

from __future__ import annotations

from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from src.adapters.base import BaseAdapter, SourceClient
from src.adapters.common import make_record, strip_address_label
from src.exceptions import SourceResponseError
from src.input_reader import ChainRequest
from src.normalization import clean_text, normalize_identifier
from src.validation import StoreRecord


class FarmaciaTorresAdapter(BaseAdapter):
    """Descubre páginas por ciudad y lee sus sucursales publicadas."""

    aliases = ("FARMACIA TORRES", "DROGUERIA FARMACIA TORRES")
    strategy = "directorio_paginas_por_ciudad"

    def supports(self, chain_name: str, url: str = "") -> bool:
        parsed = urlsplit(url)
        return super().supports(chain_name, url) or (
            parsed.netloc.casefold().endswith("sucursales.com.co")
            and parsed.path.rstrip("/").endswith("/farmacia-torres")
        )

    @staticmethod
    def _city_links(html: str, source_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        source = urlsplit(source_url)
        root_parts = [part for part in source.path.split("/") if part]
        links: list[str] = []

        for anchor in soup.find_all("a", href=True):
            candidate = urljoin(source_url, clean_text(anchor.get("href")))
            parsed = urlsplit(candidate)
            parts = [part for part in parsed.path.split("/") if part]

            if parsed.netloc.casefold() != source.netloc.casefold():
                continue

            if len(parts) != len(root_parts) + 1:
                continue

            if parts[: len(root_parts)] != root_parts:
                continue

            if candidate not in links:
                links.append(candidate)

        return links

    @staticmethod
    def _address_after(heading: Tag) -> str:
        sibling = heading.find_next_sibling()

        while sibling is not None:
            if isinstance(sibling, Tag) and sibling.name in {"h2", "h3"}:
                break

            if isinstance(sibling, Tag):
                text = clean_text(sibling.get_text(" ", strip=True))
                normalized = normalize_identifier(text)

                if "direccion" in normalized:
                    return strip_address_label(text)

            sibling = sibling.find_next_sibling()

        return ""

    def _stores_from_page(
        self,
        html: str,
        chain: ChainRequest,
    ) -> list[StoreRecord]:
        soup = BeautifulSoup(html, "html.parser")
        stores: list[StoreRecord] = []

        for heading in soup.find_all("h3"):
            point_of_sale = clean_text(heading.get_text(" ", strip=True))

            if not normalize_identifier(point_of_sale).startswith("sucursal "):
                continue

            address_text = self._address_after(heading)

            if not address_text:
                continue

            stores.append(
                make_record(
                    chain_name=chain.chain_name,
                    source_url=chain.url,
                    point_of_sale=point_of_sale,
                    address_text=address_text,
                )
            )

        return stores

    def extract(
        self,
        chain: ChainRequest,
        client: SourceClient,
    ) -> list[StoreRecord]:
        root_html = client.get_html(chain.url)
        stores = self._stores_from_page(root_html, chain)

        for city_url in self._city_links(root_html, chain.url):
            stores.extend(self._stores_from_page(client.get_html(city_url), chain))

        if not stores:
            raise SourceResponseError(
                "El directorio de Farmacia Torres no publicó sucursales en "
                "una estructura reconocible"
            )

        return stores
