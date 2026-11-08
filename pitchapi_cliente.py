"""Cliente opcional PitchAPI. Solo consulta endpoints documentados y nunca expone claves.
No se activa en producción sin validación de cobertura y datos históricos.
"""
import json
import os
import urllib.parse
import urllib.request

BASE = "https://api.pitchapi.dev/v1"

class PitchAPIError(RuntimeError):
    pass

def consultar(ruta, params=None, api_key=None):
    key = api_key or os.getenv("PITCHAPI_API_KEY")
    if not key:
        raise PitchAPIError("Configura PITCHAPI_API_KEY como secreto de GitHub Actions")
    if not ruta.startswith("/") or ".." in ruta or "://" in ruta:
        raise ValueError("Ruta API inválida")
    url = BASE + ruta
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"X-API-KEY": key, "Accept": "application/json", "User-Agent": "QuinielaLab/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            envelope = json.load(response)
    except Exception as exc:
        raise PitchAPIError("Error de conexión con PitchAPI: " + type(exc).__name__) from exc
    if not isinstance(envelope, dict) or "data" not in envelope:
        raise PitchAPIError("Respuesta API sin datos válidos")
    return envelope["data"]

def cobertura_espanola(api_key=None):
    """Devuelve coincidencias del catálogo real; no presupone SP1/SP2."""
    catalogo = consultar("/leagues", api_key=api_key)
    ligas = catalogo.get("leagues", [])
    return [{"id": liga.get("id"), "nombre": liga.get("name"), "pais": liga.get("country_code"), "temporadas": liga.get("seasons", [])}
            for liga in ligas if liga.get("country_code") == "ESP"]

def partidos_liga(league_id, season, api_key=None):
    return consultar("/leagues/" + urllib.parse.quote(league_id, safe="") + "/matches",
                     {"season": season, "status": "played"}, api_key=api_key).get("matches", [])

def tiros_partido(match_id, api_key=None):
    return consultar("/matches/" + urllib.parse.quote(match_id, safe="") + "/shots", api_key=api_key)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--comprobar-cobertura", action="store_true")
    args = parser.parse_args()
    if args.comprobar_cobertura:
        print(json.dumps(cobertura_espanola(), ensure_ascii=False, indent=2))
