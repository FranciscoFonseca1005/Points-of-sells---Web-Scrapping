# Extractor general de puntos de venta

Programa en Python para recibir una lista de cadenas y URLs, localizar los
puntos de venta publicados en fuentes públicas y consolidarlos en un único CSV
y Excel.

La herramienta combina adaptadores conocidos con un descubrimiento automático
conservador. Puede recibir cualquier URL, pero solo exporta establecimientos
cuando encuentra evidencia explícita. No inventa nombres, direcciones,
coordenadas ni enlaces.

## Fuentes integradas

| Fuente | Estrategia | Información extraída |
|---|---|---|
| Tu Droguería Virtual / Unidrogas | API pública compartida y filtro estricto por marca | Nombre, dirección y coordenadas publicadas |
| Darsalud | Encabezados y direcciones del HTML | Nombre y dirección |
| Farmacia Torres | Descubrimiento de páginas por ciudad | Nombre y dirección |
| Mercado Zapatoca | Tarjetas con enlace explícito de mapa | Nombre, dirección, enlace y coordenadas literales si aparecen en el enlace |
| URL nueva | JSON-LD o tarjetas inequívocas con mapa | Solo campos publicados de forma estructurada |

Las marcas de Unidrogas incluidas son:

- Droguería Alemana
- Droguería Inglesa
- Droguería Andina
- Botica Junín

La fuente compartida se descarga una sola vez durante cada ejecución gracias a
la caché del cliente. Cada marca se filtra por una palabra explícita de su
nombre; nunca se replica la lista completa para todas las cadenas.

## Contrato de salida

`output/stores.csv` y `output/stores.xlsx` contienen exactamente:

```text
chain_name
url
point_of_sale
address_text
address_link
latitude
longitude
```

Una fila representa un punto de venta. Las coordenadas solo se incluyen cuando
la fuente las publica como números o dentro de un enlace de mapa. Una dirección
sin coordenadas permanece sin coordenadas.

El diagnóstico se guarda por separado en
`output/extraction_report.csv`; por tanto, los mensajes técnicos nunca agregan
columnas a `stores`.

## Requisitos

- Python 3.10 o superior.
- Acceso a internet durante la extracción.
- Chromium de Playwright para páginas dinámicas o verificaciones no
  interactivas.

## Instalación en Windows

Desde PowerShell, dentro de la carpeta del proyecto:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
py -m playwright install chromium
```

El paquete `truststore` hace que `requests` utilice los certificados confiables
de Windows. Esto conserva la solución aplicada al error
`CERTIFICATE_VERIFY_FAILED` de la fuente de Unidrogas.

## Entrada

`input/chains.csv` debe conservar exactamente dos columnas:

```csv
chain_name,url
DROGERIA ALEMANA,https://www.tudrogueriavirtual.com/
DROGUERIA INGLESA,https://www.tudrogueriavirtual.com/
DARSALUD,https://darsalud.com/drugstores.html
DROGUERIA ANDINA,https://www.tudrogueriavirtual.com/
BOTICA JUNIN,https://www.tudrogueriavirtual.com/
FARMACIA TORRES,https://sucursales.com.co/farmacia-torres/
ZAPATOCA,https://www.mercadozapatoca.com/puntos-de-venta/
```

Se aceptan mayúsculas, minúsculas y variantes con o sin acentos de las marcas
conocidas. El texto original de `chain_name` se conserva en la salida.

## Ejecución

Flujo habitual:

```powershell
py main.py
```

Rutas personalizadas:

```powershell
py main.py --input input\chains.csv --output-dir output
```

Mostrar Chromium cuando una página lo necesite:

```powershell
py main.py --headed
```

Desactivar completamente el respaldo de navegador:

```powershell
py main.py --no-browser
```

Al terminar se crean o actualizan:

```text
output/stores.csv
output/stores.xlsx
output/extraction_report.csv
```

Si todas las cadenas fallan, `stores.csv` y `stores.xlsx` no se sobrescriben.
El reporte sí se actualiza para explicar cada fallo.

## Cómo decide la estrategia

1. Valida `chain_name` y `url`.
2. Selecciona el adaptador más específico por marca o dominio.
3. Reutiliza respuestas de URLs repetidas.
4. Intenta HTTP estático.
5. Si recibe una pantalla de verificación o un error de acceso, utiliza
   Chromium una vez como respaldo.
6. Extrae únicamente campos publicados.
7. Valida las siete columnas y elimina duplicados evidentes.
8. Exporta resultados y reporte por separado.

El navegador espera verificaciones automáticas normales, pero no resuelve
CAPTCHA, no evade bloqueos y no inicia sesión.

## URLs nuevas

Una URL desconocida pasa al adaptador automático. Este reconoce:

- objetos JSON-LD `LocalBusiness`, `Store`, `Pharmacy` y tipos relacionados;
- tarjetas repetidas con nombre, dirección y un enlace explícito de mapa.

Si no existe una estructura suficientemente clara, la cadena aparece como
`ERROR` en `extraction_report.csv`. Esto evita confundir productos, teléfonos,
direcciones corporativas o contenido del pie de página con sucursales.

En ese caso se diagnostica la nueva fuente y se incorpora un adaptador pequeño
en `src/adapters/`. No es necesario modificar las demás cadenas.

## Pruebas

```powershell
py -m pip install -r requirements-dev.txt
py -m pytest -q
```

Las pruebas usan páginas y respuestas simuladas; no generan tráfico hacia los
sitios reales.

## Estructura principal

```text
web scrapping/
├── input/
│   └── chains.csv
├── output/
├── src/
│   ├── adapters/
│   │   ├── unidrogas.py
│   │   ├── darsalud.py
│   │   ├── farmacia_torres.py
│   │   ├── zapatoca.py
│   │   ├── generic.py
│   │   └── registry.py
│   ├── http_client.py
│   ├── pipeline.py
│   ├── validation.py
│   └── export.py
├── tests/
├── docs/
├── main.py
└── requirements.txt
```

## Límites

- Ningún extractor puede garantizar resultados para literalmente cualquier
  página: el contenido puede requerir sesión, CAPTCHA o una API privada.
- Los cambios de diseño de una fuente pueden exigir mantenimiento de su
  adaptador.
- La falta de resultados significa que no se identificó evidencia suficiente;
  no demuestra que la cadena carezca de tiendas.
- No se geocodifican direcciones ni se consultan mapas para completar datos.
- No se extraen cuentas privadas ni datos personales.

La metodología detallada está en
[`docs/guia_generalizacion.md`](docs/guia_generalizacion.md).
