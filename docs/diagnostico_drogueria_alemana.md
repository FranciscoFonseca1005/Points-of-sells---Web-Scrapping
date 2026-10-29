# Diagnóstico: Droguería Alemana

Fecha de revisión: 13 de julio de 2026.

## Fuente revisada

- URL principal: <https://www.tudrogueriavirtual.com/>
- Localizador oficial: <https://www.tudrogueriavirtual.com/tiendas>
- Fuente JSON pública usada por el localizador:
  <https://api.redeca.unidrogas.com/external/storesData>

El localizador está construido en VTEX y carga un componente JavaScript de
`unidrogas.store-locator`. El código publicado del componente realiza una
solicitud GET a la fuente JSON anterior. Por esta razón, la extracción final no
necesita controlar un navegador ni recorrer manualmente los filtros por
departamento y ciudad.

## Estructura observada

La fuente devuelve una lista de establecimientos de varias marcas. Durante la
revisión, el localizador recibió 802 registros. La lista mezcla, entre otras,
tiendas Alemana, Coofarma y otros establecimientos de Unidrogas.

Los campos pertinentes son:

| Campo JSON | Uso en la salida |
|---|---|
| `name` | `point_of_sale` |
| `direction` | `address_text` |
| `lat` | `latitude` |
| `lgn` | `longitude` |

La fuente también puede publicar otros datos, pero no se exportan porque no
pertenecen al esquema solicitado.

## Regla del adaptador

El adaptador conserva únicamente registros cuyo `name` contiene de forma
explícita la palabra `ALEMANA`, sin distinguir mayúsculas o tildes. No asigna a
Droguería Alemana los establecimientos de otras marcas presentes en la misma
fuente.

En la validación del 13 de julio de 2026 se obtuvieron 307 puntos de venta
únicos. Esa cantidad puede cambiar cuando la cadena actualice su fuente.

`address_link` queda vacío porque la respuesta no publica un enlace individual
de ubicación. Las coordenadas se copian de `lat` y `lgn`; no se geocodifican
direcciones ni se consulta Google Maps para completar datos.

## Estrategia elegida

1. Consultar el JSON con `requests`.
2. Comprobar que la respuesta sea una lista.
3. Filtrar por el nombre explícito `ALEMANA`.
4. Limpiar solamente espacios y saltos de línea.
5. Validar rangos de coordenadas.
6. Eliminar únicamente duplicados evidentes.
7. Exportar las siete columnas contractuales.

Los prototipos con Playwright se conservan únicamente como evidencia y respaldo
de investigación; no forman parte del flujo principal.
