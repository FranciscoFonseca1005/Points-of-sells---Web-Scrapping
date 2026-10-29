"""Contrato común para adaptadores de fuentes públicas."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol

from src.input_reader import ChainRequest
from src.normalization import normalize_identifier
from src.validation import StoreRecord


class SourceClient(Protocol):
    """Interfaz mínima requerida por los adaptadores."""

    def get_json(self, url: str) -> Any:
        """Consulta una URL y devuelve su JSON."""

    def get_html(self, url: str) -> str:
        """Consulta una URL y devuelve HTML estático o renderizado."""

    def get_text(self, url: str, accept: str = "text/plain, */*") -> str:
        """Consulta una URL de texto (XML, KML, CSV, etc.)."""


# Alias conservado para no romper importaciones de la primera versión.
JsonClient = SourceClient


class BaseAdapter(ABC):
    """Base aislada para la lógica específica de cada cadena."""

    aliases: tuple[str, ...] = ()
    strategy = "adaptador_especifico"

    def supports(self, chain_name: str, url: str = "") -> bool:
        """Indica si el adaptador reconoce la cadena o la fuente."""

        del url
        normalized = normalize_identifier(chain_name)
        return normalized in {
            normalize_identifier(alias) for alias in self.aliases
        }

    @abstractmethod
    def extract(
        self,
        chain: ChainRequest,
        client: SourceClient,
    ) -> list[StoreRecord]:
        """Extrae los puntos de venta publicados por una cadena."""
