"""Registro ordenado de adaptadores disponibles."""

from __future__ import annotations

from src.adapters.base import BaseAdapter
from src.adapters.darsalud import DarsaludAdapter
from src.adapters.farmacia_torres import FarmaciaTorresAdapter
from src.adapters.generic import GenericStructuredAdapter
from src.adapters.unidrogas import UnidrogasAdapter
from src.adapters.zapatoca import ZapatocaAdapter


# El adaptador genérico siempre permanece al final.
ADAPTERS: tuple[BaseAdapter, ...] = (
    UnidrogasAdapter(),
    DarsaludAdapter(),
    FarmaciaTorresAdapter(),
    ZapatocaAdapter(),
    GenericStructuredAdapter(),
)


def get_adapter(chain_name: str, url: str = "") -> BaseAdapter:
    """Selecciona la regla más específica y usa descubrimiento como respaldo."""

    for adapter in ADAPTERS:
        if adapter.supports(chain_name, url):
            return adapter

    raise RuntimeError("El registro debe terminar con un adaptador genérico")
