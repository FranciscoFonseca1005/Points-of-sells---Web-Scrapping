"""Extracción conservadora de Farmacias El Descuento en Farmaenlace."""

from __future__ import annotations

from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, NavigableString, Tag

from src.adapters.base import BaseAdapter, SourceClient
from src.adapters.common import coordinates_from_url, is_map_url, make_record
from src.exceptions import SourceResponseError
from src.input_reader import ChainRequest
from src.normalization import clean_text, normalize_identifier
from src.validation import StoreRecord


class FarmaenlaceDescuentoAdapter(BaseAdapter):
    """Filtra únicamente POS que el sitio identifica como El Descuento.

    Farmaenlace publica varias marcas en la misma página. Este adaptador no
    atribuye tiendas ECO/MEDI/Farmayor/El Cisne a El Descuento; sólo conserva
    nombres con evidencia explícita de la marca (EL DESCUENTO, PAF ED o
    FARMADESCUENTO).
    """

    aliases = ("DESCUENTO", "EL DESCUENTO", "FARMACIAS EL DESCUENTO")
    strategy = "html_farmaenlace_el_descuento_conservador"

    def supports(self, chain_name: str, url: str = "") -> bool:
        host = urlsplit(url).netloc.casefold()
        normalized = normalize_identifier(chain_name)
        by_name = normalized in {normalize_identifier(alias) for alias in self.aliases}
        return by_name and (not host or host.endswith("farmaenlace.com"))

    @staticmethod
    def _is_discount_name(value: str) -> bool:
        normalized = normalize_identifier(value)
        return (
            "el descuento" in normalized
            or normalized.startswith("paf ed ")
            or "farmadescuento" in normalized
            or "farma descuento" in normalized
        )

    @staticmethod
    def _details_after_heading(heading: Tag, source_url: str) -> tuple[str, str, float | str, float | str]:
        address_text = ""
        address_link = ""
        latitude: float | str = ""
        longitude: float | str = ""
        expecting_address = False

        for element in heading.next_elements:
            if element is heading:
                continue

            if isinstance(element, Tag):
                if element.name in {"h2", "h3", "h4", "h5", "h6"}:
                    break

                if element.name == "a" and element.get("href") and not address_link:
                    href = urljoin(source_url, clean_text(element.get("href")))
                    text = normalize_identifier(element.get_text(" ", strip=True))
                    if is_map_url(href) or "ver en el mapa" in text:
                        address_link = href
                        latitude, longitude = coordinates_from_url(href)

                if latitude == "" or longitude == "":
                    attrs = {
                        normalize_identifier(key): clean_text(value)
                        for key, value in element.attrs.items()
                        if isinstance(value, (str, int, float))
                    }
                    lat_value = next(
                        (attrs[key] for key in ("data lat", "lat", "latitude", "data latitude") if attrs.get(key)),
                        "",
                    )
                    lon_value = next(
                        (attrs[key] for key in ("data lng", "data lon", "lng", "lon", "longitude", "data longitude") if attrs.get(key)),
                        "",
                    )
                    if lat_value and lon_value:
                        try:
                            lat = float(lat_value)
                            lon = float(lon_value)
                        except ValueError:
                            pass
                        else:
                            if -90 <= lat <= 90 and -180 <= lon <= 180:
                                latitude, longitude = lat, lon

            if isinstance(element, NavigableString):
                text = clean_text(str(element))
                if not text:
                    continue

                normalized = normalize_identifier(text)
                if normalized in {"direccion", "direccion:"}:
                    expecting_address = True
                    continue

                if normalized.startswith("direccion:"):
                    suffix = clean_text(text.split(":", maxsplit=1)[1])
                    if suffix:
                        address_text = suffix
                        expecting_address = False
                    else:
                        expecting_address = True
                    continue

                if expecting_address and not address_text:
                    if normalized not in {"ver en el mapa", "regresar"}:
                        address_text = text
                        expecting_address = False

        return address_text, address_link, latitude, longitude

    def extract(self, chain: ChainRequest, client: SourceClient) -> list[StoreRecord]:
        soup = BeautifulSoup(client.get_html(chain.url), "html.parser")
        stores: list[StoreRecord] = []
        seen: set[tuple[str, str]] = set()

        for heading in soup.find_all(["h4", "h5", "h6"]):
            point_of_sale = clean_text(heading.get_text(" ", strip=True))
            if not self._is_discount_name(point_of_sale):
                continue

            address_text, address_link, latitude, longitude = self._details_after_heading(
                heading, chain.url
            )
            if not address_text:
                continue

            key = (normalize_identifier(point_of_sale), normalize_identifier(address_text))
            if key in seen:
                continue

            stores.append(
                make_record(
                    chain_name=chain.chain_name,
                    source_url=chain.url,
                    point_of_sale=point_of_sale,
                    address_text=address_text,
                    address_link=address_link,
                    latitude=latitude,
                    longitude=longitude,
                )
            )
            seen.add(key)

        if not stores:
            raise SourceResponseError(
                "Farmaenlace no expuso puntos identificables de Farmacias El "
                "Descuento en la página consultada. No se mezclaron otras marcas."
            )

        return stores
