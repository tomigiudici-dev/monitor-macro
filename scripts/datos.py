"""Descarga las series del Catálogo API-INDEC y las guarda como JSON en docs/data/.

Necesita el token del INDEC (variable INDEC_TOKEN o archivo ~/indec_token.txt).
Imprime una línea por serie con "ACTUALIZADO" o "sin cambios", y al final
"CAMBIOS: <series>" para que el flujo de GitHub sepa qué cambió.

    python scripts/datos.py
"""

import datetime
import json
import os

from indec_api import a_numero, consultar

DESDE = "2016-10"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "docs", "data")


def fecha(periodo):
    """'202609' -> '2026-09'; '20262T' (trimestre) -> '2026-04', el primer mes del trimestre."""
    if periodo.endswith("T"):
        return f"{periodo[:4]}-{(int(periodo[4]) - 1) * 3 + 1:02d}"
    return f"{periodo[:4]}-{periodo[4:6]}"


def pivotear(filas, clave, columnas):
    """Arma una fila por período con una columna por valor de `clave` (según el dict `columnas`)."""
    por_fecha = {}
    for f in filas:
        col = columnas.get(f[clave])
        if col is None:
            continue
        fila = por_fecha.setdefault(fecha(f["periodo"]), {"fecha": fecha(f["periodo"])})
        fila[col] = a_numero(f["valor"])
    nombres = list(columnas.values())
    return [
        {"fecha": k, **{n: v.get(n) for n in nombres}}
        for k, v in sorted(por_fecha.items())
        if k >= DESDE
    ]


def ipc():
    filas = consultar("ipc_nacional", {
        "region": "eq.Nacional",
        "clasificador": "eq.IPC",
        "codigo": "eq.0",
        "tipo_de_indicador": "in.(Indice,v_m,v_ia)",
    }, order="periodo,tipo_de_indicador")
    return pivotear(filas, "tipo_de_indicador", {"Indice": "ipc", "v_m": "v_m", "v_ia": "v_ia"})


def salarios():
    filas = consultar("indice_salarios", {
        "tipo_de_indicador": "eq.Indice",
        "codigo": "in.(0,110,120,200)",
        "anio": "gte.2016",
    }, order="periodo,codigo")
    return pivotear(filas, "codigo", {
        "0": "total",
        "110": "privado_registrado",
        "120": "publico",
        "200": "no_registrado",
    })


def emae():
    filas = consultar("estimador-mensual-de-actividad-economica-nivel-general", {"anio": "gte.2016"},
                      order="periodo,tipo_de_indicador_descripcion")
    return pivotear(filas, "tipo_de_indicador_descripcion", {
        "Índice serie original": "original",
        "Índice serie desestacionalizada": "desestacionalizada",
        "Var % interanual serie original": "v_ia",
        "Var % mensual serie desestacionalizada": "v_m",
    })


def desempleo():
    filas = consultar("mercado_trabajo_eph", {
        "area_geografica_nom": "eq.T_31_A",
        "select": "periodo,tasa_de_desocupacion",
    }, order="periodo")
    out = []
    for f in filas:
        tasa = a_numero(f["tasa_de_desocupacion"])
        out.append({"fecha": fecha(f["periodo"]), "tasa": None if tasa is None else round(tasa / 100, 6)})
    return sorted((r for r in out if r["fecha"] >= DESDE), key=lambda r: r["fecha"])


def guardar(nombre, contenido):
    """Escribe el archivo solo si cambió. Devuelve True si lo actualizó."""
    ruta = os.path.join(SALIDA, f"{nombre}.json")
    texto = json.dumps(contenido, ensure_ascii=False, separators=(",", ":"))
    try:
        with open(ruta, encoding="utf-8") as fh:
            if fh.read() == texto:
                return False
    except OSError:
        pass
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(texto)
    return True


def main():
    os.makedirs(SALIDA, exist_ok=True)
    # Baja todo antes de escribir: si la API falla a mitad de camino, no queda nada a medio actualizar.
    datos = {nombre: bajar() for nombre, bajar in
             (("ipc", ipc), ("salarios", salarios), ("emae", emae), ("desempleo", desempleo))}
    cambios = []
    for nombre, filas in datos.items():
        if guardar(nombre, filas):
            cambios.append(nombre)
        estado = "ACTUALIZADO" if nombre in cambios else "sin cambios"
        print(f"{nombre}.json: {estado}, {len(filas)} filas, {filas[0]['fecha']} a {filas[-1]['fecha']}")
    if cambios:
        ahora = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        guardar("meta", {"actualizado": ahora, "series": cambios})
    print("CAMBIOS:", " ".join(cambios))


if __name__ == "__main__":
    main()
