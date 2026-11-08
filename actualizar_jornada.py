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
        if tabla is None:
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
    if set(partidos) != set(range(1, 16)):
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
    diagnostico = {"consultado": ahora, "fuentes": {}, "publicacion_automatica": False, "motivo": ""}
    candidatos = {}
    for nombre, url, extractor in [
        ("quinielafutbol", SOURCE_A, fuente_quinielafutbol),
        ("quiniprats", SOURCE_B.format(numero=int(json.loads(JORNADA.read_text(encoding="utf-8")).get("numero", 0)) + 1), None),
    ]:
        try:
            parsed = (fuente_quiniprats(descargar(url), int(json.loads(JORNADA.read_text(encoding="utf-8")).get("numero", 0)) + 1) if extractor is None else extractor(descargar(url)))
            diagnostico["fuentes"][nombre] = {"url": url, "accesible": True, "jornadas_completas": sorted(parsed)}
            candidatos[nombre] = parsed
        except Exception as exc:
            diagnostico["fuentes"][nombre] = {"url": url, "accesible": False, "error": str(exc)[:180]}
            candidatos[nombre] = {}
    actual = json.loads(JORNADA.read_text(encoding="utf-8"))
    actual_numero = int(actual.get("numero", 0))
    comunes = sorted(set(candidatos["quinielafutbol"]) & set(candidatos["quiniprats"]))
    validos = [n for n in comunes if coinciden(candidatos["quinielafutbol"][n], candidatos["quiniprats"][n])]
    # Nunca retroceder ni saltar jornadas, ni sobreescribir una jornada que no ha finalizado.
    siguiente = actual_numero + 1
    if siguiente in validos and date.fromisoformat(actual["fecha_fin"]) < date.today():
        candidato = candidatos["quinielafutbol"][siguiente]
        fechas = candidato["fechas"]
        if fechas and fechas[1] >= date.today() and (fechas[1] - fechas[0]).days <= 5:
            partidos = [
                {"posicion": n, "local": candidato["partidos"][n][0],
                 "visitante": candidato["partidos"][n][1], "liga": None}
                for n in range(1, 15)
            ]
            local, visitante = candidato["partidos"][15]
            nueva = {
                "numero": siguiente, "temporada": actual.get("temporada", "2026-2027"),
                "fecha_inicio": fechas[0].isoformat(), "fecha_fin": fechas[1].isoformat(),
                "estado": "verificada",
                "verificacion": "15 encuentros coincidentes en dos fuentes; fechas de QuinielaFutbol.",
                "fuentes": [SOURCE_A, SOURCE_B.format(numero=siguiente)], "partidos": partidos,
                "pleno": {"local": local, "visitante": visitante},
            }
            JORNADA.write_text(json.dumps(nueva, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            diagnostico["publicacion_automatica"] = True
            diagnostico["motivo"] = f"Jornada {siguiente} publicada tras contrastar 15 encuentros."
        else:
            diagnostico["motivo"] = "Coinciden partidos, pero faltan fechas futuras válidas."
    elif actual_numero in validos:
        diagnostico["motivo"] = "Jornada actual coincidente en ambas fuentes. Sin cambios."
    else:
        diagnostico["motivo"] = "Sin coincidencia completa de 15 partidos para la jornada actual."
    diagnostico["jornadas_coincidentes"] = validos
    diagnostico["fuente_independiente_actualizada"] = siguiente in candidatos["quiniprats"]
    diagnostico["nota"] = "Sin coincidencia de dos fuentes no se publican jornadas nuevas. QuiniPrats se consulta para la siguiente jornada."
    # No elevar un estado 'publicable' basándose solo en nombres y enlaces.
    ROOT.mkdir(exist_ok=True)
    (ROOT / "diagnostico_fuentes.json").write_text(json.dumps(diagnostico, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(diagnostico["motivo"])
    print(json.dumps(diagnostico["fuentes"], ensure_ascii=False))

if __name__ == "__main__":
    main()
