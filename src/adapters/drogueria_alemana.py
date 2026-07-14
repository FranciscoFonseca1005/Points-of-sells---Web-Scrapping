"""Compatibilidad con el adaptador original de Droguería Alemana."""

from src.adapters.unidrogas import STORES_DATA_URL, UnidrogasAdapter


CHAIN_KEYWORD = "alemana"


class DrogueriaAlemanaAdapter(UnidrogasAdapter):
    """Nombre histórico conservado para scripts y pruebas existentes."""

    aliases = (
        "DROGERIA ALEMANA",
        "DROGUERÍA ALEMANA",
        "ALEMANA",
    )
