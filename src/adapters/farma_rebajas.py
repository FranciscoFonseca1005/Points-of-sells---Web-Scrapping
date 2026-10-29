"""Adaptador del directorio público de Farma Rebajas Ecuador."""

from __future__ import annotations

from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from src.adapters.base import BaseAdapter, SourceClient
from src.adapters.common import coordinates_from_url, is_map_url, make_record
from src.exceptions import SourceResponseError
from src.input_reader import ChainRequest
from src.normalization import clean_text, normalize_identifier
from src.validation import StoreRecord


class FarmaRebajasAdapter(BaseAdapter):
    """Lee las tarjetas con nombre, ciudad, dirección y ``Cómo llegar``."""

    aliases = ("LA REBAJA", "FARMA REBAJAS", "FARMAREBAJAS")
    strategy = "html_farma_rebajas"

    def supports(self, chain_name: str, url: str = "") -> bool:
        host = urlsplit(url).netloc.casefold()
        return super().supports(chain_name, url) or host.endswith("farmarebajas.com.ec")

    @staticmethod
    def _card_from_directions_link(anchor: Tag) -> Tag | None:
        selected: Tag | None = None

        for ancestor in anchor.parents:
            if not isinstance(ancestor, Tag) or ancestor.name in {"body", "html"}:
                break

            direction_links = [
                link
                for link in ancestor.find_all("a", href=True)
                if "como llegar" in normalize_identifier(link.get_text(" ", strip=True))
            ]
            headings = ancestor.find_all(["h2", "h3", "h4", "h5", "h6"])

            if len(direction_links) == 1 and len(headings) == 1:
                selected = ancestor
            elif len(direction_links) > 1:
                break

        return selected

    @staticmethod
    def _record_from_card(card: Tag, anchor: Tag, source_url: str) -> dict[str, object] | None:
        heading = card.find(["h2", "h3", "h4", "h5", "h6"])
        if heading is None:
            return None

        point_of_sale = clean_text(heading.get_text(" ", strip=True))
        lines = [clean_text(text) for text in card.stripped_strings]
        normalized_name = normalize_identifier(point_of_sale)

        useful: list[str] = []
        for line in lines:
            normalized = normalize_identifier(line)
            if not line or normalized == normalized_name:
                continue
            if "como llegar" in normalized or normalized.startswith("mapa de "):
                continue
            useful.append(line)

        # La tarjeta pública muestra ciudad y después dirección. La última línea
        # textual antes de ``Cómo llegar`` es por tanto la dirección publicada.
        address_text = useful[-1] if useful else ""
        href = urljoin(source_url, clean_text(anchor.get("href")))
        address_link = href if is_map_url(href) else href
        latitude, longitude = coordinates_from_url(address_link)

        if not point_of_sale or not address_text:
            return None

        return {
            "point_of_sale": point_of_sale,
            "address_text": address_text,
            "address_link": address_link,
            "latitude": latitude,
            "longitude": longitude,
        }

    def extract(self, chain: ChainRequest, client: SourceClient) -> list[StoreRecord]:
        soup = BeautifulSoup(client.get_html(chain.url), "html.parser")
        stores: list[StoreRecord] = []
        seen: set[tuple[str, str]] = set()

        for anchor in soup.find_all("a", href=True):
            if "como llegar" not in normalize_identifier(anchor.get_text(" ", strip=True)):
                continue

            card = self._card_from_directions_link(anchor)
            if card is None:
                continue

            values = self._record_from_card(card, anchor, chain.url)
            if values is None:
                continue

            key = (
                normalize_identifier(values["point_of_sale"]),
                normalize_identifier(values["address_text"]),
            )
            if key in seen:
                continue

            stores.append(
                make_record(
                    chain_name=chain.chain_name,
                    source_url=chain.url,
                    **values,
                )
            )
            seen.add(key)

        if not stores:
            raise SourceResponseError(
                "No se identificaron sucursales en el directorio público de Farma Rebajas"
            )

        return stores
