"""Backtest cronológico de Poisson goles vs mezcla goles/xG con PitchAPI.
No se usa xG del partido objetivo ni se altera producción.
"""
import json, math, os, time
from collections import defaultdict
from datetime import date
from pathlib import Path
from pitchapi_cliente import partidos_liga, tiros_partido
from pronosticos import calcular_liga

LIGAS={"SP1":"l_0ErfuF","SP2":"l_3kyHLd"}
TEMPORADA="2025/2026"
PESOS=(0.0,0.5,1.0)
UMBRAL_EMPATE=(1.0,0.9,0.8)
RHO_DC=(0.0,-0.1,-0.2)

def elegir(probs, umbral=1.0):
    # Un umbral inferior a 1 es una politica de decision, NO recalibra probabilidades.
    # Selecciona X solo cuando su probabilidad es suficientemente cercana a la del favorito.
    favorito=max(probs[0],probs[2])
    if probs[1]>=umbral*favorito:return 1
    return 0 if probs[0]>=probs[2] else 2

MAX_PARTIDOS=int(os.getenv("MAX_PARTIDOS_XG","100"))

def goles_xg(partido):
    raw=tiros_partido(str(partido["id"]))
    sums=defaultdict(float)
    n=0
    for periodo in raw.get("periods",[]):
        for tiro in periodo.get("shots",[]):
            if tiro.get("team_id") in (partido["home_team"]["id"],partido["away_team"]["id"]):
                v=tiro.get("expected_goals")
                if isinstance(v,(int,float)) and math.isfinite(v) and v>=0:
                    sums[tiro["team_id"]]+=v;n+=1
    if not n:
        return None
    return (sums[partido["home_team"]["id"]],sums[partido["away_team"]["id"]])

def dixon_coles(lh,la,rho):
    from pronosticos import poisson
    p=[0.0,0.0,0.0]
    for i in range(11):
        for j in range(11):
            tau=1.0
            if i==0 and j==0:tau=1-lh*la*rho
            elif i==0 and j==1:tau=1+lh*rho
            elif i==1 and j==0:tau=1+la*rho
            elif i==1 and j==1:tau=1-rho
            if tau<0:return None
            p[0 if i>j else 1 if i==j else 2]+=poisson(i,lh)*poisson(j,la)*tau
    return [v/sum(p) for v in p]

def main():
    output={"fuente":"PitchAPI tiros expected_goals","temporada":TEMPORADA,
      "metodo":"Walk-forward: xG de partidos previos, comparación de mezcla de goles observados y xG; muestra parcial cronológica",
      "limite_por_liga":MAX_PARTIDOS,"resultados":{}}
    for liga,lid in LIGAS.items():
        try:
            lista=partidos_liga(lid,TEMPORADA)
        except Exception as exc:
            output['resultados'][liga]={'estado':'error_consulta_partidos','error':type(exc).__name__}
            print(liga,'sin datos:',type(exc).__name__,flush=True)
            continue
        lista=sorted([p for p in lista if p.get("score_home") is not None and p.get("score_away") is not None],
            key=lambda p:(p.get("date",""),p.get("time_utc",""),p["id"]))[:MAX_PARTIDOS]
        observados=[];errores=[];conteos={w:{"n":0,"aciertos":0,"brier_suma":0.0,"logloss_suma":0.0,"empates_elegidos":0,"empates_reales":0,"p_empate_suma":0.0,"politicas":{str(t):{"aciertos":0,"x_elegidas":0,"x_acertadas":0} for t in UMBRAL_EMPATE},"dc":{str(r):{"aciertos":0,"x_elegidas":0,"x_acertadas":0,"brier":0.0,"logloss":0.0,"p_x":0.0} for r in RHO_DC}} for w in PESOS}
        for k,p in enumerate(lista):
            try:
                xg=goles_xg(p)
            except Exception as e:
                errores.append({"indice":k,"error":type(e).__name__})
                if len(errores)>4:break
                continue
            if xg is None:continue
            home=p["home_team"]["name"];away=p["away_team"]["name"]
            gl=int(p["score_home"]);gv=int(p["score_away"])
            fecha=p["date"][:10]
            if len(observados)>=40:
                # Fecha estrictamente anterior: evita contaminación de partidos del mismo día
                historia=[x for x in observados if x["fecha"]<fecha]
                if len(historia)>=40:
                    for w in PESOS:
                        train=[dict(x,goles_local=(1-w)*x["goles_local"]+w*x["xg_local"],
                                    goles_visitante=(1-w)*x["goles_visitante"]+w*x["xg_visitante"]) for x in historia]
                        # El motor actual trunca goles a enteros. Para xG usamos
                        # variante que permite goles fraccionarios, sin tocar producción.
                        result=calcular_xg(train,(home,away))
                        if not result:continue
                        probs=result
                        actual=0 if gl>gv else 1 if gl==gv else 2
                        m=conteos[w];m["n"]+=1
                        for rho in RHO_DC:
                            lambdas=calcular_lambdas(train,(home,away))
                            dc=dixon_coles(*lambdas,rho) if lambdas else None
                            if dc is None:continue
                            d=m["dc"][str(rho)]
                            elegido=max(range(3),key=lambda i:dc[i])
                            d["aciertos"]+=int(elegido==actual)
                            d["x_elegidas"]+=int(elegido==1)
                            d["x_acertadas"]+=int(elegido==1 and actual==1)
                            d["p_x"]+=dc[1]
                            d["brier"]+=sum((dc[i]-(i==actual))**2 for i in range(3))
                            d["logloss"]-=math.log(max(dc[actual],1e-12))
                        m["empates_reales"]+=int(actual==1)
                        m["p_empate_suma"]+=probs[1]
                        for umbral in UMBRAL_EMPATE:
                            elegido=elegir(probs,umbral)
                            policy=m["politicas"][str(umbral)]
                            policy["aciertos"]+=int(elegido==actual)
                            policy["x_elegidas"]+=int(elegido==1)
                            policy["x_acertadas"]+=int(elegido==1 and actual==1)
                        m["aciertos"]+=int(max(range(3),key=lambda i:probs[i])==actual)
                        m["empates_elegidos"]+=int(max(range(3),key=lambda i:probs[i])==1)
                        m["brier_suma"]+=sum((probs[i]-(i==actual))**2 for i in range(3))
                        m["logloss_suma"]-=math.log(max(probs[actual],1e-12))
            observados.append({"fecha":fecha,"local":home,"visitante":away,
                "goles_local":gl,"goles_visitante":gv,"xg_local":xg[0],"xg_visitante":xg[1]})
            if (k+1)%40==0:print(liga,"consultados",k+1,flush=True)
        output["resultados"][liga]={"consultados":len(observados),"errores":errores,
            "modelos":{str(w):{"n":m["n"],"aciertos":m["aciertos"],
                "precision":round(m["aciertos"]/m["n"]*100,2) if m["n"] else None,
                "brier":round(m["brier_suma"]/m["n"],4) if m["n"] else None,
                "logloss":round(m["logloss_suma"]/m["n"],4) if m["n"] else None,
                "empates_elegidos":m["empates_elegidos"],"empates_reales":m["empates_reales"],"probabilidad_empate_media":round(m["p_empate_suma"]/m["n"],4) if m["n"] else None,"politicas":{t:dict(v,precision=round(100*v["aciertos"]/m["n"],2) if m["n"] else None) for t,v in m["politicas"].items()},"dixon_coles":{t:{"aciertos":v["aciertos"],"precision":round(100*v["aciertos"]/m["n"],2) if m["n"] else None,"x_elegidas":v["x_elegidas"],"x_acertadas":v["x_acertadas"],"prob_x_media":round(v["p_x"]/m["n"],4) if m["n"] else None,"brier":round(v["brier"]/m["n"],4) if m["n"] else None,"logloss":round(v["logloss"]/m["n"],4) if m["n"] else None} for t,v in m["dc"].items()}} for w,m in conteos.items()}}
        print(liga,json.dumps(output["resultados"][liga]),flush=True)
    Path("data").mkdir(exist_ok=True)
    Path("data/backtest_xg_pitchapi.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def calcular_xg(partidos, objetivo):
    from pronosticos import probabilidades
    lambdas=calcular_lambdas(partidos,objetivo)
    return [x/100 for x in probabilidades(*lambdas)] if lambdas else None

def calcular_lambdas(partidos, objetivo):
    # Replica Poisson con ratios casa/fuera y suavizado de cinco partidos,
    # pero acepta goles fraccionarios (xG).
    h,a=objetivo
    equipos={p["local"] for p in partidos}|{p["visitante"] for p in partidos}
    if h not in equipos or a not in equipos:return None
    if sum(h in (p["local"],p["visitante"]) for p in partidos)<3:return None
    if sum(a in (p["local"],p["visitante"]) for p in partidos)<3:return None
    n=len(partidos)
    media_h=max(.1,sum(p["goles_local"] for p in partidos)/n)
    media_a=max(.1,sum(p["goles_visitante"] for p in partidos)/n)
    def ratio(equipo,local,campo,media):
        subset=[p for p in partidos if p["local" if local else "visitante"]==equipo]
        return (sum(p[campo] for p in subset)+5*media)/((len(subset)+5)*media)
    eh=max(.1,min(5,media_h*ratio(h,True,"goles_local",media_h)*ratio(a,False,"goles_local",media_h)))
    ea=max(.1,min(5,media_a*ratio(a,False,"goles_visitante",media_a)*ratio(h,True,"goles_visitante",media_a)))
    # above fields for defense use opponent goals from same game
    return (eh,ea)

if __name__=="__main__":main()
