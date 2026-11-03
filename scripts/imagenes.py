"""Genera las imágenes para compartir (docs/img/) y los textos sugeridos para X (docs/x/textos.json).

También escribe novedades.md con los posteos de las series que cambiaron, para el aviso
que abre el flujo de GitHub. Las rutas de imagen ahí llevan {BASE} para completar después.

    python scripts/imagenes.py                  # todas las series
    python scripts/imagenes.py ipc desempleo    # solo marca como novedad esas series

SITIO_URL (variable de entorno) es la dirección pública del sitio, para los textos.
"""

import datetime
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(RAIZ, "docs", "data")
IMG = os.path.join(RAIZ, "docs", "img")
X = os.path.join(RAIZ, "docs", "x")
SITIO = os.environ.get("SITIO_URL", "").rstrip("/")

FONDO, TINTA, TENUE, GRILLA = "#F4F6F9", "#132231", "#5B6B7B", "#DCE2E8"
ACENTO, NARANJA, VERDE, VIOLETA = "#1D5C96", "#D0682A", "#2B8566", "#8656BF"
BUENO, MALO = "#1C7547", "#B3362F"

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.edgecolor": GRILLA,
    "axes.labelcolor": TENUE,
    "xtick.color": TENUE,
    "ytick.color": TENUE,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
})


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
        return TENUE
    return BUENO if (v > 0) == mejor_si_sube else MALO


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


# ---------- piezas de las imágenes ----------

def lienzo(alto=6.75):
    fig = plt.figure(figsize=(12, alto), dpi=100)
    fig.patch.set_facecolor(FONDO)
    return fig


def pie(fig):
    fig.text(0.05, 0.05, "Fuente: INDEC · Catálogo API-INDEC", fontsize=12, color=TENUE)
    if SITIO:
        fig.text(0.95, 0.05, SITIO.split("://")[-1], fontsize=12, color=TENUE, ha="right")


def bloque(fig, kicker, periodo, numero, linea1, linea2, color2):
    fig.text(0.05, 0.86, kicker.upper(), fontsize=13, color=TENUE, weight="bold")
    fig.text(0.05, 0.78, periodo[:1].upper() + periodo[1:], fontsize=22, color=TINTA)
    fig.text(0.05, 0.56, numero, fontsize=74, color=TINTA, weight="bold")
    fig.text(0.05, 0.46, linea1, fontsize=16, color=TENUE)
    fig.text(0.05, 0.40, linea2, fontsize=16, color=color2, weight="bold")


def ejes(fig, ancho=0.50):
    ax = fig.add_axes([0.45, 0.17, ancho, 0.66])
    ax.set_facecolor(FONDO)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(GRILLA)
    ax.tick_params(length=0, pad=6)
    ax.grid(axis="y", color=GRILLA, linewidth=1)
    ax.set_axisbelow(True)
    return ax


def anios(ax, fechas):
    idx = [i for i, f in enumerate(fechas) if f.endswith("-01")]
    ax.set_xticks(idx, [fechas[i][:4] for i in idx])


def eje(ax, escala=1, sufijo=""):
    """Rótulos del eje y con los decimales que pide la separación entre marcas (enteras o de a 0,5)."""
    marcas = ax.get_yticks()
    paso = (marcas[1] - marcas[0]) * escala if len(marcas) > 1 else 1
    dec = 0 if abs(paso - round(paso)) < 1e-9 else 1
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{coma(v * escala, dec)}{sufijo}"))


def eje_pct(ax):
    eje(ax, 100, "%")


def guardar(fig, nombre):
    os.makedirs(IMG, exist_ok=True)
    fig.savefig(os.path.join(IMG, nombre), facecolor=FONDO)
    plt.close(fig)


# ---------- imágenes ----------

def img_inflacion(inflacion):
    filas = [r for r in inflacion if r["mensual"] is not None][-24:]
    u, prev = filas[-1], filas[-2]
    fig = lienzo()
    bloque(fig, "Inflación · IPC nacional", mes(u["fecha"], True), pct(u["mensual"]),
           f"mensual · {pct(u['interanual'])} interanual",
           f"{pp(u['mensual'] - prev['mensual'])} contra {mes_solo(prev['fecha'])}",
           tono(u["mensual"] - prev["mensual"], False))
    ax = ejes(fig)
    n = len(filas)
    ax.bar(range(n), [r["mensual"] for r in filas], width=0.72, color=ACENTO, zorder=2)
    for barra in ax.patches[:-1]:
        barra.set_alpha(0.35)
    eje_pct(ax)
    anios(ax, [r["fecha"] for r in filas])
    ax.set_title("Variación mensual, últimos 24 meses", loc="left", fontsize=13, color=TENUE, pad=10)
    pie(fig)
    guardar(fig, "inflacion.png")


def etiquetas_finales(ax, x, valores, colores, textos, separacion):
    orden = sorted(range(len(valores)), key=lambda i: valores[i])
    ys = [valores[i] for i in orden]
    for k in range(1, len(ys)):
        ys[k] = max(ys[k], ys[k - 1] + separacion)
    for k, i in enumerate(orden):
        ax.annotate(textos[i], (x, valores[i]), xytext=(x + 0.8, ys[k]), textcoords="data",
                    fontsize=12, color=colores[i], weight="bold", va="center", annotation_clip=False)


def img_salario(salario_real):
    filas = salario_real[-36:]
    u, prev, hace12 = salario_real[-1], salario_real[-2], salario_real[-13]
    var_a = u["total"] / hace12["total"] - 1
    var_m = u["total"] / prev["total"] - 1
    fig = lienzo()
    bloque(fig, "Salario real", mes(u["fecha"], True), pct(var_a, True),
           "interanual, en términos reales",
           f"{pct(var_m, True)} contra {mes_solo(prev['fecha'])}", tono(var_m, True))
    ax = ejes(fig, 0.39)
    series = (("total", "Total", ACENTO, 3), ("privado_registrado", "Privado reg.", NARANJA, 2),
              ("publico", "Público", VERDE, 2), ("no_registrado", "No registrado", VIOLETA, 2))
    x = range(len(filas))
    for clave, _, color, ancho in series:
        ax.plot(x, [r[clave] for r in filas], color=color, linewidth=ancho, solid_capstyle="round")
    lo = min(r[c] for r in filas for c, *_ in series)
    hi = max(r[c] for r in filas for c, *_ in series)
    etiquetas_finales(ax, len(filas) - 1, [filas[-1][c] for c, *_ in series], [s[2] for s in series],
                      [f"{s[1]} {coma(filas[-1][s[0]])}" for s in series], (hi - lo) * 0.07)
    eje(ax)
    anios(ax, [r["fecha"] for r in filas])
    ax.set_title("Índice de salarios ÷ IPC, diciembre 2016 = 100", loc="left", fontsize=13, color=TENUE, pad=10)
    pie(fig)
    guardar(fig, "salario_real.png")


def img_actividad(actividad):
    filas = actividad[-36:]
    u, prev = actividad[-1], actividad[-2]
    fig = lienzo()
    bloque(fig, "Actividad económica · EMAE", mes(u["fecha"], True), pct(u["interanual"], True),
           "variación interanual",
           f"{pct(u['mensual'], True)} contra {mes_solo(prev['fecha'])}",
           tono(u["mensual"], True))
    ax = ejes(fig)
    x = list(range(len(filas)))
    y = [r["desestacionalizada"] for r in filas]
    piso = min(y) - (max(y) - min(y)) * 0.15
    ax.fill_between(x, y, piso, color=ACENTO, alpha=0.10, linewidth=0)
    ax.plot(x, y, color=ACENTO, linewidth=3, solid_capstyle="round")
    ax.plot([x[-1]], [y[-1]], "o", color=ACENTO, markersize=7)
    ax.set_ylim(bottom=piso)
    eje(ax)
    anios(ax, [r["fecha"] for r in filas])
    ax.set_title("Serie sin estacionalidad, base 2004 = 100", loc="left", fontsize=13, color=TENUE, pad=10)
    pie(fig)
    guardar(fig, "actividad.png")


def img_desocupacion(desocupacion):
    filas = desocupacion[-12:]
    u = filas[-1]
    fig = lienzo()
    bloque(fig, "Desocupación · EPH", trim(u["fecha"]), pct(u["tasa"]),
           "de la población activa",
           f"{pp(u['dif'])} contra un año antes", tono(u["dif"], False))
    ax = ejes(fig)
    n = len(filas)
    ax.bar(range(n), [r["tasa"] for r in filas], width=0.62, color=ACENTO, zorder=2)
    for barra in ax.patches[:-1]:
        barra.set_alpha(0.35)
    eje_pct(ax)
    anios(ax, [r["fecha"] for r in filas])
    ax.set_title("Tasa trimestral, 31 aglomerados urbanos", loc="left", fontsize=13, color=TENUE, pad=10)
    pie(fig)
    guardar(fig, "desocupacion.png")


def img_portada(inflacion, salario_real, actividad, desocupacion):
    i, s, a, d = inflacion[-1], salario_real[-1], actividad[-1], desocupacion[-1]
    sal_a = s["total"] / salario_real[-13]["total"] - 1
    fig = lienzo(6.3)
    fig.text(0.05, 0.80, "Monitor Macro", fontsize=44, color=TINTA, weight="bold")
    fig.text(0.05, 0.71, "Inflación, salarios, actividad y empleo con datos del INDEC",
             fontsize=18, color=TENUE)
    tarjetas = (
        ("Inflación", mes(i["fecha"]), pct(i["mensual"]), f"{pct(i['interanual'])} interanual"),
        ("Salario real", mes(s["fecha"]), pct(sal_a, True), "interanual"),
        ("Actividad (EMAE)", mes(a["fecha"]), pct(a["interanual"], True), "interanual"),
        ("Desocupación", trim(d["fecha"]).replace("trimestre de", "trim."), pct(d["tasa"]), "de la población activa"),
    )
    for k, (titulo, periodo, numero, sub) in enumerate(tarjetas):
        x = 0.05 + k * 0.23
        fig.patches.append(plt.Rectangle((x - 0.012, 0.17), 0.215, 0.43, transform=fig.transFigure,
                                         facecolor="white", edgecolor=GRILLA, linewidth=1))
        fig.text(x, 0.52, titulo, fontsize=15, color=TINTA, weight="bold")
        fig.text(x, 0.46, periodo, fontsize=13, color=TENUE)
        fig.text(x, 0.30, numero, fontsize=40, color=ACENTO, weight="bold")
        fig.text(x, 0.22, sub, fontsize=12, color=TENUE)
    pie(fig)
    guardar(fig, "og.png")


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
         "alt": f"Gráfico de barras de la inflación mensual. {mes(i['fecha'], True).capitalize()}: {pct(i['mensual'])}.",
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
         "alt": f"Gráfico de barras de la desocupación trimestral. {trim(d['fecha'])}: {pct(d['tasa'])}.",
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
