from src.adapters.farmacias_popular import FarmaciasPopularAdapter
from src.adapters.farma_rebajas import FarmaRebajasAdapter
from src.adapters.farmaenlace_descuento import FarmaenlaceDescuentoAdapter
from src.adapters.registry import get_adapter
from src.input_reader import ChainRequest


class FakeHtmlClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.requested_urls: list[str] = []

    def get_html(self, url: str) -> str:
        self.requested_urls.append(url)
        return self.pages[url]


def test_popular_discovers_tiendas_and_keeps_stores_without_coordinates() -> None:
    root = "https://farmaciaspopular.com/"
    directory = "https://farmaciaspopular.com/tiendas"
    client = FakeHtmlClient(
        {
            root: '<a href="/tiendas">Nuestras tiendas</a>',
            directory: """
                <section class="stores">
                  <article>
                    <h3>Farmacia Popular Unidas 50</h3>
                    <p>General Torres 7-26</p>
                    <p>Cuenca</p>
                    <a href="https://www.google.com/maps?q=-2.9,-79.0">Cómo llegar</a>
                  </article>
                  <article>
                    <h3>Farmacia Popular Unidas 60</h3>
                    <p>Cochancay</p>
                    <p>Cochancay</p>
                    <span>Sin coordenadas</span>
                  </article>
                </section>
            """,
        }
    )

    stores = FarmaciasPopularAdapter().extract(
        ChainRequest("FARMACIAS POPULAR UNIDAS", root), client
    )

    assert client.requested_urls == [root, directory]
    assert len(stores) == 2
    assert stores[0]["point_of_sale"] == "Farmacia Popular Unidas 50"
    assert stores[0]["address_text"] == "General Torres 7-26"
    assert stores[0]["latitude"] == -2.9
    assert stores[0]["longitude"] == -79.0
    assert stores[1]["point_of_sale"] == "Farmacia Popular Unidas 60"
    assert stores[1]["address_text"] == "Cochancay"
    assert stores[1]["address_link"] == ""
    assert stores[1]["latitude"] == ""


def test_farma_rebajas_reads_cards_with_city_and_directions_link() -> None:
    url = "https://farmarebajas.com.ec/sucursales"
    client = FakeHtmlClient(
        {
            url: """
                <main>
                  <article class="branch">
                    <a href="https://www.google.com/maps?q=-1.55,-79.75">Mapa de Palenque</a>
                    <h3>Palenque</h3>
                    <p>Vinces</p>
                    <p>Calle Rocha y Juan Carlos Aspiazu</p>
                    <a href="https://www.google.com/maps?q=-1.55,-79.75">Cómo llegar</a>
                  </article>
                  <article class="branch">
                    <h3>Ximena</h3>
                    <p>Guayaquil</p>
                    <p>Ximena 413 y Alejo Lascano</p>
                    <a href="https://maps.app.goo.gl/abc">Cómo llegar</a>
                  </article>
                </main>
            """
        }
    )

    stores = FarmaRebajasAdapter().extract(ChainRequest("LA REBAJA", url), client)

    assert len(stores) == 2
    assert stores[0]["point_of_sale"] == "Palenque"
    assert stores[0]["address_text"] == "Calle Rocha y Juan Carlos Aspiazu"
    assert stores[0]["latitude"] == -1.55
    assert stores[0]["longitude"] == -79.75
    assert stores[1]["point_of_sale"] == "Ximena"
    assert stores[1]["address_text"] == "Ximena 413 y Alejo Lascano"


def test_farmaenlace_descuento_does_not_mix_other_brands() -> None:
    url = "https://www.farmaenlace.com/puntos-de-venta/"
    client = FakeHtmlClient(
        {
            url: """
                <div class="store"><h5>ECO QUITO PUEMBO</h5>
                  <span>Dirección:</span><p>HUMBERTO DUQUE OE7-356</p></div>
                <div class="store"><h5>MEDI QUITO WHYMPER</h5>
                  <span>Dirección:</span><p>CALLE WHYMPER N31-257</p></div>
                <div class="store"><h5>PAF EL DESCUENTO AMBATO AV GALO VELA</h5>
                  <span>Dirección:</span><p>AV. GALO VELA S/N Y CALLE OYAMBARO</p>
                  <a href="https://www.google.com/maps?q=-1.27,-78.62">Ver en el mapa</a></div>
                <div class="store"><h5>PAF ED ESMERALDAS HOSPITAL DEL SUR</h5>
                  <span>Dirección:</span><p>AV. A S/N, ENTRE CALLE G Y CALLE</p></div>
                <div class="store"><h5>PAF FARMADESCUENTOS NACIONAL</h5>
                  <span>Dirección:</span><p>VICENTE ROCAFUERTE 509 Y AV. CHONE</p></div>
            """
        }
    )

    stores = FarmaenlaceDescuentoAdapter().extract(
        ChainRequest("DESCUENTO", url), client
    )

    assert [store["point_of_sale"] for store in stores] == [
        "PAF EL DESCUENTO AMBATO AV GALO VELA",
        "PAF ED ESMERALDAS HOSPITAL DEL SUR",
        "PAF FARMADESCUENTOS NACIONAL",
    ]
    assert stores[0]["address_text"] == "AV. GALO VELA S/N Y CALLE OYAMBARO"
    assert stores[0]["latitude"] == -1.27
    assert stores[0]["longitude"] == -78.62
    assert all(not store["point_of_sale"].startswith("ECO") for store in stores)
    assert all(not store["point_of_sale"].startswith("MEDI") for store in stores)


def test_registry_selects_new_ecuador_adapters() -> None:
    assert isinstance(
        get_adapter("FARMACIAS POPULAR UNIDAS", "https://farmaciaspopular.com/"),
        FarmaciasPopularAdapter,
    )
    assert isinstance(
        get_adapter("LA REBAJA", "https://farmarebajas.com.ec/sucursales"),
        FarmaRebajasAdapter,
    )
    assert isinstance(
        get_adapter("DESCUENTO", "https://www.farmaenlace.com/puntos-de-venta/"),
        FarmaenlaceDescuentoAdapter,
    )
