from src.adapters.darsalud import DarsaludAdapter
from src.adapters.farmacia_torres import FarmaciaTorresAdapter
from src.adapters.generic import GenericStructuredAdapter
from src.adapters.zapatoca import ZapatocaAdapter
from src.input_reader import ChainRequest


class FakeHtmlClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.requested_urls: list[str] = []

    def get_html(self, url: str) -> str:
        self.requested_urls.append(url)
        return self.pages[url]


def test_darsalud_reads_headings_and_removes_phones() -> None:
    url = "https://darsalud.com/drugstores.html"
    client = FakeHtmlClient(
        {
            url: """
                <h2>Otras Sucursales</h2>
                <h5>El Centro</h5>
                <p>Dirección: Calle 34 No. 27-97 - Teléfono: 280 88 38</p>
                <hr>
                <h5>Berlin</h5>
                <p>Dirección: Calle 42 No. 30 - 10 Teléfono: 283 62 41</p>
            """
        }
    )

    stores = DarsaludAdapter().extract(ChainRequest("DARSALUD", url), client)

    assert [store["point_of_sale"] for store in stores] == [
        "El Centro",
        "Berlin",
    ]
    assert [store["address_text"] for store in stores] == [
        "Calle 34 No. 27-97",
        "Calle 42 No. 30 - 10",
    ]
    assert all(store["latitude"] == "" for store in stores)


def test_zapatoca_reads_map_cards_and_literal_coordinates() -> None:
    url = "https://www.mercadozapatoca.com/puntos-de-venta/"
    client = FakeHtmlClient(
        {
            url: """
                <section>
                  <h1>Puntos de venta</h1>
                  <article class="store-card">
                    <h3>Pradera</h3>
                    <p>Carrera 65 No. 4B - 97</p>
                    <p>pradera@example.com</p>
                    <a href="https://www.google.com/maps?q=4.625,-74.115">
                      Ver mapa
                    </a>
                  </article>
                  <article class="store-card">
                    <h3>Primavera</h3>
                    <p>Calle 5A No. 43 - 22</p>
                    <a href="https://maps.app.goo.gl/abc">Ver mapa</a>
                  </article>
                </section>
            """
        }
    )

    stores = ZapatocaAdapter().extract(ChainRequest("ZAPATOCA", url), client)

    assert len(stores) == 2
    assert stores[0]["point_of_sale"] == "Pradera"
    assert stores[0]["address_text"] == "Carrera 65 No. 4B - 97"
    assert stores[0]["latitude"] == 4.625
    assert stores[0]["longitude"] == -74.115
    assert stores[1]["latitude"] == ""
    assert stores[1]["longitude"] == ""


def test_farmacia_torres_discovers_city_page() -> None:
    root = "https://sucursales.com.co/farmacia-torres/"
    city = "https://sucursales.com.co/farmacia-torres/barranquilla/"
    client = FakeHtmlClient(
        {
            root: f'<a href="{city}">Farmacia Torres Barranquilla</a>',
            city: """
                <h2>Sucursales con horario normal en Barranquilla</h2>
                <h3>Sucursal Carrera 40</h3>
                <ul><li>📍 <strong>Dirección</strong>: Cra. 40 #37-44</li></ul>
                <ul><li><strong>Teléfono</strong>: 321 5196404</li></ul>
                <h3>Sucursal Carrera 43</h3>
                <ul><li>📍 <strong>Dirección</strong>: Cra. 43 #70-24</li></ul>
            """,
        }
    )

    stores = FarmaciaTorresAdapter().extract(
        ChainRequest("FARMACIA TORRES", root),
        client,
    )

    assert client.requested_urls == [root, city]
    assert [(store["point_of_sale"], store["address_text"]) for store in stores] == [
        ("Sucursal Carrera 40", "Cra. 40 #37-44"),
        ("Sucursal Carrera 43", "Cra. 43 #70-24"),
    ]


def test_generic_adapter_reads_local_business_json_ld() -> None:
    url = "https://example.com/tiendas"
    client = FakeHtmlClient(
        {
            url: """
                <script type="application/ld+json">
                {
                  "@context": "https://schema.org",
                  "@graph": [
                    {
                      "@type": "Pharmacy",
                      "name": "Sucursal Norte",
                      "address": {
                        "@type": "PostalAddress",
                        "streetAddress": "Calle 10 #20-30",
                        "addressLocality": "Bogotá"
                      },
                      "geo": {"latitude": 4.7, "longitude": -74.05}
                    }
                  ]
                }
                </script>
            """
        }
    )

    stores = GenericStructuredAdapter().extract(
        ChainRequest("CADENA NUEVA", url),
        client,
    )

    assert stores == [
        {
            "chain_name": "CADENA NUEVA",
            "url": url,
            "point_of_sale": "Sucursal Norte",
            "address_text": "Calle 10 #20-30, Bogotá",
            "address_link": "",
            "latitude": 4.7,
            "longitude": -74.05,
        }
    ]
