import json
import math
from datetime import datetime, timezone
from pathlib import Path

DATOS = Path("data/estadisticas.json")
SALIDA = Path("data/pronosticos.json")
EXTRA = Path("data/estadisticas_extra.json")


XG = Path("data/xg_pitchapi.json")

def normalizar_equipo(s):
    import unicodedata, re
    s=unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode().lower()
    s=re.sub(r"\\b(fc|cf|cd|ud|sd|rcd|real|club|de|la)\\b"," ",s)
    return " ".join(re.findall(r"[a-z0-9]+",s))

def mezclar_xg(partidos, cache):
    from difflib import SequenceMatcher
    by_date={}
    for x in cache.values():
        if isinstance(x,dict) and all(k in x for k in ("fecha","goles_local","goles_visitante","xg_local","xg_visitante")):
            by_date.setdefault(x["fecha"],[]).append(x)
    resultado=[]; matches=0; usados=set()
    for p in partidos:
        try:
            fecha=datetime.strptime(p["fecha"],"%d/%m/%Y").strftime("%Y-%m-%d")
        except (ValueError,TypeError):
            resultado.append(dict(p));continue
        candidatos=[]
        for x in by_date.get(fecha,[]):
            if int(p["goles_local"])!=int(x["goles_local"]) or int(p["goles_visitante"])!=int(x["goles_visitante"]):continue
            a=SequenceMatcher(None,normalizar_equipo(p["local"]),normalizar_equipo(x["local"])).ratio()
            b=SequenceMatcher(None,normalizar_equipo(p["visitante"]),normalizar_equipo(x["visitante"])).ratio()
            key=(x["fecha"],x["local"],x["visitante"])
            if a>=0.72 and b>=0.72 and key not in usados:candidatos.append((key,x))
        if len(candidatos)==1:
            key,x=candidatos[0];usados.add(key)
            resultado.append(dict(p,goles_local=float(x["xg_local"]),goles_visitante=float(x["xg_visitante"])))
            matches+=1
        else:resultado.append(dict(p))
    return resultado,matches

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
    goles_casa = sum(float(w) * float(p["goles_local"]) for p,w in zip(jugados,pesos))
    goles_fuera = sum(float(w) * float(p["goles_visitante"]) for p,w in zip(jugados,pesos))
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

    partidos_reales = {equipo: 0 for equipo in equipos}
    for p, w in zip(jugados, pesos):
        partidos_reales[p["local"]] += 1
        partidos_reales[p["visitante"]] += 1
        local = stats[p["local"]]
        fuera = stats[p["visitante"]]
        gl = float(p["goles_local"])
        gv = float(p["goles_visitante"])

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
            if (partidos_reales[local] < min_partidos_equipo or
                partidos_reales[visitante] < min_partidos_equipo):
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
        "modelo": "Poisson con xG PitchAPI cuando disponible y fallback de goles reales",
        "fuente": datos.get("fuente"),
        "competiciones": {}
    }

    try:
        extras = json.loads(EXTRA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        extras = {"competiciones": {}, "estado": {}}
    salida["cobertura_extra"] = extras.get("estado", {})
    competiciones = {**datos["competiciones"], **extras.get("competiciones", {})}
    try:
        xg_cache=json.loads(XG.read_text(encoding="utf-8"))
        if xg_cache.get("temporada")!=datos.get("temporada"):xg_cache={}
    except (OSError,ValueError):xg_cache={}
    salida["cobertura_xg"]={}
    for liga, partidos in competiciones.items():
        # No se fabrican estimaciones con muestras demasiado pequeñas.
        # Los torneos UEFA tienen muestras limitadas: marcamos las salidas como exploratorias.
        if liga in ("LIGAF", "UCL", "UEL", "UECL") and len(partidos) < 12:
            salida["competiciones"][liga] = []
            continue
        usar=partidos
        if liga in ("SP1","SP2"):
            usar,coincidencias=mezclar_xg(partidos,xg_cache.get("competiciones",{}).get(liga,{}))
            salida["cobertura_xg"][liga]={"partidos_con_xg":coincidencias,"partidos_totales":len(partidos)}
        salida["competiciones"][liga] = calcular_liga(usar, min_partidos_equipo=3 if liga in ("UCL", "UEL", "UECL", "LIGAF") else 0)
        print(f"{liga}: {len(salida['competiciones'][liga])} enfrentamientos calculados")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(
        json.dumps(salida, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

if __name__ == "__main__":
    main()
