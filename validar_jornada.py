"""Valida la jornada antes de permitir que la web la presente como confirmada.
No descarga calendarios: sin una fuente fiable, mantiene el estado pendiente.
"""
import json
from datetime import date, datetime, timezone
from pathlib import Path

RUTA = Path("data/jornada_actual.json")
ESTADO = Path("data/estado_jornada.json")

def validar(j):
    problemas = []
    if j.get("estado") != "verificada":
        problemas.append("Composición no verificada")
    partidos = j.get("partidos", [])
    if len(partidos) != 14:
        problemas.append("La jornada no contiene exactamente 14 partidos")
    posiciones = [p.get("posicion") for p in partidos]
    if posiciones != list(range(1, 15)):
        problemas.append("Las posiciones no son 1 a 14")
    enfrentamientos = []
    for p in partidos:
        local, visitante = p.get("local"), p.get("visitante")
        if not isinstance(local, str) or not local.strip() or not isinstance(visitante, str) or not visitante.strip():
            problemas.append("Hay equipos sin identificar")
        elif local.strip().casefold() == visitante.strip().casefold():
            problemas.append("Un equipo juega contra sí mismo")
        else:
            enfrentamientos.append((local.strip().casefold(), visitante.strip().casefold()))
    if len(set(enfrentamientos)) != len(enfrentamientos):
        problemas.append("Hay enfrentamientos duplicados")
    pleno = j.get("pleno") or {}
    if not pleno.get("local") or not pleno.get("visitante"):
        problemas.append("Falta el Pleno al 15")
    try:
        inicio = date.fromisoformat(j["fecha_inicio"])
        fin = date.fromisoformat(j["fecha_fin"])
        if fin < inicio:
            problemas.append("Fechas incoherentes")
        if fin < date.today():
            problemas.append("La jornada ya ha terminado")
    except (KeyError, ValueError, TypeError):
        problemas.append("Fechas no válidas")
    fuentes = j.get("fuentes") or []
    if not fuentes or not all(isinstance(s, str) and s.startswith("https://") for s in fuentes):
        problemas.append("Falta una referencia de origen verificable")
    # Una URL acredita el origen declarado, no prueba por sí sola la exactitud del calendario.
    return problemas

def main():
    try:
        jornada = json.loads(RUTA.read_text(encoding="utf-8"))
        problemas = validar(jornada)
    except (OSError, ValueError, TypeError) as exc:
        jornada = {}
        problemas = [f"No se puede leer la jornada: {exc}"]
    estado = {
        "comprobado": datetime.now(timezone.utc).isoformat(),
        "numero": jornada.get("numero"),
        "publicable": not problemas,
        "motivos": problemas,
        "nota": "Verificación estructural. QuinielaFutbol es la fuente principal; QuiniPrats solo actúa como respaldo ante errores de acceso."
    }
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Jornada publicable:", estado["publicable"])
    for motivo in problemas:
        print("-", motivo)

if __name__ == "__main__":
    main()
