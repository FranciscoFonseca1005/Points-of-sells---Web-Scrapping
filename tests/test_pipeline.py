from typing import Any

from src.input_reader import ChainRequest
from src.pipeline import run_pipeline


class FakeClient:
    def get_json(self, _: str) -> Any:
        return [
            {
                "name": "ALEMANA 01",
                "direction": "CARRERA 33 NO. 45-68",
                "lat": 7.118271,
                "lgn": -73.111548,
            }
        ]


def test_pipeline_isolates_unsupported_chain() -> None:
    chains = [
        ChainRequest("DROGERIA ALEMANA", "https://example.com/alemana"),
        ChainRequest("CADENA SIN ADAPTADOR", "https://example.com/otra"),
    ]

    report = run_pipeline(chains, client=FakeClient())

    assert len(report.records) == 1
    assert len(report.successes) == 1
    assert len(report.failures) == 1
    assert report.failures[0].chain_name == "CADENA SIN ADAPTADOR"
