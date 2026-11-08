"""Auditoría cronológica 2026/27, hasta la fecha de ejecución.
Categorías descriptivas, no causas demostradas. Sin resultados del mismo día.
"""
import csv,io,json,urllib.request
from collections import Counter,defaultdict
from datetime import date,datetime,timezone
from pathlib import Path
from pronosticos import calcular_liga

SEASON="2627"
TODAY=date.today()
def obtener(liga):
    url=f"https://www.football-data.co.uk/mmz4281/{SEASON}/{liga}.csv"
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=35) as r:
        raw=r.read().decode("utf-8-sig",errors="replace")
    out=[]
    for row in csv.DictReader(io.StringIO(raw)):
        try:
            fecha=datetime.strptime(row["Date"],"%d/%m/%Y").date()
            gl,gv=int(row["FTHG"]),int(row["FTAG"])
            if fecha>TODAY:continue
            out.append({"fecha":fecha.isoformat(),"local":row["HomeTeam"].strip(),
                "visitante":row["AwayTeam"].strip(),"goles_local":gl,"goles_visitante":gv,
                "resultado":"H" if gl>gv else "D" if gl==gv else "A"})
        except (ValueError,KeyError,TypeError):continue
    return out,url

def auditar(partidos):
    byday=defaultdict(list)
    for p in partidos:byday[p["fecha"]].append(p)
    hist=[];evaluados=[];omitidos=Counter()
    for fecha,group in sorted(byday.items()):
        if len(hist)<40:
            omitidos["menos_de_40_partidos_previos"]+=len(group)
        else:
            pred=calcular_liga(hist,min_partidos_equipo=3,objetivos={(p["local"],p["visitante"]) for p in group})
            ix={(x["local"],x["visitante"]):x for x in pred}
            for p in group:
                x=ix.get((p["local"],p["visitante"]))
                if x is None:
                    omitidos["equipo_con_menos_de_3_partidos_previos"]+=1;continue
                prob=x["probabilidades"];real={"H":"1","D":"X","A":"2"}[p["resultado"]]
                elegido=x["recomendado"];maxprob=prob[elegido]
                margen=maxprob-sorted(prob.values())[-2]
                # Clasificación mutuamente excluyente del fallo; no es diagnóstico causal.
                if real==elegido:tipo="acierto"
                elif real=="X":tipo="empate_no_pronosticado"
                elif elegido=="X":tipo="empate_pronosticado_sin_ocurrir"
                elif elegido=="1" and real=="2":tipo="victoria_visitante_inesperada"
                else:tipo="victoria_local_inesperada"
                evaluados.append({"fecha":fecha,"local":p["local"],"visitante":p["visitante"],
                    "marcador":f'{p["goles_local"]}-{p["goles_visitante"]}',
                    "real":real,"pronosticado":elegido,"probabilidades":prob,
                    "goles_esperados":x["goles_esperados"],"acierto":real==elegido,
                    "tipo":tipo,"confianza":maxprob,"margen_pp":round(margen,2),
                    "partido_ajustado":margen<10,
                    "favorito_fuerte_fallido":real!=elegido and maxprob>=55,
                    "probabilidad_real":prob[real]})
        hist.extend(group)
    return evaluados,dict(omitidos)

def resumen(rows):
    fallos=[x for x in rows if not x["acierto"]]
    tipos=Counter(x["tipo"] for x in fallos)
    return {"evaluados":len(rows),"aciertos":len(rows)-len(fallos),"fallos":len(fallos),
        "porcentaje":round(100*(len(rows)-len(fallos))/len(rows),2) if rows else None,
        "tipos_de_fallo":dict(tipos),
        "fallos_en_partidos_ajustados":sum(x["partido_ajustado"] for x in fallos),
        "fallos_con_confianza_55_o_mas":sum(x["favorito_fuerte_fallido"] for x in fallos),
        "empates_reales":sum(x["real"]=="X" for x in rows),
        "empates_pronosticados":sum(x["pronosticado"]=="X" for x in rows),
        "baseline_todos_local":sum(x["real"]=="1" for x in rows)}
def main():
    informe={"temporada":"2026/27","fecha_corte_utc":datetime.now(timezone.utc).isoformat(),
        "metodo":"Poisson de producción, walk-forward por fecha; entrenado solo con partidos de la misma liga en 2026/27",
        "alcance":"Primera y Segunda masculina; partidos individuales, no boletos oficiales",
        "advertencia":"Los tipos de fallo son patrones observables, NO explicaciones causales demostradas.",
        "ligas":{}}
    todos=[]
    for liga in ("SP1","SP2"):
        games,url=obtener(liga)
        rows,omitidos=auditar(games)
        informe["ligas"][liga]={"fuente":url,"partidos_finalizados":len(games),
            "omitidos":omitidos,"resumen":resumen(rows),"partidos":rows}
        todos+=rows
        print(liga,"partidos",len(games),"evaluados",len(rows),resumen(rows),flush=True)
    informe["global"]=resumen(todos)
    Path("data/auditoria_2026_27.json").write_text(json.dumps(informe,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("GLOBAL",informe["global"],flush=True)
if __name__=="__main__":main()
