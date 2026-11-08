"""Datos complementarios de Liga F y UEFA desde marcadores ESPN públicos.
No publica probabilidades si una fuente falla o los partidos son insuficientes.
"""
import json
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

OUT = Path("data/estadisticas_extra.json")
LEAGUES = {
    "LIGAF": "esp.w.1",
    "UCL": "uefa.champions",
    "UEL": "uefa.europa",
    "UECL": "uefa.europa.conf",
}

def parse_events(payload, hoy):
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise ValueError("Respuesta sin lista de eventos")
    matches = []
    for ev in payload["events"]:
        for comp in ev.get("competitions", []):
            state = (comp.get("status") or ev.get("status") or {}).get("type", {})
            if not state.get("completed", False):
                continue
            teams = comp.get("competitors") or []
            if len(teams) != 2:
                continue
            home = next((x for x in teams if x.get("homeAway") == "home"), None)
            away = next((x for x in teams if x.get("homeAway") == "away"), None)
            if not home or not away:
                continue
            try:
                h, a = int(home["score"]), int(away["score"])
                fecha = (comp.get("date") or ev.get("date") or "")[:10]
                if date.fromisoformat(fecha) > hoy:
                    continue
                n1 = home["team"]["displayName"].strip()
                n2 = away["team"]["displayName"].strip()
                if not n1 or not n2 or n1 == n2:
                    continue
            except (KeyError, TypeError, ValueError):
                continue
            matches.append({
                "fecha": fecha, "local": n1, "visitante": n2,
                "goles_local": h, "goles_visitante": a,
                "resultado": "H" if h > a else "D" if h == a else "A",
                "id": str(ev.get("id", ""))
            })
    return matches

def request_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "QuinielaLab/1.0 (public match results)", "Accept":"application/json"})
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)

def obtener_liga(slug, hoy):
    # ESPN acepta un intervalo de fechas; un solo intervalo cubre la temporada hasta hoy.
    inicio = f"{hoy.year if hoy.month >= 7 else hoy.year - 1}0801"
    fin = hoy.strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard?dates={hoy.year}&limit=500"
    payload = request_json(url)
    games = parse_events(payload, hoy)
    by_id = {}
    for p in games:
        key = p["id"] or (p["fecha"], p["local"], p["visitante"])
        by_id[key] = p
    return list(by_id.values()), url

def main():
    hoy = date.today()
    old = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8")).get("competiciones", {})
        except (OSError, ValueError):
            pass
    resultado = {"actualizado": datetime.now(timezone.utc).isoformat(),
                 "fuente": "ESPN scoreboard, resultados públicos no oficiales",
                 "competiciones": {}, "estado": {}}
    for liga, slug in LEAGUES.items():
        try:
            partidos, url = obtener_liga(slug, hoy) if liga == "LIGAF" else obtener_uefa(liga, hoy)
            # Si falla el proveedor o no hay partidos, conservar histórico anterior,
            # pero dejarlo marcado y no presentar datos como actualizados.
            if len(partidos) < 6:
                raise ValueError(f"Solo {len(partidos)} partidos completos; mínimo 6")
            resultado["competiciones"][liga] = partidos
            resultado["estado"][liga] = {"ok": True, "partidos": len(partidos), "url": url}
        except Exception as exc:
            resultado["competiciones"][liga] = old.get(liga, [])
            resultado["estado"][liga] = {"ok": False, "partidos": len(old.get(liga, [])), "error": str(exc)[:180]}
        print(liga, resultado["estado"][liga])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
