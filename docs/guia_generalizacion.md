# Guía metodológica para generalizar el extractor

## Objetivo

Aceptar lotes de cadenas y URLs sin convertir el programa en un raspador que
adivine contenido. La generalización se obtiene mediante un orquestador común,
estrategias reutilizables y adaptadores aislados para excepciones.

## Principio de evidencia

Un registro se exporta únicamente cuando la fuente permite relacionar de forma
explícita un punto de venta con al menos una dirección, un enlace de mapa o
coordenadas. Los campos ausentes quedan vacíos.

No se realizan estas operaciones:

- geocodificar una dirección;
- construir coordenadas a partir de una ciudad;
- completar nombres con resultados de terceros;
- resolver CAPTCHA o autenticación;
- mezclar registros de dos marcas que comparten una plataforma.

## Capas del proceso

| Capa | Responsabilidad |
|---|---|
| Entrada | Exigir `chain_name` y `url`, y validar HTTP/HTTPS |
| Registro | Elegir el adaptador más específico |
| Acceso | Consultar HTTP, reutilizar respuestas y activar Chromium solo si hace falta |
| Extracción | Traducir la fuente a las siete columnas |
| Validación | Revisar llaves, tipos y rangos de coordenadas |
| Deduplicación | Eliminar únicamente coincidencias evidentes |
| Exportación | Separar datos finales y diagnóstico técnico |

## Orden de estrategias

1. **API pública conocida.** Es el método más estable y estructurado.
2. **HTML específico conocido.** Usa relaciones claras entre encabezados,
   direcciones y enlaces.
3. **JSON-LD genérico.** Aprovecha datos `schema.org` publicados por una URL
   nueva.
4. **Tarjetas con mapa.** Requiere nombre, dirección y enlace explícito dentro
   de la misma tarjeta.
5. **Adaptador pendiente.** Si ninguna estrategia produce evidencia suficiente,
   se reporta el caso sin fabricar filas.

## Fuentes compartidas

Cuando varias marcas apuntan a la misma URL, la respuesta se conserva en caché
durante la ejecución. Cada marca aplica después su filtro explícito. En
Unidrogas, por ejemplo, `ALEMANA`, `INGLESA`, `ANDINA` y `JUNIN` son tokens
independientes del nombre publicado del establecimiento.

## Navegador de respaldo

El cliente comienza con `requests`. Si recibe una pantalla de espera, una
verificación automática o un error HTTP, puede abrir Chromium y devolver el
HTML renderizado. El navegador comparte su sesión entre páginas de la misma
ejecución y se cierra al finalizar.

Si la verificación persiste, la cadena falla de forma aislada. Las demás
continúan y el motivo queda en `extraction_report.csv`.

## Incorporar una nueva fuente

1. Agregarla a `input/chains.csv` y ejecutar el programa.
2. Revisar `extraction_report.csv`.
3. Si el modo automático falla, inspeccionar la fuente pública y determinar si
   usa HTML, JSON, API o JavaScript.
4. Crear una clase derivada de `BaseAdapter`.
5. Definir `supports`, `strategy` y `extract`.
6. Registrar el adaptador antes del genérico en `registry.py`.
7. Agregar pruebas con una respuesta mínima simulada.
8. Comparar el conteo y varias filas contra la página pública.

## Pruebas de aceptación recomendadas

- Todas las cadenas válidas aparecen como `OK` o `ERROR` en el reporte.
- Una URL compartida no mezcla marcas.
- `stores` conserva exactamente siete columnas.
- No aparecen teléfonos, correos ni horarios en la dirección.
- Las coordenadas vacías permanecen vacías.
- Las coordenadas presentes respetan los rangos globales.
- Ejecutar dos veces produce los mismos duplicados eliminados.
- Un fallo de una fuente no elimina resultados de las demás.

## Mantenimiento

Conviene revisar periódicamente:

- cambios de dominio o ruta del localizador;
- cambios en nombres de campos JSON;
- conteos que caen repentinamente a cero;
- pantallas nuevas de verificación;
- sucursales duplicadas por cambios de formato.

Los conteos esperados sirven como alerta, pero no deben codificarse como una
verdad fija porque las cadenas abren y cierran establecimientos.
