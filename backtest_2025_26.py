"""Backtest cronológico 2025/26 del motor Poisson real.
No utiliza resultados posteriores a cada encuentro. Partidos, no boletos oficiales.
"""
import csv
import io
import json
import math
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path
from pronosticos import calcular_liga
from estadisticas_extra import parse_events, request_json

START, END = date(2025,8,1), date(2026,7,1)
MIN_TRAIN = 40
LEAGUES = {"SP1":"Primera masculina","SP2":"Segunda masculina","LIGAF":"Liga F",
           "UCL":"Champions League","UEL":"Europa League","UECL":"Conference League"}
ESPN = {"LIGAF":"esp.w.1","UCL":"uefa.champions","UEL":"uefa.europa","UECL":"uefa.europa.conf"}
def leer_sp(liga):
    url=f"https://www.football-data.co.uk/mmz4281/2526/{liga}.csv"
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=35) as response:
        raw=response.read().decode("utf-8-sig",errors="replace")
    result=[]
    for r in csv.DictReader(io.StringIO(raw)):
        try:
            dt=date.strptime(r["Date"],"%d/%m/%Y") # fallback below
        except AttributeError:
            try:
                from datetime import datetime
                dt=datetime.strptime(r["Date"],"%d/%m/%Y").date()
            except (ValueError,KeyError,TypeError):
                continue
        try:
            h,a=int(r["FTHG"]),int(r["FTAG"])
            if not START<=dt<END:continue
            result.append({"fecha":dt.isoformat(),"local":r["HomeTeam"].strip(),"visitante":r["AwayTeam"].strip(),
                           "goles_local":h,"goles_visitante":a,"resultado":"H" if h>a else "D" if h==a else "A"})
        except (KeyError,TypeError,ValueError):
            continue
    return result,url

def leer_espn(liga):
    slug=ESPN[liga]
    all_rows=[]
    urls=[]
    for year in (2025,2026):
        url=f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard?dates={year}&limit=500"
        urls.append(url)
        all_rows.extend(parse_events(request_json(url),date(2026,7,1)))
    unique={}
    for r in all_rows:
        if START<=date.fromisoformat(r["fecha"])<END:
            unique[r.get("id") or (r["fecha"],r["local"],r["visitante"])]=r
    return list(unique.values()),urls

def evaluar(partidos, min_train=MIN_TRAIN, min_team=3):
    partidos=sorted(partidos,key=lambda p:p["fecha"])
    train=[]; predictions=[]; skipped=defaultdict(int)
    days=defaultdict(list)
    for p in partidos:days[p["fecha"]].append(p)
    for fecha, group in sorted(days.items()):
        if len(train)<min_train:
            skipped["sin_historico_suficiente"]+=len(group)
        else:
            # Entrenar una sola vez por fecha: ni siquiera usamos otros resultados del mismo día.
            pred=calcular_liga(train,min_partidos_equipo=min_team,objetivos={(p["local"],p["visitante"]) for p in group})
            lookup={(p["local"],p["visitante"]):p for p in pred}
            for p in group:
                item=lookup.get((p["local"],p["visitante"]))
                if not item:
                    skipped["equipo_sin_muestra"]+=1
                    continue
                probs=[item["probabilidades"][s]/100 for s in ("1","X","2")]
                actual={"H":0,"D":1,"A":2}[p["resultado"]]
                guess=max(range(3),key=lambda i:probs[i])
                predictions.append({"fecha":fecha,"local":p["local"],"visitante":p["visitante"],
                                    "real":p["resultado"],"pronosticado":("H","D","A")[guess],
                                    "acierto":guess==actual,"prob_real":probs[actual],
                                    "brier":sum((v-(1 if i==actual else 0))**2 for i,v in enumerate(probs)),
                                    "logloss":-math.log(max(probs[actual],1e-10))})
        train.extend(group)
    return predictions,dict(skipped)

def resumen(rows):
    n=len(rows)
    if not n:return {"evaluados":0}
    return {"evaluados":n,"aciertos":sum(x["acierto"] for x in rows),
            "porcentaje":round(100*sum(x["acierto"] for x in rows)/n,2),
            "brier":round(sum(x["brier"] for x in rows)/n,4),
            "logloss":round(sum(x["logloss"] for x in rows)/n,4),
            "baseline_todos_1":round(100*sum(x["real"]=="H" for x in rows)/n,2),
            "desde":rows[0]["fecha"],"hasta":rows[-1]["fecha"]}

def main():
    report={"temporada":"2025/26","metodo":"Walk-forward por fecha; solo partidos anteriores; modelo Poisson sin recalibrar",
            "alcance":"Partidos individuales de seis competiciones; NO jornadas oficiales de La Quiniela",
            "min_partidos_entrenamiento":MIN_TRAIN,"min_partidos_por_equipo":3,"ligas":{}}
    for league in LEAGUES:
        try:
            games,src=leer_sp(league) if league in ("SP1","SP2") else leer_espn(league)
            preds,skip=evaluar(games)
            report["ligas"][league]={"nombre":LEAGUES[league],"partidos_obtenidos":len(games),
                                   "omitidos":skip,"fuentes":src,"resultado":resumen(preds)}
            print(league,len(games),resumen(preds),skip,flush=True)
        except Exception as exc:
            report["ligas"][league]={"nombre":LEAGUES[league],"error":str(exc)[:250]}
            print(league,"ERROR",exc,flush=True)
    all_evaluated=[(k,v["resultado"]) for k,v in report["ligas"].items() if v.get("resultado",{}).get("evaluados")]
    total=sum(v["evaluados"] for _,v in all_evaluated)
    aciertos=sum(v["aciertos"] for _,v in all_evaluated)
    report["total"]={"evaluados":total,"aciertos":aciertos,"porcentaje":round(100*aciertos/total,2) if total else None}
    out=Path("data/backtest_2025_26.json");out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("TOTAL",report["total"],flush=True)
if __name__=="__main__":main()
