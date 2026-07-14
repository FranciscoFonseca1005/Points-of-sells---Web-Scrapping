from pathlib import Path

import pytest

from src.exceptions import InputValidationError
from src.input_reader import read_chain_requests


def write_input(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_reads_exact_input_schema(tmp_path: Path) -> None:
    input_path = tmp_path / "chains.csv"
    write_input(
        input_path,
        "chain_name,url\n"
        "DROGERIA ALEMANA,https://www.tudrogueriavirtual.com/\n",
    )

    chains = read_chain_requests(input_path)

    assert len(chains) == 1
    assert chains[0].chain_name == "DROGERIA ALEMANA"
    assert chains[0].url == "https://www.tudrogueriavirtual.com/"


def test_rejects_additional_input_columns(tmp_path: Path) -> None:
    input_path = tmp_path / "chains.csv"
    write_input(
        input_path,
        "chain_name,url,city\nDROGERIA ALEMANA,https://example.com,Bogotá\n",
    )

    with pytest.raises(InputValidationError):
        read_chain_requests(input_path)


def test_rejects_invalid_url(tmp_path: Path) -> None:
    input_path = tmp_path / "chains.csv"
    write_input(input_path, "chain_name,url\nCadena,no-es-una-url\n")

    with pytest.raises(InputValidationError):
        read_chain_requests(input_path)
