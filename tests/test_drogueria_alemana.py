from typing import Any

import pytest

from src.adapters.drogueria_alemana import (
    STORES_DATA_URL,
    DrogueriaAlemanaAdapter,
)
from src.exceptions import SourceResponseError
from src.input_reader import ChainRequest


class FakeClient:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.requested_urls: list[str] = []

    def get_json(self, url: str) -> Any:
        self.requested_urls.append(url)
        return self.payload


def test_maps_only_explicit_alemana_records() -> None:
    payload = [
        {
            "name": "  ALEMANA   01 ",
            "direction": "CARRERA 33\nNO. 45-68 SAN PIO",
            "lat": "7.118271",
            "lgn": -73.111548,
            "phone": "no debe exportarse",
        },
        {
            "name": "COOFARMA 5",
            "direction": "Otra dirección",
            "lat": 7.0,
            "lgn": -73.0,
        },
        {
            "name": "ALEMANA SIN COORDENADAS",
            "direction": None,
            "lat": None,
            "lgn": "",
        },
    ]
    client = FakeClient(payload)
    chain = ChainRequest(
        chain_name="DROGERIA ALEMANA",
        url="https://www.tudrogueriavirtual.com/",
    )

    stores = DrogueriaAlemanaAdapter().extract(chain, client)

    assert client.requested_urls == [STORES_DATA_URL]
    assert len(stores) == 2
    assert stores[0] == {
        "chain_name": "DROGERIA ALEMANA",
        "url": "https://www.tudrogueriavirtual.com/",
        "point_of_sale": "ALEMANA 01",
        "address_text": "CARRERA 33 NO. 45-68 SAN PIO",
        "address_link": "",
        "latitude": 7.118271,
        "longitude": -73.111548,
    }
    assert stores[1]["address_text"] == ""
    assert stores[1]["latitude"] == ""
    assert stores[1]["longitude"] == ""


def test_invalid_coordinates_remain_empty() -> None:
    client = FakeClient(
        [
            {
                "name": "ALEMANA PRUEBA",
                "direction": "Dirección publicada",
                "lat": 100,
                "lgn": "no-numérica",
            }
        ]
    )
    chain = ChainRequest("ALEMANA", "https://example.com")

    store = DrogueriaAlemanaAdapter().extract(chain, client)[0]

    assert store["latitude"] == ""
    assert store["longitude"] == ""


def test_rejects_non_list_payload() -> None:
    client = FakeClient({"stores": []})
    chain = ChainRequest("ALEMANA", "https://example.com")

    with pytest.raises(SourceResponseError):
        DrogueriaAlemanaAdapter().extract(chain, client)
