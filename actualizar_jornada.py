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
SOURCE_B = "https://www.eduardolosilla.es/quiniela/ayudas/horarios"

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
            encontrados[numero] = partidos
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
            return {numero: partidos}
    return {}

def coinciden(a, b):
    return all(clave(a[n][0]) == clave(b[n][0]) and clave(a[n][1]) == clave(b[n][1]) for n in range(1, 16))

def main():
    ahora = datetime.now(timezone.utc).isoformat()
    diagnostico = {"consultado": ahora, "fuentes": {}, "publicacion_automatica": False, "motivo": ""}
    candidatos = {}
    for nombre, url, extractor in [
        ("quinielafutbol", SOURCE_A, fuente_quinielafutbol),
        ("eduardolosilla", SOURCE_B, fuente_losilla),
    ]:
        try:
            parsed = extractor(descargar(url))
            diagnostico["fuentes"][nombre] = {"url": url, "accesible": True, "jornadas_completas": sorted(parsed)}
            candidatos[nombre] = parsed
        except Exception as exc:
            diagnostico["fuentes"][nombre] = {"url": url, "accesible": False, "error": str(exc)[:180]}
            candidatos[nombre] = {}
    actual = json.loads(JORNADA.read_text(encoding="utf-8"))
    actual_numero = int(actual.get("numero", 0))
    comunes = sorted(set(candidatos["quinielafutbol"]) & set(candidatos["eduardolosilla"]))
    validos = [n for n in comunes if coinciden(candidatos["quinielafutbol"][n], candidatos["eduardolosilla"][n])]
    # Nunca retroceder ni saltar jornadas, ni sobreescribir una jornada que no ha finalizado.
    siguiente = actual_numero + 1
    if siguiente in validos and date.fromisoformat(actual["fecha_fin"]) < date.today():
        diagnostico["motivo"] = ("Jornada siguiente coincidente, pero no publicada: "
            "las fuentes no proporcionan fechas de inicio y fin contrastadas mediante este extractor.")
    elif actual_numero in validos:
        diagnostico["motivo"] = "Jornada actual coincidente en ambas fuentes. Sin cambios."
    else:
        diagnostico["motivo"] = "Sin coincidencia completa de 15 partidos para la jornada actual."
    diagnostico["jornadas_coincidentes"] = validos
    # No elevar un estado 'publicable' basándose solo en nombres y enlaces.
    ROOT.mkdir(exist_ok=True)
    (ROOT / "diagnostico_fuentes.json").write_text(json.dumps(diagnostico, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(diagnostico["motivo"])
    print(json.dumps(diagnostico["fuentes"], ensure_ascii=False))

if __name__ == "__main__":
    main()
