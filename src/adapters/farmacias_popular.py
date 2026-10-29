from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.adapters.base import BaseAdapter
from src.exceptions import SourceResponseError


STORE_PAGE_URL = "https://farmaciaspopular.com/tiendas"


class FarmaciasPopularAdapter(BaseAdapter):
    """Extrae Farmacias Popular Unidas desde el bundle JS público."""

    source_type = "js_embedded_farmacias_popular"

    def supports(self, chain_name: str, url: str) -> bool:
        normalized_name = chain_name.strip().upper()
        normalized_url = url.strip().lower()

        return (
            normalized_name in {
                "FARMACIAS POPULAR UNIDAS",
                "FARMACIA POPULAR UNIDAS",
                "POPULAR UNIDAS",
            }
            or "farmaciaspopular.com" in normalized_url
        )


    def extract(self, chain, client):
        # 1. Descargar la página de tiendas.
        html = client.get_html(STORE_PAGE_URL)

        # 2. Encontrar el bundle JavaScript actual.
        soup = BeautifulSoup(html, "html.parser")

        script_src = None

        for script in soup.find_all("script"):
            src = script.get("src", "")

            if "/assets/index-" in src and src.endswith(".js"):
                script_src = src
                break

        if not script_src:
            raise SourceResponseError(
                "No se encontró el bundle JavaScript público "
                "de Farmacias Popular Unidas."
            )

        bundle_url = urljoin(STORE_PAGE_URL, script_src)

        # 3. Descargar el bundle.
        js = client.get_text(bundle_url)

        # 4. Los puntos de venta están embebidos con esta estructura:
        #
        # {code:"MAR",
        #  name:"Farmacia Popular Unidas 1",
        #  address:"Gran Colombia y Tarqui",
        #  city:"Cuenca",
        #  lat:-2.895...,
        #  lng:-79.008...}
        #
        pattern = re.compile(
            r'\{code:"(?P<code>[^"]*)",'
            r'name:"(?P<name>[^"]*)",'
            r'address:"(?P<address>[^"]*)",'
            r'city:"(?P<city>[^"]*)",'
            r'lat:(?P<lat>null|-?\d+(?:\.\d+)?),'
            r'lng:(?P<lng>null|-?\d+(?:\.\d+)?)\}'
        )

        stores = []

        for match in pattern.finditer(js):
            row = match.groupdict()

            name = " ".join(row["name"].split())
            address = " ".join(row["address"].split())
            city = " ".join(row["city"].split())

            # Evita capturar otros objetos que pudieran tener
            # la misma estructura dentro del bundle.
            if "farmacia" not in name.lower():
                continue

            if "popular" not in name.lower():
                continue

            if row["lat"] == "null":
                latitude = ""
            else:
                latitude = float(row["lat"])

            if row["lng"] == "null":
                longitude = ""
            else:
                longitude = float(row["lng"])

            if address and city and city.lower() not in address.lower():
                address_text = f"{address}, {city}"
            else:
                address_text = address

            stores.append(
                {
                    "chain_name": chain.chain_name,
                    "url": chain.url,
                    "point_of_sale": name,
                    "address_text": address_text,
                    "address_link": "",
                    "latitude": latitude,
                    "longitude": longitude,
                }
            )

        if not stores:
            raise SourceResponseError(
                "Se encontró el bundle de Farmacias Popular Unidas, "
                "pero no se identificaron tiendas en el dataset embebido."
            )

        return stores

