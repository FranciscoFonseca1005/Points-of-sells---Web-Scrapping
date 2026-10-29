"""Adaptador del listado público de Darsalud."""

from __future__ import annotations

from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag

from src.adapters.base import BaseAdapter, SourceClient
from src.adapters.common import address_before_phone, make_record
from src.exceptions import SourceResponseError
from src.input_reader import ChainRequest
from src.normalization import clean_text, normalize_identifier
from src.validation import StoreRecord


class DarsaludAdapter(BaseAdapter):
    """Lee encabezados de sucursal seguidos por su dirección publicada."""

    aliases = ("DARSALUD", "DARSALUD DROGUERIAS", "DARSALUD DROGUERÍAS")
    strategy = "html_darsalud"

    def supports(self, chain_name: str, url: str = "") -> bool:
        host = urlsplit(url).netloc.casefold()
        return super().supports(chain_name, url) or host.endswith("darsalud.com")

    @staticmethod
    def _address_after(heading: Tag) -> str:
        sibling = heading.find_next_sibling()

        while sibling is not None:
            if isinstance(sibling, Tag) and sibling.name in {
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
            }:
                break

            if isinstance(sibling, Tag):
                text = clean_text(sibling.get_text(" ", strip=True))

                if normalize_identifier(text).startswith("direccion:"):
                    return address_before_phone(text)

            sibling = sibling.find_next_sibling()

        return ""

    def extract(
        self,
        chain: ChainRequest,
        client: SourceClient,
    ) -> list[StoreRecord]:
        soup = BeautifulSoup(client.get_html(chain.url), "html.parser")
        stores: list[StoreRecord] = []

        for heading in soup.find_all(["h4", "h5"]):
            point_of_sale = clean_text(heading.get_text(" ", strip=True))
            address_text = self._address_after(heading)

            if not point_of_sale or not address_text:
                continue

            stores.append(
                make_record(
                    chain_name=chain.chain_name,
                    source_url=chain.url,
                    point_of_sale=point_of_sale,
                    address_text=address_text,
                )
            )

        if not stores:
            raise SourceResponseError(
                "No se identificaron sucursales en el listado público de Darsalud"
            )

        return stores
