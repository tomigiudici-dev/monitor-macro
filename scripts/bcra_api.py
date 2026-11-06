"""Cliente mínimo para la API de estadísticas del BCRA (https://api.bcra.gob.ar), versión 4.0.

Es pública: no pide token. Solo usa la biblioteca estándar.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.bcra.gob.ar/estadisticas/v4.0/monetarias"
UA = "monitor-macro/0.1 (+python)"
PAGINA = 3000


class ErrorBCRA(Exception):
    pass


def serie(id_variable, desde, hasta):
    """Devuelve [(fecha 'AAAA-MM-DD', valor)] de una variable, ordenado por fecha."""
    filas, offset = [], 0
    while True:
        q = urllib.parse.urlencode({"desde": desde, "hasta": hasta, "limit": PAGINA, "offset": offset})
        req = urllib.request.Request(f"{BASE}/{id_variable}?{q}",
                                     headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.load(r)
        except urllib.error.HTTPError as e:
            raise ErrorBCRA(f"La API del BCRA respondió HTTP {e.code} para la variable {id_variable}") from None
        except OSError as e:  # sin conexión, conexión cortada o tiempo agotado
            raise ErrorBCRA(f"Sin conexión con la API del BCRA: {getattr(e, 'reason', None) or e}") from None
        resultados = d.get("results") or []
        detalle = resultados[0].get("detalle", []) if resultados else []
        filas += [(x["fecha"], x["valor"]) for x in detalle if x.get("valor") is not None]
        total = d.get("metadata", {}).get("resultset", {}).get("count", 0)
        offset += len(detalle)
        if not detalle or offset >= total:
            break
    return sorted(filas)
