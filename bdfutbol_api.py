"""Adaptador opcional para BDFutbol API v2.
No descarga datos sin credenciales ni altera pronósticos existentes.
Credenciales SOLO en variables de entorno; nunca en Git ni en la web.
Documentación: https://www.bdfutbol.com/es/c/api2.html
"""
import base64
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime

BASE = "https://api.bdfutbol.com/v2"
CATEGORIAS = {"SP1": "1a", "SP2": "2a"}
TIPOS = frozenset(("cla", "res", "pla", "plae", "jug", "ent", "eq", "p", "find", "partsj", "partse", "partseq", "partseqr"))

class BDFutbolError(RuntimeError):
    pass

def consultar(tipo, **parametros):
    if tipo not in TIPOS:
        raise ValueError("Tipo de consulta no reconocido")
    usuario = os.environ.get("BDFUTBOL_USER")
    clave = os.environ.get("BDFUTBOL_PASSWORD")
    if not usuario or not clave:
        raise BDFutbolError("Faltan credenciales BDFUTBOL_USER / BDFUTBOL_PASSWORD")
    query = urllib.parse.urlencode({"tip": tipo, **parametros})
    auth = base64.b64encode(f"{usuario}:{clave}".encode()).decode()
    req = urllib.request.Request(f"{BASE}?{query}", headers={
        "Authorization": f"Basic {auth}", "Accept": "application/json",
        "User-Agent": "QuinielaLab/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.load(response)
    except Exception as exc:
        raise BDFutbolError(f"Error consultando BDFutbol ({type(exc).__name__})") from exc
    if not isinstance(data, dict) or str(data.get("status")) != "1":
        raise BDFutbolError("BDFutbol no ha devuelto una respuesta válida")
    return data.get("result", {})

def resultados(liga, temporada, fecha_corte=None):
    """Partidos terminados ANTES de fecha_corte (YYYY-MM-DD).
    Conserva IDs BDFutbol para unir futuras alineaciones/entrenadores.
    """
    if liga not in CATEGORIAS:
        raise ValueError("Solo SP1 y SP2")
    if fecha_corte is None:
        raise ValueError("fecha_corte obligatorio para evitar filtraciones futuras")
    limite = datetime.strptime(fecha_corte, "%Y-%m-%d").date()
    data = consultar("res", cat=CATEGORIAS[liga], temp=temporada, cal=0)
    partidos = data.get("resultado", [])
    if isinstance(partidos, dict):
        partidos = [partidos]
    salida = []
    for p in partidos:
        try:
            fecha = datetime.strptime(p["fecha"], "%d/%m/%Y").date()
            if fecha >= limite:
                continue
            goles_local = int(p["goles_local"])
            goles_visitante = int(p["goles_visitante"])
            salida.append({
                "fecha": fecha.isoformat(), "id_partido": str(p["id_partido"]),
                "id_local": str(p["id_local"]), "id_visitante": str(p["id_visitante"]),
                "local": p["nombre_local"], "visitante": p["nombre_visitante"],
                "goles_local": goles_local, "goles_visitante": goles_visitante,
                "resultado": "H" if goles_local > goles_visitante else "D" if goles_local == goles_visitante else "A",
                "jornada": p.get("jornada"),
            })
        except (KeyError, ValueError, TypeError):
            continue
    return sorted(salida, key=lambda p: (p["fecha"], p["id_partido"]))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--liga", choices=("SP1", "SP2"), required=True)
    parser.add_argument("--temporada", required=True, help="Ejemplo: 2025-26")
    parser.add_argument("--fecha-corte", required=True, help="YYYY-MM-DD (excluida)")
    args = parser.parse_args()
    print(json.dumps(resultados(args.liga, args.temporada, args.fecha_corte), ensure_ascii=False, indent=2))
