"""Adaptador de la página pública de puntos de venta de Zapatoca."""

from __future__ import annotations

from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from src.adapters.base import BaseAdapter, SourceClient
from src.adapters.common import extract_map_cards, make_record
from src.exceptions import SourceResponseError
from src.input_reader import ChainRequest
from src.validation import StoreRecord


class ZapatocaAdapter(BaseAdapter):
    """Extrae las tarjetas que incluyen un enlace explícito de mapa."""

    aliases = ("ZAPATOCA", "MERCADO ZAPATOCA", "MERCADOS ZAPATOCA")
    strategy = "html_tarjetas_con_mapa"

    def supports(self, chain_name: str, url: str = "") -> bool:
        host = urlsplit(url).netloc.casefold()
        return super().supports(chain_name, url) or host.endswith(
            "mercadozapatoca.com"
        )

    def extract(
        self,
        chain: ChainRequest,
        client: SourceClient,
    ) -> list[StoreRecord]:
        soup = BeautifulSoup(client.get_html(chain.url), "html.parser")
        cards = extract_map_cards(soup, chain.url)
        stores = [
            make_record(
                chain_name=chain.chain_name,
                source_url=chain.url,
                **card,
            )
            for card in cards
        ]

        if not stores:
            raise SourceResponseError(
                "No se identificaron tarjetas con nombre, dirección y mapa "
                "en la página de Zapatoca"
            )

        return stores
