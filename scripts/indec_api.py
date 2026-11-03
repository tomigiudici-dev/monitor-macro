"""Cliente mínimo para el Catálogo API-INDEC (https://api.indec.gob.ar).

Solo usa la biblioteca estándar. El token se lee de la variable de entorno INDEC_TOKEN
o, si no está, del archivo ~/indec_token.txt (se genera en el perfil de api.indec.gob.ar
después de registrarse).

Ejemplos:
    python indec_api.py --list
    python indec_api.py --info ipc_nacional
    python indec_api.py ipc_nacional anio=gte.2025 --max 50
    python indec_api.py mercado_trabajo_eph --select periodo,tasa_de_desocupacion --csv desempleo.csv
"""

import argparse
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.indec.gob.ar/v1"
PAGE = 1000  # la API devuelve como máximo 1000 filas por respuesta
UA = "indec-api-cliente/0.1 (+python)"


def _request(url, token=None, headers=None):
    h = {"User-Agent": UA, "Accept": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r), dict(r.headers)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise SystemExit(f"HTTP {e.code} en {url}\n{body}") from None
    except OSError as e:  # sin conexión, conexión cortada o tiempo agotado
        motivo = getattr(e, "reason", None) or e
        raise SystemExit(f"Sin conexión con {url}: {motivo}") from None


def spec():
    """La especificación OpenAPI es pública (no requiere token)."""
    data, _ = _request(BASE + "/")
    return data


def tablas(s=None):
    """Devuelve {tabla: (resumen, clave_de_orden)} a partir de la especificación."""
    s = s or spec()
    out = {}
    for path, ops in s["paths"].items():
        op = ops.get("get", {})
        clave = ""
        for p in op.get("parameters", []):
            if p.get("name") == "order":
                m = re.search(r"clave completa:\s*(\S+)", p.get("description", ""))
                clave = m.group(1) if m else ""
        out[path.strip("/")] = (op.get("summary", ""), clave)
    return out


def consultar(tabla, filtros=None, select=None, order=None, token=None, max_filas=None):
    """Descarga todas las filas de `tabla` que cumplen `filtros`, paginando de a 1000.

    filtros: dict estilo PostgREST, ej. {"anio": "gte.2024", "region": "eq.Nacional"}
    order:   si no se indica, usa la clave completa de la tabla (orden estable para paginar).
    """
    token = token or os.environ.get("INDEC_TOKEN") or _token_archivo()
    if not token:
        raise SystemExit("Falta el token: definí INDEC_TOKEN o guardalo en ~/indec_token.txt.")
    if order is None:
        order = tablas().get(tabla, ("", ""))[1] or None

    filas, offset = [], 0
    while True:
        params = dict(filtros or {})
        params.update({"limit": PAGE, "offset": offset})
        if select:
            params["select"] = select
        if order:
            params["order"] = order
        url = f"{BASE}/{tabla}?{urllib.parse.urlencode(params, safe=',.*()')}"
        page, headers = _request(url, token, {"Prefer": "count=exact"})
        filas.extend(page)
        total = _total(headers)
        offset += len(page)
        if not page or len(page) < PAGE or (total is not None and offset >= total):
            break
        if max_filas and len(filas) >= max_filas:
            break
    return filas[:max_filas] if max_filas else filas


def _token_archivo():
    ruta = os.path.join(os.path.expanduser("~"), "indec_token.txt")
    try:
        # Set-Content de PowerShell puede dejar BOM o salto de línea
        with open(ruta, encoding="utf-8-sig") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def _total(headers):
    # Content-Range: 0-999/103545
    cr = next((v for k, v in headers.items() if k.lower() == "content-range"), "")
    tail = cr.rpartition("/")[2]
    return int(tail) if tail.isdigit() else None


def a_numero(v):
    """`valor` puede traer signos convencionales del INDEC ('s', '///', '...', '-').

    Devuelve float, 0.0 para '-' (cero absoluto) o None si no hay dato numérico.
    """
    if v is None or isinstance(v, (int, float)):
        return v
    v = str(v).strip().rstrip("*").strip()
    if v == "-":
        return 0.0
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return None


def _main():
    ap = argparse.ArgumentParser(description="Consulta el Catálogo API-INDEC")
    ap.add_argument("tabla", nargs="?", help="nombre del servicio, ej. ipc_nacional")
    ap.add_argument("filtros", nargs="*", help="columna=op.valor, ej. anio=gte.2024")
    ap.add_argument("--list", action="store_true", help="listar servicios disponibles")
    ap.add_argument("--info", metavar="TABLA", help="mostrar columnas y descripción de un servicio")
    ap.add_argument("--select", help="columnas separadas por coma")
    ap.add_argument("--order", help="orden PostgREST (por defecto, la clave completa)")
    ap.add_argument("--max", type=int, help="cantidad máxima de filas")
    ap.add_argument("--csv", help="guardar en CSV en lugar de imprimir JSON")
    a = ap.parse_args()

    if a.list:
        for t, (resumen, _) in tablas().items():
            print(f"{t:55} {resumen}")
        return
    if a.info:
        op = spec()["paths"][f"/{a.info}"]["get"]
        print(op.get("summary", ""), "\n")
        print(op.get("description", "").split("### Ejemplos")[0].strip(), "\n")
        for p in op.get("parameters", []):
            if p.get("in") == "query" and p["name"] not in ("select", "order", "limit", "offset"):
                print(f"  {p['name']:40} {p.get('description', '')[:80]}")
        return
    if not a.tabla:
        ap.error("indicá una tabla o usá --list")

    filtros = dict(f.split("=", 1) for f in a.filtros)
    filas = consultar(a.tabla, filtros, a.select, a.order, max_filas=a.max)
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(filas[0]) if filas else [])
            w.writeheader()
            w.writerows(filas)
        print(f"{len(filas)} filas guardadas en {a.csv}  (Fuente: INDEC, servicio {a.tabla})")
    else:
        json.dump(filas, sys.stdout, ensure_ascii=False, indent=2)
        print()


if __name__ == "__main__":
    _main()
