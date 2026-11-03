"""Genera las imágenes para compartir (docs/img/) y los textos sugeridos para X (docs/x/textos.json).

También escribe novedades.md con los posteos de las series que cambiaron, para el aviso
que abre el flujo de GitHub. Las rutas de imagen ahí llevan {BASE} para completar después.

    python scripts/imagenes.py                  # todas las series
    python scripts/imagenes.py ipc desempleo    # solo marca como novedad esas series

SITIO_URL (variable de entorno) es la dirección pública del sitio, para los textos.
Las imágenes se dibujan en píxeles (origen arriba a la izquierda), con las tipografías
de scripts/fuentes/ (Archivo, Chivo y Chivo Mono, de Omnibus-Type, licencia OFL).
"""

import datetime
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(RAIZ, "docs", "data")
IMG = os.path.join(RAIZ, "docs", "img")
X = os.path.join(RAIZ, "docs", "x")
FUENTES = os.path.join(RAIZ, "scripts", "fuentes")
SITIO = os.environ.get("SITIO_URL", "").rstrip("/")

# Paleta del diseño
FONDO, PANEL, TINTA, TEXTO2, TENUE = "#F3F6F8", "#FFFFFF", "#0D2131", "#33495B", "#4F6475"
BORDE, GRILLA, EJE, BORDE_FUERTE = "#DCE3E9", "#E8EDF1", "#9DAEBB", "#C5D1DB"
ACENTO, BARRA, SOL = "#1F67A8", "#B9D4EC", "#F6B40E"
S_PRIV, S_PUB, S_NOREG = "#2F7DC1", "#E0A10B", "#8E5BB8"
BUENO, MALO = "#1C6B44", "#9A2F25"
NAVY_PANEL, CELESTE, GRIS_NAVY, SPARK_NAVY = "#16324A", "#9CC3E6", "#B8CCDD", "#5E9BD3"

F = {n: FontProperties(fname=os.path.join(FUENTES, f"{a}.ttf")) for n, a in {
    "texto": "Archivo-Regular", "medio": "Archivo-Medium", "semi": "Archivo-SemiBold", "negrita": "Archivo-Bold",
    "num": "Chivo-Bold", "num_extra": "Chivo-ExtraBold", "mono": "ChivoMono-Regular", "mono_medio": "ChivoMono-Medium",
}.items()}

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


# ---------- formato ----------

def coma(x, dec=1):
    return f"{x:.{dec}f}".replace(".", ",")


def pct(v, signo=False):
    s = "+" if signo and v > 0 else "−" if v < 0 else ""
    return f"{s}{coma(abs(v) * 100)}%"


def pp(v):
    s = "+" if v > 0 else "−" if v < 0 else ""
    return f"{s}{coma(abs(v) * 100)} p.p."


def mes(f, articulo=False):
    y, m = f.split("-")
    return f"{MESES[int(m) - 1]} de {y}" if articulo else f"{MESES[int(m) - 1]} {y}"


def mes_solo(f):
    return MESES[int(f.split("-")[1]) - 1]


def trim(f):
    y, m = f.split("-")
    return f"{(int(m) - 1) // 3 + 1}.º trimestre de {y}"


def tono(v, mejor_si_sube):
    if not v:
        return TINTA
    return BUENO if (v > 0) == mejor_si_sube else MALO


def mayuscula(s):
    return s[:1].upper() + s[1:]


# ---------- datos ----------

def leer(nombre):
    with open(os.path.join(DATOS, f"{nombre}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def derivar():
    ipc, salarios, emae, desempleo = (leer(n) for n in ("ipc", "salarios", "emae", "desempleo"))
    inflacion = [{"fecha": r["fecha"],
                  "mensual": None if r["v_m"] is None else r["v_m"] / 100,
                  "interanual": None if r["v_ia"] is None else r["v_ia"] / 100} for r in ipc]
    precios = {r["fecha"]: r["ipc"] / 100 for r in ipc}
    base = next(r for r in salarios if r["fecha"] == "2016-12")
    sectores = ("total", "privado_registrado", "publico", "no_registrado")
    salario_real = [{"fecha": r["fecha"], **{s: r[s] / base[s] / precios[r["fecha"]] * 100 for s in sectores}}
                    for r in salarios if r["fecha"] in precios]
    actividad = [{"fecha": r["fecha"], "desestacionalizada": r["desestacionalizada"],
                  "mensual": r["v_m"] / 100, "interanual": r["v_ia"] / 100} for r in emae]
    desocupacion = [{"fecha": r["fecha"], "tasa": r["tasa"],
                     "dif": r["tasa"] - desempleo[i - 4]["tasa"] if i >= 4 else None}
                    for i, r in enumerate(desempleo)]
    return inflacion, salario_real, actividad, desocupacion


# ---------- lienzo en píxeles ----------

def pt(px):
    """Tamaño de letra en puntos para que mida `px` píxeles a 100 dpi."""
    return px * 0.72


class Lienzo:
    def __init__(self, ancho, alto, fondo):
        self.fig = plt.figure(figsize=(ancho / 100, alto / 100), dpi=100)
        self.fig.patch.set_facecolor(fondo)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, ancho)
        self.ax.set_ylim(alto, 0)  # y crece hacia abajo, como en el diseño
        self.ax.axis("off")
        self.fondo = fondo
        self.render = self.fig.canvas.get_renderer()

    def texto(self, x, y, s, fuente, px, color, ha="left", va="baseline", z=3):
        return self.ax.text(x, y, s, fontproperties=fuente, fontsize=pt(px), color=color, ha=ha, va=va, zorder=z)

    def ancho(self, t):
        return t.get_window_extent(self.render).width

    def caja(self, t):
        """Caja del texto en coordenadas del lienzo: (x0, arriba, x1, abajo)."""
        (x0, y0), (x1, y1) = self.ax.transData.inverted().transform(t.get_window_extent(self.render).get_points())
        return x0, min(y0, y1), x1, max(y0, y1)

    def rect(self, x, y, w, h, color, radio=0, borde=None, z=1):
        if radio:
            p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={radio}",
                               facecolor=color, edgecolor=borde or "none", linewidth=1 if borde else 0, zorder=z)
        else:
            p = Rectangle((x, y), w, h, facecolor=color, edgecolor=borde or "none", linewidth=1 if borde else 0, zorder=z)
        self.ax.add_patch(p)

    def linea(self, xs, ys, color, ancho=1.0, z=2, **kw):
        self.ax.plot(xs, ys, color=color, linewidth=ancho * 0.72, zorder=z, solid_capstyle="round",
                     solid_joinstyle="round", **kw)

    def punto(self, x, y, color, radio, borde=None, z=4):
        self.ax.add_patch(plt.Circle((x, y), radio, facecolor=color, edgecolor=borde or "none",
                                     linewidth=1.5 if borde else 0, zorder=z))

    def guardar(self, nombre):
        os.makedirs(IMG, exist_ok=True)
        self.fig.savefig(os.path.join(IMG, nombre), facecolor=self.fondo)
        plt.close(self.fig)


def logo(lz, x, y, lado, fondo=TINTA, barras=CELESTE):
    k = lado / 28
    lz.rect(x, y, lado, lado, fondo, radio=7 * k, z=3)
    for bx, by, bh, c in ((6, 15, 7, barras), (12, 10, 12, barras), (18, 6, 16, SOL)):
        lz.rect(x + bx * k, y + by * k, 4 * k, bh * k, c, radio=1 * k, z=4)


def escala(lo, hi, y_abajo, y_arriba, nbins=4):
    """Marcas redondas entre lo y hi y la función que pasa un valor a píxeles."""
    marcas = [m for m in MaxNLocator(nbins=nbins).tick_values(lo, hi)]
    lo, hi = min(marcas[0], lo), max(marcas[-1], hi)
    return marcas, (lambda v: y_abajo - (v - lo) / (hi - lo) * (y_abajo - y_arriba))


def rotulos_eje(marcas):
    paso = marcas[1] - marcas[0]
    return 0 if abs(paso - round(paso)) < 1e-9 else 1


def grilla(lz, marcas, ypx, x0, x1, fmt):
    for m in marcas:
        es_base = m == marcas[0]
        lz.linea([x0, x1], [ypx(m), ypx(m)], EJE if es_base else GRILLA, ancho=2 if es_base else 1, z=1)
        lz.texto(x0 - 10, ypx(m) + 5, fmt(m), F["mono"], 15, TENUE, ha="right")


def anios(lz, fechas, xpos, y):
    for i, f in enumerate(fechas):
        if f.endswith("-01"):
            lz.texto(xpos(i), y, f[:4], F["mono"], 15, TENUE, ha="center")


def etiqueta(lz, x, y, s, x_max):
    """Chip amarillo con el último valor, centrado en x y apoyado sobre y."""
    t = lz.texto(0, 0, s, F["mono_medio"], 15, TINTA, ha="center")
    w = lz.ancho(t) + 16
    cx = min(x, x_max - w / 2)
    t.set_position((cx, y - 12))
    lz.rect(cx - w / 2, y - 32, w, 26, SOL, radio=8, z=2)


def barras(lz, caja, valores, fechas, fmt, rotulo):
    x0, y0, x1, y1 = caja
    marcas, ypx = escala(0, max(valores), y1, y0 + 34)
    dec = rotulos_eje([m * 100 for m in marcas]) if fmt == "pct" else rotulos_eje(marcas)
    f = (lambda m: f"{coma(m * 100, dec)}%") if fmt == "pct" else (lambda m: coma(m, dec))
    xg = x0 + 48
    grilla(lz, marcas, ypx, xg, x1, f)
    n = len(valores)
    paso = (x1 - xg - 8) / n
    bw = paso * 0.76
    xpos = lambda i: xg + 4 + paso * i + paso / 2  # noqa: E731
    for i, v in enumerate(valores):
        lz.rect(xpos(i) - bw / 2, ypx(v), bw, ypx(0) - ypx(v), ACENTO if i == n - 1 else BARRA, radio=min(4, bw / 2), z=2)
    etiqueta(lz, xpos(n - 1), ypx(valores[-1]), rotulo, x1 + 18)
    anios(lz, fechas, xpos, y1 + 28)


def lineas(lz, caja, series, fechas, finales=None, area=False):
    """series: [(valores, color, ancho)]; finales: rótulos al final de cada serie."""
    x0, y0, x1, y1 = caja
    todos = [v for vals, _, _ in series for v in vals]
    lo, hi = min(todos), max(todos)
    pad = (hi - lo) * 0.08
    marcas, ypx = escala(lo - pad, hi + pad, y1, y0 + 10)
    dec = rotulos_eje(marcas)
    xg = x0 + 48
    ancho_fin = 0
    if finales:
        for s in finales:
            t = lz.texto(0, 0, s, F["semi"], 15, TINTA)
            ancho_fin = max(ancho_fin, lz.ancho(t) + 18)
            t.remove()
    xf = x1 - ancho_fin
    grilla(lz, marcas, ypx, xg, xf, lambda m: coma(m, dec))
    n = len(fechas)
    xpos = lambda i: xg + 6 + (xf - xg - 12) * i / (n - 1)  # noqa: E731
    if area:
        vals, color, _ = series[0]
        lz.ax.fill_between([xpos(i) for i in range(n)], [ypx(v) for v in vals], ypx(marcas[0]),
                           color=color, alpha=0.14, linewidth=0, zorder=1)
    for vals, color, ancho in reversed(series):
        lz.linea([xpos(i) for i in range(n)], [ypx(v) for v in vals], color, ancho=ancho, z=2)
        lz.punto(xpos(n - 1), ypx(vals[-1]), color, 5 if ancho > 2.5 else 4, borde=PANEL if ancho > 2.5 else None)
    if finales:
        ys = sorted(((ypx(vals[-1]), k) for k, (vals, _, _) in enumerate(series)))
        pos = []
        for y, k in ys:
            y = max(y, pos[-1][0] + 20) if pos else y
            pos.append((y, k))
        for y, k in pos:
            lz.texto(xf + 14, y + 5, finales[k], F["semi"], 15, series[k][1])
    anios(lz, fechas, xpos, y1 + 28)


# ---------- tarjeta para X (1200 × 675) ----------

def tarjeta(nombre, eyebrow, periodo, numero, sub, filas, titulo, grafico):
    lz = Lienzo(1200, 675, FONDO)
    logo(lz, 64, 52, 30)
    lz.texto(106, 75, "Monitor Macro", F["num_extra"], 22, TINTA)
    lz.texto(64, 140, eyebrow.upper(), F["negrita"], 17, ACENTO)
    lz.texto(64, 186, mayuscula(periodo), F["medio"], 34, TINTA)

    # Número grande, achicado si no entra en la columna, con el resaltador amarillo detrás
    t = lz.texto(64, 352, numero, F["num_extra"], 168, TINTA)
    w = lz.ancho(t)
    if w > 440:
        t.set_fontsize(pt(168 * 440 / w))
    # El resaltador va de la mitad de las cifras hasta apenas debajo de la línea base (352),
    # sin bajar hasta la coma, para no tapar la frase de abajo.
    tam = t.get_fontsize() / 0.72
    x0, _, x1, _ = lz.caja(t)
    lz.rect(x0 - 6, 352 - tam * 0.34, x1 - x0 + 12, tam * 0.42, SOL, z=2)

    lz.texto(64, 398, sub, F["texto"], 22, TEXTO2)
    for k, (valor, texto, color) in enumerate(filas):
        y = 486 + k * 56
        lz.linea([64, 494], [y - 34, y - 34], BORDE_FUERTE, ancho=1, z=1)
        lz.texto(64, y, valor, F["num"], 22, color)
        lz.texto(208, y, texto, F["texto"], 22, TEXTO2)

    lz.rect(542, 52, 594, 523, PANEL, radio=20, borde=BORDE, z=0.5)
    lz.texto(570, 98, titulo, F["semi"], 18, TINTA)
    grafico(lz, (570, 112, 1108, 520))

    lz.rect(0, 611, 1200, 64, TINTA, z=1)
    a = lz.texto(64, 650, "Fuente: ", F["texto"], 19, "#D6E3EE")
    b = lz.texto(64 + lz.ancho(a), 650, "INDEC", F["semi"], 19, "#FFFFFF")
    lz.texto(64 + lz.ancho(a) + lz.ancho(b), 650, " · Catálogo API-INDEC", F["texto"], 19, "#D6E3EE")
    if SITIO:
        lz.texto(1136, 650, SITIO.split("://")[-1], F["mono"], 19, CELESTE, ha="right")
    lz.guardar(nombre)


def img_inflacion(inflacion):
    filas = [r for r in inflacion if r["mensual"] is not None][-24:]
    u, prev = filas[-1], filas[-2]
    dif = u["mensual"] - prev["mensual"]
    tarjeta("inflacion.png", "Inflación · IPC nacional", mes(u["fecha"], True), pct(u["mensual"]),
            "de aumento en el mes",
            [(pct(u["interanual"]), "en doce meses", TINTA), (pp(dif), f"contra {mes_solo(prev['fecha'])}", tono(dif, False))],
            "Inflación mensual, últimos 24 meses",
            lambda lz, caja: barras(lz, caja, [r["mensual"] for r in filas], [r["fecha"] for r in filas], "pct", pct(u["mensual"])))


def img_salario(salario_real):
    filas = salario_real[-36:]
    u, prev, hace12 = salario_real[-1], salario_real[-2], salario_real[-13]
    var_m = u["total"] / prev["total"] - 1
    series = [([r["total"] for r in filas], TINTA, 3.5), ([r["no_registrado"] for r in filas], S_NOREG, 2.5),
              ([r["privado_registrado"] for r in filas], S_PRIV, 2.5), ([r["publico"] for r in filas], S_PUB, 2.5)]
    nombres = ("Total", "No reg.", "Privado reg.", "Público")
    tarjeta("salario_real.png", "Salario real", mes(u["fecha"], True), pct(u["total"] / hace12["total"] - 1, True),
            "en doce meses, descontada la inflación",
            [(pct(var_m, True), f"contra {mes_solo(prev['fecha'])}", tono(var_m, True)), (coma(u["total"]), "índice, dic. 2016 = 100", TINTA)],
            "Índice de salarios ÷ IPC, por sector",
            lambda lz, caja: lineas(lz, caja, series, [r["fecha"] for r in filas],
                                    finales=[f"{n} {coma(s[0][-1])}" for n, s in zip(nombres, series)]))


def img_actividad(actividad):
    filas = actividad[-36:]
    u, prev = actividad[-1], actividad[-2]
    tarjeta("actividad.png", "Actividad económica · EMAE", mes(u["fecha"], True), pct(u["interanual"], True),
            "variación interanual",
            [(pct(u["mensual"], True), f"contra {mes_solo(prev['fecha'])}", tono(u["mensual"], True)),
             (coma(u["desestacionalizada"]), "índice, base 2004 = 100", TINTA)],
            "Serie sin estacionalidad, últimos 3 años",
            lambda lz, caja: lineas(lz, caja, [([r["desestacionalizada"] for r in filas], S_PRIV, 3)],
                                    [r["fecha"] for r in filas], finales=[coma(u["desestacionalizada"])], area=True))


def img_desocupacion(desocupacion):
    filas = desocupacion[-12:]
    u, hace4 = desocupacion[-1], desocupacion[-5]
    tarjeta("desocupacion.png", "Desocupación · EPH", trim(u["fecha"]), pct(u["tasa"]),
            "de la población activa",
            [(pp(u["dif"]), "contra un año antes", tono(u["dif"], False)),
             (pct(hace4["tasa"]), f"en el {trim(hace4['fecha']).replace('trimestre de', 'trim.')}", TINTA)],
            "Tasa trimestral, 31 aglomerados urbanos",
            lambda lz, caja: barras(lz, caja, [r["tasa"] for r in filas], [r["fecha"] for r in filas], "pct", pct(u["tasa"])))


# ---------- portada para links (1200 × 630) ----------

def chispa(lz, x, y, valores):
    lo, hi = min(valores), max(valores)
    n = len(valores)
    xs = [x + 3 + i * 114 / (n - 1) for i in range(n)]
    ys = [y + 33 - (v - lo) / (hi - lo) * 30 for v in valores]
    lz.linea(xs, ys, SPARK_NAVY, ancho=2.5, z=3)
    lz.punto(xs[-1], ys[-1], SOL, 4.5)


def img_portada(inflacion, salario_real, actividad, desocupacion):
    i, s, a, d = inflacion[-1], salario_real[-1], actividad[-1], desocupacion[-1]
    lz = Lienzo(1200, 630, TINTA)
    logo(lz, 64, 52, 34, fondo="#FFFFFF", barras=S_PRIV)
    lz.texto(110, 79, "Monitor Macro", F["num_extra"], 26, "#FFFFFF")
    lz.texto(64, 176, "Inflación, salarios, actividad y empleo", F["num_extra"], 56, "#FFFFFF")
    lz.texto(64, 222, "Con datos oficiales del INDEC, actualizados con cada publicación.", F["texto"], 23, GRIS_NAVY)
    tarjetas = (
        ("Inflación", mes(i["fecha"]), pct(i["mensual"]),
         [r["mensual"] for r in inflacion if r["mensual"] is not None][-24:]),
        ("Salario real", f"{mes(s['fecha'])}, interanual", pct(s["total"] / salario_real[-13]["total"] - 1, True),
         [r["total"] for r in salario_real[-24:]]),
        ("Actividad (EMAE)", f"{mes(a['fecha'])}, interanual", pct(a["interanual"], True),
         [r["desestacionalizada"] for r in actividad[-24:]]),
        ("Desocupación", trim(d["fecha"]).replace("trimestre de", "trimestre"), pct(d["tasa"]),
         [r["tasa"] for r in desocupacion[-12:]]),
    )
    for k, (titulo, periodo, numero, serie) in enumerate(tarjetas):
        x = 64 + k * 272
        lz.rect(x, 300, 256, 236, NAVY_PANEL, radio=16, z=1)
        lz.texto(x + 22, 336, titulo, F["semi"], 17, CELESTE)
        lz.texto(x + 22, 362, periodo, F["texto"], 15, "#A8BDCD")
        lz.texto(x + 22, 438, numero, F["num"], 50, "#FFFFFF")
        chispa(lz, x + 22, 470, serie)
    a = lz.texto(64, 590, "Fuente: ", F["texto"], 17, GRIS_NAVY)
    b = lz.texto(64 + lz.ancho(a), 590, "INDEC", F["semi"], 17, "#FFFFFF")
    lz.texto(64 + lz.ancho(a) + lz.ancho(b), 590, " · Sitio independiente", F["texto"], 17, GRIS_NAVY)
    if SITIO:
        lz.texto(1136, 590, SITIO.split("://")[-1], F["mono"], 17, CELESTE, ha="right")
    lz.guardar("og.png")


# ---------- textos para X ----------

def textos(inflacion, salario_real, actividad, desocupacion):
    cierre = "\n\nFuente: INDEC" + (f"\n{SITIO}" if SITIO else "")
    i, ip = inflacion[-1], inflacion[-2]
    s, sp, s12 = salario_real[-1], salario_real[-2], salario_real[-13]
    a, ap = actividad[-1], actividad[-2]
    d = desocupacion[-1]
    return [
        {"id": "inflacion", "serie": "ipc", "titulo": f"Inflación de {mes(i['fecha'], True)}",
         "imagen": "img/inflacion.png",
         "alt": f"Gráfico de barras de la inflación mensual. {mayuscula(mes(i['fecha'], True))}: {pct(i['mensual'])}.",
         "texto": (f"Inflación de {mes(i['fecha'], True)}: {pct(i['mensual'])} mensual "
                   f"({pp(i['mensual'] - ip['mensual'])} contra {mes_solo(ip['fecha'])}) "
                   f"y {pct(i['interanual'])} interanual.") + cierre},
        {"id": "salario_real", "serie": "salarios", "titulo": f"Salario real de {mes(s['fecha'], True)}",
         "imagen": "img/salario_real.png",
         "alt": f"Gráfico de líneas del salario real por sector hasta {mes(s['fecha'], True)}.",
         "texto": (f"Salario real en {mes(s['fecha'], True)}: {pct(s['total'] / s12['total'] - 1, True)} "
                   f"en doce meses y {pct(s['total'] / sp['total'] - 1, True)} contra {mes_solo(sp['fecha'])}. "
                   f"Índice de salarios del INDEC descontada la inflación.") + cierre},
        {"id": "actividad", "serie": "emae", "titulo": f"Actividad económica de {mes(a['fecha'], True)}",
         "imagen": "img/actividad.png",
         "alt": f"Gráfico de línea del EMAE desestacionalizado hasta {mes(a['fecha'], True)}.",
         "texto": (f"Actividad económica (EMAE) en {mes(a['fecha'], True)}: {pct(a['interanual'], True)} "
                   f"interanual y {pct(a['mensual'], True)} contra {mes_solo(ap['fecha'])}, "
                   f"sin estacionalidad.") + cierre},
        {"id": "desocupacion", "serie": "desempleo", "titulo": f"Desocupación del {trim(d['fecha'])}",
         "imagen": "img/desocupacion.png",
         "alt": f"Gráfico de barras de la desocupación trimestral. {mayuscula(trim(d['fecha']))}: {pct(d['tasa'])}.",
         "texto": (f"Desocupación del {trim(d['fecha'])}: {pct(d['tasa'])}, "
                   f"{pp(d['dif'])} contra un año antes (EPH, 31 aglomerados urbanos).") + cierre},
    ]


def main():
    cambios = set(sys.argv[1:]) or {"ipc", "salarios", "emae", "desempleo"}
    inflacion, salario_real, actividad, desocupacion = derivar()
    img_inflacion(inflacion)
    img_salario(salario_real)
    img_actividad(actividad)
    img_desocupacion(desocupacion)
    img_portada(inflacion, salario_real, actividad, desocupacion)

    items = textos(inflacion, salario_real, actividad, desocupacion)
    ahora = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    os.makedirs(X, exist_ok=True)
    with open(os.path.join(X, "textos.json"), "w", encoding="utf-8") as fh:
        json.dump({"generado": ahora, "items": items}, fh, ensure_ascii=False, indent=1)

    nuevos = [it for it in items if it["serie"] in cambios]
    with open(os.path.join(RAIZ, "novedades.md"), "w", encoding="utf-8") as fh:
        fh.write("Hay datos nuevos del INDEC. Textos e imágenes listos para publicar:\n")
        for it in nuevos:
            fh.write(f"\n### {it['titulo']}\n\n```\n{it['texto']}\n```\n\n![{it['alt']}]({{BASE}}{it['imagen']})\n")
    for it in items:
        print(f"{it['id']}: {len(it['texto'])} caracteres{' (novedad)' if it in nuevos else ''}")


if __name__ == "__main__":
    main()
