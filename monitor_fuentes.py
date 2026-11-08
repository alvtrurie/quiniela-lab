"""Monitor de fuentes de La Quiniela.
No publica composiciones sin contraste: genera un diagnóstico reproducible.
"""
import json
import re
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

FUENTES = {
    "quinielafutbol": "https://www.quinielafutbol.info/proximas-jornadas-de-la-quiniela.html",
    "quiniprats_21": "https://quiniprats.com/es/quiniela/2026-27/jornada/21",
    "quiniprats_22": "https://quiniprats.com/es/quiniela/2026-27/jornada/22",
}
DESTINO = Path("data/diagnostico_fuentes.json")

class Textos(HTMLParser):
    def __init__(self):
        super().__init__()
        self.partes = []
        self.omitir = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.omitir += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.omitir:
            self.omitir -= 1
    def handle_data(self, texto):
        if not self.omitir:
            limpio = " ".join(texto.split())
            if limpio:
                self.partes.append(limpio)

def consultar(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; QuinielaLab/1.0; public football calendar monitor)",
        "Accept": "text/html",
    })
    with urllib.request.urlopen(req, timeout=18) as respuesta:
        html = respuesta.read(1_500_000).decode("utf-8", errors="replace")
        codigo = respuesta.status
    parser = Textos()
    parser.feed(html)
    texto = " ".join(parser.partes)
    return {
        "accesible": True,
        "http": codigo,
        "bytes_html": len(html),
        "menciona_quiniela": "quiniela" in texto.casefold(),
        "menciona_pleno": bool(re.search(r"pleno\\s+al\\s+15|españa\\s*[-–]\\s*inglaterra", texto, re.I)),
        "extracto": texto[:350],
    }

def main():
    estado = {"consultado": datetime.now(timezone.utc).isoformat(), "fuentes": {},
              "publicacion_automatica": False,
              "explicacion": "Monitor de accesibilidad. No extrae ni valida todavía una composición completa."}
    for nombre, url in FUENTES.items():
        try:
            resultado = consultar(url)
            print(nombre, "HTTP", resultado["http"], "bytes", resultado["bytes_html"])
        except Exception as exc:
            resultado = {"accesible": False, "error": str(exc)[:250]}
            print(nombre, "NO DISPONIBLE:", resultado["error"])
        estado["fuentes"][nombre] = {"url": url, **resultado}
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
