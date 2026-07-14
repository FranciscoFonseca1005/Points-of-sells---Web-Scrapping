"""Adaptador compartido del localizador público de Unidrogas."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from src.adapters.base import BaseAdapter, SourceClient
from src.adapters.common import make_record
from src.exceptions import SourceResponseError
from src.input_reader import ChainRequest
from src.normalization import clean_text, normalize_identifier
from src.validation import StoreRecord


STORES_DATA_URL = "https://api.redeca.unidrogas.com/external/storesData"


@dataclass(frozen=True)
class ChainRule:
    """Nombres aceptados y token explícito publicado por la fuente."""

    aliases: tuple[str, ...]
    keyword: str


CHAIN_RULES = (
    ChainRule(
        aliases=("DROGERIA ALEMANA", "DROGUERÍA ALEMANA", "ALEMANA"),
        keyword="alemana",
    ),
    ChainRule(
        aliases=("DROGUERIA INGLESA", "DROGUERÍA INGLESA", "INGLESA"),
        keyword="inglesa",
    ),
    ChainRule(
        aliases=(
            "DROGUERIA ANDINA",
            "DROGUERÍA ANDINA",
            "DROOGUERIA ANDINA",
            "ANDINA",
        ),
        keyword="andina",
    ),
    ChainRule(
        aliases=("BOTICA JUNIN", "BOTICA JUNÍN", "JUNIN", "JUNÍN"),
        keyword="junin",
    ),
)


class UnidrogasAdapter(BaseAdapter):
    """Filtra estrictamente una marca dentro de la fuente compartida."""

    aliases = tuple(alias for rule in CHAIN_RULES for alias in rule.aliases)
    strategy = "api_publica_unidrogas"

    @staticmethod
    def _rule_for(chain_name: str) -> ChainRule:
        normalized = normalize_identifier(chain_name)

        for rule in CHAIN_RULES:
            if normalized in {
                normalize_identifier(alias) for alias in rule.aliases
            }:
                return rule

        raise SourceResponseError(
            f"No existe una regla explícita de Unidrogas para {chain_name!r}"
        )

    def extract(
        self,
        chain: ChainRequest,
        client: SourceClient,
    ) -> list[StoreRecord]:
        rule = self._rule_for(chain.chain_name)
        payload = client.get_json(STORES_DATA_URL)

        if not isinstance(payload, list):
            raise SourceResponseError(
                "La fuente de Unidrogas no devolvió una lista JSON"
            )

        stores: list[StoreRecord] = []

        for raw_store in payload:
            if not isinstance(raw_store, Mapping):
                continue

            point_of_sale = clean_text(raw_store.get("name"))
            words = set(re.findall(r"[a-z0-9]+", normalize_identifier(point_of_sale)))

            if rule.keyword not in words:
                continue

            stores.append(
                make_record(
                    chain_name=chain.chain_name,
                    source_url=chain.url,
                    point_of_sale=point_of_sale,
                    address_text=raw_store.get("direction"),
                    latitude=raw_store.get("lat"),
                    longitude=raw_store.get("lgn"),
                )
            )

        if not stores:
            raise SourceResponseError(
                "La fuente pública de Unidrogas no contiene registros con "
                f"el identificador explícito {rule.keyword.upper()}"
            )

        return stores
