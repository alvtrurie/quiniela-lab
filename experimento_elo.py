"""Elo cronológico como corrector de probabilidades Poisson; comparación fuera de muestra.
Elo usa únicamente resultados de fechas anteriores; no aprende de partidos del mismo día.
"""
import csv
import io
import json
import math
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from pronosticos import calcular_liga

LIGAS=("SP1","SP2")
TEMPORADAS=("2425","2526")
CONFIGS={"base":0.0,"elo_15":0.15,"elo_30":0.30,"elo_50":0.50}
K=20
VENTAJA_LOCAL=65

def descargar(liga,temporada):
    url=f"https://www.football-data.co.uk/mmz4281/{temporada}/{liga}.csv"
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=35) as response:
        raw=response.read().decode("utf-8-sig",errors="replace")
    out=[]
    for row in csv.DictReader(io.StringIO(raw)):
        try:
            fecha=datetime.strptime(row["Date"],"%d/%m/%Y").date().isoformat()
            gl=int(row["FTHG"]);gv=int(row["FTAG"])
            local=row["HomeTeam"].strip();visitante=row["AwayTeam"].strip()
            if not local or not visitante:continue
            out.append({"fecha":fecha,"local":local,"visitante":visitante,
                        "goles_local":gl,"goles_visitante":gv,
                        "resultado":"H" if gl>gv else "D" if gl==gv else "A"})
        except (ValueError,KeyError,TypeError):continue
    return out

def elo_actualizar(ratings,partidos):
    # Todos los encuentros de la misma fecha utilizan Elo previo a esa fecha.
    cambios=defaultdict(float)
    for p in partidos:
        a=p["local"];b=p["visitante"]
        ra=ratings.get(a,1500.0);rb=ratings.get(b,1500.0)
        esperado=1/(1+10**((rb-ra-VENTAJA_LOCAL)/400))
        real=1 if p["resultado"]=="H" else 0.5 if p["resultado"]=="D" else 0
        margen=abs(p["goles_local"]-p["goles_visitante"])
        factor=1+0.15*max(0,margen-1)
        delta=K*factor*(real-esperado)
        cambios[a]+=delta;cambios[b]-=delta
    for equipo,delta in cambios.items():
        ratings[equipo]=ratings.get(equipo,1500.0)+delta

def ajustar(probs,elo_local,elo_visitante,peso):
    # Modificar odds relativas 1 vs 2; conservar X para aislar efecto de calidad de rival.
    # Elo incorpora ventaja local; restamos ventaja para no contarla dos veces en Poisson.
    diff=(elo_local-elo_visitante)/400
    factor=math.exp(peso*diff)
    a=probs[0]*factor;b=probs[1];c=probs[2]/factor
    z=a+b+c
    return [a/z,b/z,c/z]

def evaluar(partidos):
    dias=defaultdict(list)
    for p in partidos:dias[p["fecha"]].append(p)
    historico=[];ratings={}
    filas={k:[] for k in CONFIGS}
    for fecha,juegos in sorted(dias.items()):
        if len(historico)>=40:
            objetivos={(p["local"],p["visitante"]) for p in juegos}
            pred=calcular_liga(historico,min_partidos_equipo=3,objetivos=objetivos)
            indice={(p["local"],p["visitante"]):p for p in pred}
            for p in juegos:
                x=indice.get((p["local"],p["visitante"]))
                if not x:continue
                original=[x["probabilidades"][s]/100 for s in ("1","X","2")]
                real={"H":0,"D":1,"A":2}[p["resultado"]]
                for nombre,peso in CONFIGS.items():
                    probs=ajustar(original,ratings.get(p["local"],1500),ratings.get(p["visitante"],1500),peso)
                    elegido=max(range(3),key=lambda i:probs[i])
                    filas[nombre].append((int(elegido==real),sum((v-(i==real))**2 for i,v in enumerate(probs))))
        elo_actualizar(ratings,juegos)
        historico.extend(juegos)
    return filas

def main():
    reporte={"metodo":"Walk-forward por fecha, Elo K=20, ventaja local 65; Elo corrector de odds 1/2; empate intacto",
             "advertencia":"Variantes exploratorias: no se despliegan automáticamente; 2024/25 y 2025/26 por separado",
             "resultados":{}}
    for temporada in TEMPORADAS:
        for liga in LIGAS:
            partidos=descargar(liga,temporada)
            resultados=evaluar(partidos)
            clave=f"{temporada}_{liga}"
            reporte["resultados"][clave]={}
            for nombre,filas in resultados.items():
                n=len(filas);aciertos=sum(x[0] for x in filas)
                reporte["resultados"][clave][nombre]={"n":n,"aciertos":aciertos,
                    "porcentaje":round(100*aciertos/n,2) if n else None,
                    "brier":round(sum(x[1] for x in filas)/n,4) if n else None}
            print(clave,len(partidos),reporte["resultados"][clave],flush=True)
    reporte["totales"]={}
    for nombre in CONFIGS:
        n=sum(r[nombre]["n"] for r in reporte["resultados"].values())
        a=sum(r[nombre]["aciertos"] for r in reporte["resultados"].values())
        reporte["totales"][nombre]={"n":n,"aciertos":a,"porcentaje":round(100*a/n,2)}
    Path("data/experimento_elo.json").write_text(json.dumps(reporte,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("TOTALES",reporte["totales"],flush=True)

if __name__=="__main__":main()
