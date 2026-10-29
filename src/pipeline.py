"""Orquestación de cadenas con errores aislados."""

from __future__ import annotations

from dataclasses import dataclass

from src.adapters.base import SourceClient
from src.adapters.registry import get_adapter
from src.http_client import HttpClient
from src.input_reader import ChainRequest
from src.validation import (
    StoreRecord,
    deduplicate_evident,
    validate_records,
)


@dataclass(frozen=True)
class ChainSuccess:
    """Resumen de una cadena procesada."""

    chain_name: str
    url: str
    store_count: int
    strategy: str


@dataclass(frozen=True)
class ChainFailure:
    """Error reportable fuera del archivo final."""

    chain_name: str
    url: str
    message: str
    strategy: str


@dataclass(frozen=True)
class RunReport:
    """Resultado consolidado del procesamiento."""

    records: list[StoreRecord]
    successes: list[ChainSuccess]
    failures: list[ChainFailure]


def _run_with_client(
    chains: list[ChainRequest],
    client: SourceClient,
) -> RunReport:
    all_records: list[StoreRecord] = []
    successes: list[ChainSuccess] = []
    failures: list[ChainFailure] = []

    for chain in chains:
        strategy = "sin_seleccionar"

        try:
            adapter = get_adapter(chain.chain_name, chain.url)
            strategy = adapter.strategy
            extracted = adapter.extract(chain, client)
            validated = validate_records(extracted)
            unique = deduplicate_evident(validated)

            if not unique:
                raise ValueError("El adaptador terminó sin puntos de venta")

            all_records.extend(unique)
            successes.append(
                ChainSuccess(
                    chain_name=chain.chain_name,
                    url=chain.url,
                    store_count=len(unique),
                    strategy=strategy,
                )
            )
        except Exception as error:  # Continúa con las demás cadenas.
            failures.append(
                ChainFailure(
                    chain_name=chain.chain_name,
                    url=chain.url,
                    message=str(error),
                    strategy=strategy,
                )
            )

    return RunReport(
        records=deduplicate_evident(all_records),
        successes=successes,
        failures=failures,
    )


def run_pipeline(
    chains: list[ChainRequest],
    client: SourceClient | None = None,
    *,
    allow_browser: bool = True,
    headless: bool = True,
) -> RunReport:
    """Ejecuta todas las cadenas y conserva los errores por separado."""

    if client is not None:
        return _run_with_client(chains, client)

    with HttpClient(
        allow_browser=allow_browser,
        headless=headless,
    ) as http_client:
        return _run_with_client(chains, http_client)
