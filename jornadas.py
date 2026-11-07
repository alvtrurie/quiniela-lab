import json
import re
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

URL = "https://www.loteriasyapuestas.es/es/avisos-de-interes"
SALIDA = Path("data/jornadas_fuente.json")

class Extractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.textos = []

    def handle_data(self, data):
        texto = " ".join(data.split())
        if texto:
            self.textos.append(texto)

def main():
    peticion = urllib.request.Request(
        URL,
        headers={"User-Agent": "Mozilla/5.0 QuinielaLab/1.0"}
    )

    with urllib.request.urlopen(peticion, timeout=30) as respuesta:
        html = respuesta.read().decode("utf-8", errors="replace")

    parser = Extractor()
    parser.feed(html)

    avisos = []
    vistos = set()

    for texto in parser.textos:
        normalizado = texto.upper()
        if "QUINIELA" not in normalizado:
            continue
        if not any(p in normalizado for p in (
            "COMPOSICION", "COMPOSICIÓN",
            "JORNADA", "CALENDARIO", "APLAZAMIENTO"
        )):
            continue
        if texto in vistos:
            continue
        vistos.add(texto)
        avisos.append(texto)

    if not avisos:
        raise RuntimeError(
            "No se encontraron avisos de Quiniela. "
            "Revisar la estructura de la fuente oficial."
        )

    datos = {
        "actualizado": datetime.now(timezone.utc).isoformat(),
        "fuente": URL,
        "estado": "avisos_localizados_pendiente_extraer_partidos",
        "avisos": avisos,
        "jornadas": []
    }

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Avisos oficiales localizados: {len(avisos)}")
    print("Pendiente: extraer y verificar los 15 encuentros.")

if __name__ == "__main__":
    main()
