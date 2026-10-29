from typing import Any

import pytest

from src.adapters.unidrogas import STORES_DATA_URL, UnidrogasAdapter
from src.input_reader import ChainRequest


class FakeClient:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.requested_urls: list[str] = []

    def get_json(self, url: str) -> Any:
        self.requested_urls.append(url)
        return self.payload


@pytest.mark.parametrize(
    ("chain_name", "expected_name"),
    [
        ("DROGERIA ALEMANA", "ALEMANA 01"),
        ("DROGUERIA INGLESA", "INGLESA 02"),
        ("DROGUERIA ANDINA", "ANDINA 03"),
        ("BOTICA JUNIN", "BOTICA JUNÍN 04"),
    ],
)
def test_filters_each_unidrogas_brand_strictly(
    chain_name: str,
    expected_name: str,
) -> None:
    payload = [
        {
            "name": name,
            "direction": f"Dirección {index}",
            "lat": 4.6 + index / 100,
            "lgn": -74.1 - index / 100,
        }
        for index, name in enumerate(
            ("ALEMANA 01", "INGLESA 02", "ANDINA 03", "BOTICA JUNÍN 04")
        )
    ]
    client = FakeClient(payload)
    chain = ChainRequest(chain_name, "https://www.tudrogueriavirtual.com/")

    stores = UnidrogasAdapter().extract(chain, client)

    assert client.requested_urls == [STORES_DATA_URL]
    assert [store["point_of_sale"] for store in stores] == [expected_name]
    assert all(store["chain_name"] == chain_name for store in stores)


def test_recognizes_known_input_typo_without_mixing_brands() -> None:
    client = FakeClient(
        [
            {
                "name": "ANDINA 01",
                "direction": "Calle 1",
                "lat": 4.6,
                "lgn": -74.1,
            },
            {
                "name": "ALEMANA 01",
                "direction": "Calle 2",
                "lat": 4.7,
                "lgn": -74.2,
            },
        ]
    )

    stores = UnidrogasAdapter().extract(
        ChainRequest("DROOGUERIA ANDINA", "https://example.com"),
        client,
    )

    assert [store["point_of_sale"] for store in stores] == ["ANDINA 01"]
