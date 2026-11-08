"""Actualiza xG de partidos ya disputados, con caché y sin utilizar datos futuros."""
import json, math, os, time
from pathlib import Path
from pitchapi_cliente import partidos_liga, tiros_partido

DEST=Path("data/xg_pitchapi.json")
LIGAS={"SP1":"l_0ErfuF","SP2":"l_3kyHLd"}
SEASON="2026/2027"

def main():
    try: db=json.loads(DEST.read_text(encoding="utf-8"))
    except (OSError,ValueError): db={"temporada":SEASON,"competiciones":{}}
    if db.get("temporada")!=SEASON:db={"temporada":SEASON,"competiciones":{}}
    for liga,lid in LIGAS.items():
        cache=db["competiciones"].setdefault(liga,{})
        try: partidos=partidos_liga(lid,SEASON)
        except Exception as e:
            print(liga,"catálogo no disponible, conservando caché",type(e).__name__,flush=True)
            continue
        nuevos=0
        for p in sorted(partidos,key=lambda p:p.get("date","")):
            pid=str(p["id"])
            if pid in cache:continue
            if p.get("score_home") is None or p.get("score_away") is None:continue
            try:
                raw=tiros_partido(pid)
                sums={p["home_team"]["id"]:0.,p["away_team"]["id"]:0.}
                valid=0
                for periodo in raw.get("periods",[]):
                    for shot in periodo.get("shots",[]):
                        team=shot.get("team_id");v=shot.get("expected_goals")
                        if team in sums and isinstance(v,(int,float)) and math.isfinite(v) and v>=0:
                            sums[team]+=v;valid+=1
                if valid==0:continue
                cache[pid]={"fecha":p["date"][:10],"local":p["home_team"]["name"],
                  "visitante":p["away_team"]["name"],"goles_local":int(p["score_home"]),
                  "goles_visitante":int(p["score_away"]),"xg_local":round(sums[p["home_team"]["id"]],5),
                  "xg_visitante":round(sums[p["away_team"]["id"]],5)}
                nuevos+=1
            except Exception as e:
                print(liga,"partido omitido",pid,type(e).__name__,flush=True)
                if nuevos==0:break
            if nuevos%25==0 and nuevos:
                DEST.write_text(json.dumps(db,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(liga,"xG almacenados",len(cache),"nuevos",nuevos,flush=True)
        DEST.parent.mkdir(exist_ok=True)
        DEST.write_text(json.dumps(db,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":main()
