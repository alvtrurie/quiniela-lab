import json
import math
from datetime import datetime, timezone
from pathlib import Path

DATOS = Path("data/estadisticas.json")
SALIDA = Path("data/pronosticos.json")
EXTRA = Path("data/estadisticas_extra.json")

def poisson(k, media):
    return math.exp(-media) * media ** k / math.factorial(k)

def probabilidades(goles_local, goles_visitante):
    p1 = px = p2 = 0.0
    for i in range(11):
        for j in range(11):
            p = poisson(i, goles_local) * poisson(j, goles_visitante)
            if i > j:
                p1 += p
            elif i == j:
                px += p
            else:
                p2 += p
    total = p1 + px + p2
    return [round(100 * x / total, 2) for x in (p1, px, p2)]

def calcular_liga(partidos, min_partidos_equipo=0, objetivos=None, pesos=None, empate_extra=0.0):
    jugados = [p for p in partidos if p.get("resultado") in ("H", "D", "A")]
    if not jugados:
        return []

    equipos = sorted(set(
        p["local"] for p in jugados
    ) | set(
        p["visitante"] for p in jugados
    ))

    if pesos is None:
        pesos = [1.0] * len(jugados)
    if len(pesos) != len(jugados):
        raise ValueError("Pesos y partidos deben coincidir")
    suma_pesos = sum(pesos)
    if suma_pesos <= 0:
        raise ValueError("Pesos inválidos")
    goles_casa = sum(float(w) * int(p["goles_local"]) for p,w in zip(jugados,pesos))
    goles_fuera = sum(float(w) * int(p["goles_visitante"]) for p,w in zip(jugados,pesos))
    media_casa = max(0.1, goles_casa / suma_pesos)
    media_fuera = max(0.1, goles_fuera / suma_pesos)

    stats = {
        equipo: {
            "pj_casa": 0, "pj_fuera": 0,
            "gf_casa": 0, "gc_casa": 0,
            "gf_fuera": 0, "gc_fuera": 0
        }
        for equipo in equipos
    }

    for p, w in zip(jugados, pesos):
        local = stats[p["local"]]
        fuera = stats[p["visitante"]]
        gl = int(p["goles_local"])
        gv = int(p["goles_visitante"])

        local["pj_casa"] += w
        local["gf_casa"] += w * gl
        local["gc_casa"] += w * gv
        fuera["pj_fuera"] += w
        fuera["gf_fuera"] += w * gv
        fuera["gc_fuera"] += w * gl

    def ratio(goles, partidos, media):
        # Suavizado para evitar estimaciones extremas con pocos partidos
        return (goles + 5 * media) / ((partidos + 5) * media)

    pronosticos = []
    for local in equipos:
        for visitante in equipos:
            if local == visitante or (objetivos is not None and (local, visitante) not in objetivos):
                continue

            a = stats[local]
            b = stats[visitante]
            if (a["pj_casa"] + a["pj_fuera"] < min_partidos_equipo or
                b["pj_casa"] + b["pj_fuera"] < min_partidos_equipo):
                continue

            ataque_local = ratio(a["gf_casa"], a["pj_casa"], media_casa)
            defensa_visitante = ratio(b["gc_fuera"], b["pj_fuera"], media_casa)
            ataque_visitante = ratio(b["gf_fuera"], b["pj_fuera"], media_fuera)
            defensa_local = ratio(a["gc_casa"], a["pj_casa"], media_fuera)

            esperados_local = max(0.1, min(5, media_casa * ataque_local * defensa_visitante))
            esperados_visitante = max(0.1, min(5, media_fuera * ataque_visitante * defensa_local))

            porcentajes = probabilidades(esperados_local, esperados_visitante)
            if empate_extra:
                p = [v / 100 for v in porcentajes]
                p[1] = max(0.01, min(0.90, p[1] + empate_extra))
                escala = (1 - p[1]) / (p[0] + p[2])
                porcentajes = [round(p[0] * escala * 100, 2), round(p[1] * 100, 2), round(p[2] * escala * 100, 2)]
            signos = ["1", "X", "2"]
            mejor = signos[max(range(3), key=lambda i: porcentajes[i])]

            pronosticos.append({
                "local": local,
                "visitante": visitante,
                "probabilidades": {
                    "1": porcentajes[0],
                    "X": porcentajes[1],
                    "2": porcentajes[2]
                },
                "recomendado": mejor,
                "goles_esperados": {
                    "local": round(esperados_local, 2),
                    "visitante": round(esperados_visitante, 2)
                }
            })
    return pronosticos

def main():
    with DATOS.open(encoding="utf-8") as f:
        datos = json.load(f)

    salida = {
        "actualizado": datetime.now(timezone.utc).isoformat(),
        "modelo": "Poisson con fuerzas local/visitante y suavizado",
        "fuente": datos.get("fuente"),
        "competiciones": {}
    }

    try:
        extras = json.loads(EXTRA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        extras = {"competiciones": {}, "estado": {}}
    salida["cobertura_extra"] = extras.get("estado", {})
    competiciones = {**datos["competiciones"], **extras.get("competiciones", {})}
    for liga, partidos in competiciones.items():
        # No se fabrican estimaciones con muestras demasiado pequeñas.
        # Los torneos UEFA tienen muestras limitadas: marcamos las salidas como exploratorias.
        if liga in ("LIGAF", "UCL", "UEL", "UECL") and len(partidos) < 12:
            salida["competiciones"][liga] = []
            continue
        salida["competiciones"][liga] = calcular_liga(partidos, min_partidos_equipo=3 if liga in ("UCL", "UEL", "UECL", "LIGAF") else 0)
        print(f"{liga}: {len(salida['competiciones'][liga])} enfrentamientos calculados")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(
        json.dumps(salida, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

if __name__ == "__main__":
    main()
