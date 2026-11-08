"""Comparar selectores de columnas sin confundir partidos consecutivos con jornadas oficiales.
Se forman bloques de 14 partidos cronológicos SOLO para experimento técnico.
Cada bloque usa datos anteriores a su primera fecha; nunca partidos del bloque.
"""
import csv,io,json,math,random,urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from pronosticos import calcular_liga

def datos(liga,temporada):
    url=f"https://www.football-data.co.uk/mmz4281/{temporada}/{liga}.csv"
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=30) as f:
        content=f.read().decode("utf-8-sig",errors="replace")
    rows=[]
    for r in csv.DictReader(io.StringIO(content)):
        try:
            d=datetime.strptime(r["Date"],"%d/%m/%Y").date().isoformat()
            h,a=int(r["FTHG"]),int(r["FTAG"])
            rows.append({"fecha":d,"local":r["HomeTeam"].strip(),"visitante":r["AwayTeam"].strip(),
                "goles_local":h,"goles_visitante":a,"resultado":"H" if h>a else "D" if h==a else "A"})
        except (KeyError,ValueError,TypeError):continue
    return sorted(rows,key=lambda x:x["fecha"])

def seleccionar(probs,limite,metodo):
    # Exacto en las candidatas más probables; diversidad maximiza cobertura de resultados
    # en lugar de solo la probabilidad conjunta de cada columna.
    signos="1X2"
    haz=[("",0.0)]
    for fila in probs:
        nuevo=[(s+signos[i],score+math.log(max(p,1e-12))) for s,score in haz for i,p in enumerate(fila) if p>0]
        nuevo.sort(key=lambda t:t[1],reverse=True)
        haz=nuevo[:max(600,limite*80)]
    if metodo=="probabilidad":
        return [x[0] for x in haz[:limite]]
    elegidas=[haz[0][0]]
    usados=set(elegidas)
    while len(elegidas)<limite:
        mejor=None;mejor_score=-1e99
        for signos_c,log in haz:
            if signos_c in usados:continue
            distancia=min(sum(a!=b for a,b in zip(signos_c,otro)) for otro in elegidas)
            # mismo objetivo de diversidad que el modo equilibrado existente
            score=log+0.22*min(4,distancia)
            if score>mejor_score:mejor_score=score;mejor=signos_c
        if mejor is None:break
        elegidas.append(mejor);usados.add(mejor)
    return elegidas

def cobertura_probabilistica(probs,limite,semilla=42):
    # Muestras Monte Carlo de resultados completos, sin conocer resultados reales.
    rng=random.Random(semilla)
    escenarios=[]
    for _ in range(350):
        s=""
        for fila in probs:
            u=rng.random()
            s+="1" if u<fila[0] else "X" if u<fila[0]+fila[1] else "2"
        escenarios.append(s)
    candidatos=set()
    candidatos.add("".join("1X2"[max(range(3),key=lambda i:p[i])] for p in probs))
    for _ in range(900):
        s=""
        for fila in probs:
            u=rng.random()
            s+="1" if u<fila[0] else "X" if u<fila[0]+fila[1] else "2"
        candidatos.add(s)
    # Maximiza aciertos esperados de la mejor columna, aproximados por escenarios.
    # Se evalúa el beneficio marginal de cada columna frente a las ya seleccionadas.
    elegidas=[];mejor_actual=[0]*len(escenarios)
    for _ in range(limite):
        ganador=None;ganancia=-1
        for candidato in candidatos:
            ganancia_c=sum(max(0,sum(a==b for a,b in zip(candidato,e))-actual)
                          for e,actual in zip(escenarios,mejor_actual))
            if ganancia_c>ganancia:
                ganador=candidato;ganancia=ganancia_c
        if ganador is None:break
        elegidas.append(ganador);candidatos.remove(ganador)
        mejor_actual=[max(actual,sum(a==b for a,b in zip(ganador,e)))
                      for e,actual in zip(escenarios,mejor_actual)]
    return elegidas

def evaluar(liga,temporada):
    games=datos(liga,temporada)
    # Bloques de fechas completas, para no usar resultados del mismo día.
    dias=defaultdict(list)
    for g in games:dias[g["fecha"]].append(g)
    hist=[];pendientes=[];bloques=[]
    for fecha,grupo in sorted(dias.items()):
        if len(hist)>=40:
            objetivos={(g["local"],g["visitante"]) for g in grupo}
            pred=calcular_liga(hist,min_partidos_equipo=3,objetivos=objetivos)
            ix={(x["local"],x["visitante"]):x for x in pred}
            for g in grupo:
                p=ix.get((g["local"],g["visitante"]))
                if p:
                    pendientes.append((g,[p["probabilidades"][s]/100 for s in "1X2"]))
        hist+=grupo
    # ATENCIÓN: cada predicción fue calculada antes de su partido, pero las
    # ventanas no son jornadas oficiales; la agrupación se realiza a posteriori.
    for i in range(0,len(pendientes)-13,14):
        bloque=pendientes[i:i+14]
        reales="".join({"H":"1","D":"X","A":"2"}[g["resultado"]] for g,_ in bloque)
        ps=[p for _,p in bloque]
        res={"reales":reales,"empates":reales.count("X")}
        for presupuesto,limite in ((3,4),(6,8),(10,13)):
            for metodo in ("probabilidad","diversidad","cobertura"):
                cols=cobertura_probabilistica(ps,limite,semilla=1000+i) if metodo=="cobertura" else seleccionar(ps,limite,metodo)
                scores=[sum(a==b for a,b in zip(c,reales)) for c in cols]
                res[f"{metodo}_{presupuesto}"]={"mejor":max(scores),"media":sum(scores)/len(scores),
                    "empates_por_columna":sum(c.count("X") for c in cols)/len(cols)}
        bloques.append(res)
    return bloques

def main():
    out={"advertencia":"Bloques artificiales de 14 partidos; NO jornadas oficiales ni premios reales.",
         "metodo":"Predicciones Poisson previas a cada partido, comparación de selección de columnas",
         "resultados":{}}
    for temporada in ("2425","2526","2627"):
        for liga in ("SP1","SP2"):
            bloques=evaluar(liga,temporada)
            if not bloques:continue
            d={"bloques":len(bloques),"empates_reales_promedio":round(sum(x["empates"] for x in bloques)/len(bloques),2)}
            for presupuesto in (3,6,10):
                for metodo in ("probabilidad","diversidad","cobertura"):
                    k=f"{metodo}_{presupuesto}"
                    d[k]={"mejor_media":round(sum(x[k]["mejor"] for x in bloques)/len(bloques),3),
                          "empates_columna_media":round(sum(x[k]["empates_por_columna"] for x in bloques)/len(bloques),3),
                          "bloques_10_o_mas":sum(x[k]["mejor"]>=10 for x in bloques)}
            out["resultados"][f"{temporada}_{liga}"]=d
            print(temporada,liga,d,flush=True)
    Path("data/experimento_selector.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":main()
