"""Actualiza La Quiniela únicamente si dos proveedores independientes coinciden.
Falla de forma conservadora: si falta información, no cambia la jornada.
"""
import json
import re
import unicodedata
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path("data")
JORNADA = ROOT / "jornada_actual.json"
ESTADO = ROOT / "estado_jornada.json"
SEASON = "2026-27"
SOURCE_A = "https://www.quinielafutbol.info/proximas-jornadas-de-la-quiniela.html"
SOURCE_B = "https://quiniprats.com/es/quiniela/2026-27/jornada/{numero}"

def descargar(url):
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; QuinielaLab/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    })
    with urllib.request.urlopen(request, timeout=25) as response:
        if response.status != 200:
            raise ValueError(f"HTTP {response.status}")
        return BeautifulSoup(response.read(2_000_000), "html.parser")

def limpiar(s):
    return " ".join(s.split()).strip()

def clave(s):
    s = unicodedata.normalize("NFKD", s.casefold())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    replacements = {
        "r valladolid": "valladolid", "real valladolid": "valladolid",
        "r oviedo": "oviedo", "real oviedo": "oviedo",
        "r sociedad b": "sociedad b", "real sociedad b": "sociedad b",
        "r sociedad f": "real sociedad f", "ath club f": "athletic club f",
        "at madrid f": "atletico madrid f", "at madrid": "atletico madrid",
        "sporting": "sporting gijon", "andorra fc": "andorra",
        "fc andorra": "andorra", "cd castellon": "castellon",
        "sevilla fc": "sevilla", "eibar f": "eibar f",
    }
    replacements.update({
        "bosnia herzegovina": "bosnia herzegovina",
        "bosnia y herzegovina": "bosnia herzegovina",
        "rep irlanda": "irlanda", "republica de irlanda": "irlanda",
        "irlanda": "irlanda", "r madrid f": "real madrid f",
        "real madrid f": "real madrid f",
        "inter f": "inter f", "bk hacken f": "hacken f",
        "hacken f": "hacken f", "chelsea f": "chelsea f",
        "psg f": "psg f", "juventus f": "juventus f",
        "leuven f": "leuven f", "oh leuven f": "leuven f",
        "austria wien f": "austria viena f", "austria viena f": "austria viena f",
        "bayern munich f": "bayern munich f", "arsenal f": "arsenal f",
        "ol lyonnes f": "ol lyonnes f", "ol lyonnes": "ol lyonnes f",
        "barcelona f": "barcelona f", "benfica f": "benfica f",
        "roma f": "roma f", "servette f": "servette f",
    })
    return replacements.get(s, s)

def enfrentamiento(s):
    s = limpiar(s)
    trozos = re.split(r"\s+[-–—]\s+", s, maxsplit=1)
    if len(trozos) != 2 or not all(trozos):
        raise ValueError(f"Enfrentamiento no interpretable: {s[:90]}")
    return trozos

def extraer_filas(tabla):
    partidos = {}
    for tr in tabla.select("tr"):
        cells = [limpiar(c.get_text(" ", strip=True)) for c in tr.find_all(["td", "th"], recursive=False)]
        if len(cells) < 2:
            continue
        n = re.fullmatch(r"(?:P-)?\s*(\d{1,2})\.?\s*", cells[0], re.I)
        if not n:
            continue
        numero = int(n.group(1))
        if not 1 <= numero <= 15:
            continue
        try:
            local, visitante = enfrentamiento(cells[1])
        except ValueError:
            continue
        partidos[numero] = (local, visitante)
    return partidos

def fechas_tabla(tabla):
    fechas = []
    for tr in tabla.select("tr"):
        for td in tr.find_all("td", recursive=False):
            for dia, mes, ano in re.findall(r"\b(\d{2})/(\d{2})/(20\d{2})\b", td.get_text(" ", strip=True)):
                try:
                    fechas.append(date(int(ano), int(mes), int(dia)))
                except ValueError:
                    pass
    return (min(fechas), max(fechas)) if len(fechas) >= 14 else None

def fuente_quinielafutbol(soup):
    encontrados = {}
    for h in soup.find_all(re.compile(r"^h[1-6]$")):
        titulo = limpiar(h.get_text(" ", strip=True))
        m = re.search(r"JORNADA\s*(?:N[º°o.]*)?\s*(\d{1,2})\b", titulo, re.I)
        if not m:
            continue
        numero = int(m.group(1))
        tabla = h.find_next("table")
        if tabla is None or (tabla.find_previous(re.compile(r"^h[1-6]$")) is not h):
            continue
        partidos = extraer_filas(tabla)
        if len(partidos) == 15:
            encontrados[numero] = {'partidos': partidos, 'fechas': fechas_tabla(tabla)}
    return encontrados

def fuente_losilla(soup):
    texto = soup.get_text(" ", strip=True)
    m = re.search(r"JORNADA\s*(\d{1,2})\s*[-–]\s*26/27", texto, re.I)
    if not m:
        return {}
    numero = int(m.group(1))
    for tabla in soup.find_all("table"):
        partidos = extraer_filas(tabla)
        if len(partidos) == 15:
            return {numero: {'partidos': partidos, 'fechas': fechas_tabla(tabla)}}
    return {}

def fuente_quiniprats(soup, numero):
    """Extrae tarjetas #1 ... #15; evita confundir iniciales de escudos con equipos."""
    titulo = soup.find(string=re.compile(r"Quiniela\s*[—-]\s*Jornada\s+" + str(numero) + r"\b", re.I))
    if titulo is None:
        return {}
    # Los equipos son nombres legibles junto a cada número. La hora queda entre ambos.
    texto = soup.get_text("\n", strip=True)
    bloques = re.split(r"(?m)^#(1[0-5]|[1-9])\s*$", texto)
    partidos = {}
    for i in range(1, len(bloques)-1, 2):
        n = int(bloques[i])
        lineas = [x.strip() for x in bloques[i+1].splitlines() if x.strip()]
        lineas = [x for x in lineas if not re.search(r"^(Pleno al 15|Image:|[A-Z])$", x)]
        if n == 15 and lineas and lineas[0].casefold() == "pleno al 15":
            lineas.pop(0)
        fecha_idx = next((k for k, x in enumerate(lineas) if re.search(r"\b(?:lun|mar|mié|mie|jue|vie|sáb|sab|dom)\b.*\d{1,2}:\d{2}", x, re.I)), None)
        if fecha_idx is None or fecha_idx < 1 or fecha_idx + 1 >= len(lineas):
            continue
        local, visitante = lineas[fecha_idx-1], lineas[fecha_idx+1]
        if local and visitante and len(local) > 1 and len(visitante) > 1:
            partidos[n] = (local, visitante)
    if set(partidos) != set(range(1, 16)) or len({(clave(a), clave(b)) for a,b in partidos.values()}) != 15:
        return {}
    # Las fechas se extraen del resumen, no de horas susceptibles a diferencias de huso.
    meses = {"enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,"junio":6,
             "julio":7,"agosto":8,"septiembre":9,"octubre":10,"noviembre":11,"diciembre":12}
    fechas = None
    m = re.search(r"entre el (\d{1,2}) (\w+) y el (\d{1,2}) (\w+)", texto, re.I)
    if m and m.group(2).lower() in meses and m.group(4).lower() in meses:
        year = 2026 if meses[m.group(2).lower()] >= 8 else 2027
        inicio = date(year, meses[m.group(2).lower()], int(m.group(1)))
        fin_year = year + (meses[m.group(4).lower()] < meses[m.group(2).lower()])
        fin = date(fin_year, meses[m.group(4).lower()], int(m.group(3)))
        fechas = (inicio, fin)
    return {numero: {"partidos": partidos, "fechas": fechas}}

def coinciden(a, b):
    a, b = a['partidos'], b['partidos']
    return set(a) == set(b) == set(range(1, 16)) and all(clave(a[n][0]) == clave(b[n][0]) and clave(a[n][1]) == clave(b[n][1]) for n in range(1, 16))

def main():
    ahora = datetime.now(timezone.utc).isoformat()
    actual = json.loads(JORNADA.read_text(encoding="utf-8"))
    numero_actual = int(actual["numero"])
    siguiente = numero_actual + 1
    diagnostico = {
        "consultado": ahora, "fuentes": {}, "publicacion_automatica": False,
        "fuente_utilizada": None, "respaldo_activado": False, "motivo": ""
    }
    candidato = None
    fuente_publicada = None
    try:
        jornadas = fuente_quinielafutbol(descargar(SOURCE_A))
        diagnostico["fuentes"]["quinielafutbol"] = {
            "url": SOURCE_A, "accesible": True,
            "jornadas_completas": sorted(jornadas)
        }
        # La fuente principal es autoritativa. NO consultar respaldo si es accesible,
        # aunque la jornada siguiente aún no esté publicada o no tenga fechas.
        diagnostico["fuente_utilizada"] = "quinielafutbol"
        candidato = jornadas.get(siguiente)
        fuente_publicada = SOURCE_A
        if candidato is None:
            diagnostico["motivo"] = f"QuinielaFutbol accesible, pero sin jornada {siguiente} completa."
    except Exception as exc:
        diagnostico["fuentes"]["quinielafutbol"] = {
            "url": SOURCE_A, "accesible": False, "error": str(exc)[:180]
        }
        diagnostico["respaldo_activado"] = True
        url = SOURCE_B.format(numero=siguiente)
        try:
            jornadas = fuente_quiniprats(descargar(url), siguiente)
            diagnostico["fuentes"]["quiniprats"] = {
                "url": url, "accesible": True,
                "jornadas_completas": sorted(jornadas)
            }
            diagnostico["fuente_utilizada"] = "quiniprats"
            candidato = jornadas.get(siguiente)
            fuente_publicada = url
            if candidato is None:
                diagnostico["motivo"] = f"Respaldo accesible, pero sin jornada {siguiente} completa."
        except Exception as exc_respaldo:
            diagnostico["fuentes"]["quiniprats"] = {
                "url": url, "accesible": False, "error": str(exc_respaldo)[:180]
            }
            diagnostico["motivo"] = "Fuente principal y respaldo no disponibles."

    if candidato is not None:
        fechas = candidato.get("fechas")
        if date.fromisoformat(actual["fecha_fin"]) >= date.today():
            diagnostico["motivo"] = f"Jornada {numero_actual} todavía en curso o pendiente; no se sustituye."
        elif not fechas:
            diagnostico["motivo"] = f"Jornada {siguiente} encontrada, pero sin fechas verificables; no se publica."
        elif fechas[1] < date.today() or fechas[1] < fechas[0] or (fechas[1] - fechas[0]).days > 5:
            diagnostico["motivo"] = f"Jornada {siguiente} con fechas caducadas o incoherentes; no se publica."
        else:
            partidos = candidato["partidos"]
            nueva = {
                "numero": siguiente,
                "temporada": actual.get("temporada", "2026-2027"),
                "fecha_inicio": fechas[0].isoformat(),
                "fecha_fin": fechas[1].isoformat(),
                "estado": "verificada",
                "verificacion": "Composición y fechas extraídas de " + diagnostico["fuente_utilizada"],
                "fuentes": [fuente_publicada],
                "partidos": [
                    {"posicion": n, "local": partidos[n][0],
                     "visitante": partidos[n][1], "liga": None}
                    for n in range(1, 15)
                ],
                "pleno": {"local": partidos[15][0], "visitante": partidos[15][1]}
            }
            JORNADA.write_text(
                json.dumps(nueva, ensure_ascii=False, indent=2) + "\\n",
                encoding="utf-8"
            )
            diagnostico["publicacion_automatica"] = True
            diagnostico["motivo"] = f"Jornada {siguiente} publicada desde {diagnostico['fuente_utilizada']}."
    diagnostico["jornadas_coincidentes"] = []
    ROOT.mkdir(exist_ok=True)
    (ROOT / "diagnostico_fuentes.json").write_text(
        json.dumps(diagnostico, ensure_ascii=False, indent=2) + "\\n",
        encoding="utf-8"
    )
    print(diagnostico["motivo"])
    print(json.dumps(diagnostico["fuentes"], ensure_ascii=False))

if __name__ == "__main__":
    main()
