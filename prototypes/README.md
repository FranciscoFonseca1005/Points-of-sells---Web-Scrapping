# Prototipos de Droguería Alemana

Estos archivos documentan la primera estrategia validada contra el localizador
visual:

- `drogueria_alemana.py`: prueba de Santander - Bucaramanga.
- `drogueria_alemana_nacional.py`: recorrido de departamentos y ciudades.

El flujo principal ahora usa la fuente JSON pública mediante `python main.py`.
Los prototipos quedan como respaldo y no deben usarse para la extracción
habitual.

Para ejecutarlos de forma opcional:

```powershell
py -m pip install -r requirements-prototypes.txt
py -m playwright install chromium
```
