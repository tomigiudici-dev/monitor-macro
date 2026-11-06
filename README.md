# Monitor Macro

Sitio público con inflación, salario real, actividad económica, desocupación, dinero y crédito de la Argentina, con datos del [Catálogo API-INDEC](https://api.indec.gob.ar/) y de la [API de estadísticas del BCRA](https://api.bcra.gob.ar/). Se actualiza solo y genera imágenes y textos listos para publicar en X.

Sitio independiente, sin relación con el INDEC ni con el BCRA. Fuentes de los datos: INDEC y BCRA.

## Cómo funciona

- `scripts/datos.py` baja las series de la API del INDEC y de la del BCRA, y las guarda en `docs/data/`. La del BCRA es pública y no pide token; si no responde, se conservan sus datos anteriores sin frenar la actualización del INDEC.
- `scripts/imagenes.py` genera las imágenes de `docs/img/` y los textos sugeridos de `docs/x/textos.json`.
- `docs/index.html` es la página. Lee los JSON y dibuja los gráficos en el navegador.
- El flujo **Actualizar datos** (`.github/workflows/actualizar.yml`) corre los días hábiles a las 16:45 y 19:45 (hora argentina). Si el INDEC publicó algo nuevo, guarda los datos, regenera las imágenes, publica el sitio y abre un issue con los textos e imágenes para X.
- El flujo **Publicar sitio** sube la carpeta `docs/` a GitHub Pages cada vez que cambia `main`.

Si la API del INDEC no responde (está en beta), la ejecución termina con un aviso y se reintenta en la siguiente. Si el token venció, la ejecución falla con un mensaje que lo dice.

## Configuración (una sola vez)

1. **Secreto del token**: en *Settings → Secrets and variables → Actions → New repository secret*, creá `INDEC_TOKEN` con el token que generaste en tu perfil de api.indec.gob.ar.
2. **GitHub Pages**: en *Settings → Pages → Build and deployment → Source*, elegí **GitHub Actions**.
3. En *Actions*, corré **Publicar sitio** a mano la primera vez.

El token vence a los 12 meses: cuando lo regeneres, actualizá el secreto.

## Uso local

```bash
pip install matplotlib
python scripts/datos.py          # lee el token de INDEC_TOKEN o de ~/indec_token.txt
python scripts/imagenes.py
python -m http.server --directory docs
```

## Notas sobre los datos

- Las variaciones de inflación y de actividad son las que publica el INDEC.
- El salario real es el índice de salarios de cada sector dividido por el IPC nacional, con base diciembre de 2016 = 100.
- La desocupación es la tasa trimestral de la EPH para el total de 31 aglomerados urbanos.
- Dinero y crédito (BCRA): promedios mensuales de los datos diarios de base monetaria, M2, depósitos y préstamos al sector privado, divididos por el IPC (diciembre de 2016 = 100); las reservas son el dato de fin de mes, en millones de dólares. Solo se toman meses completos, y un mes nuevo es lo único que cuenta como novedad, porque el BCRA revisa seguido los datos diarios.

## Tipografías

Archivo, Chivo y Chivo Mono, de Omnibus-Type, con licencia SIL Open Font License. La página las carga desde Google Fonts y el generador de imágenes usa las copias de `scripts/fuentes/`, junto con sus licencias.
