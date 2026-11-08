"""Experimento sin fuga de datos: comparar ajustes frente al Poisson original.\nReejecutar tras corrección de contador de partidos.\n"""
import json, math
from collections import defaultdict
from datetime import date
from pathlib import Path
from backtest_2025_26 import leer_sp, MIN_TRAIN
from pronosticos import calcular_liga

# Reejecución con recuento de partidos corregido.
VARIANTES = {
 "base":(None,0.0),
 "recencia_90d":(90,0.0),
 "recencia_180d":(180,0.0),
 "empate_mas_3pp":(None,0.03),
 "empate_menos_3pp":(None,-0.03),
 "recencia_180d_empate_mas_3pp":(180,0.03),
 "recencia_180d_empate_menos_3pp":(180,-0.03),
}
def simular(partidos):
    by_day=defaultdict(list)
    for p in partidos:by_day[p["fecha"]].append(p)
    history=[]; out={v:[] for v in VARIANTES}
    for fecha, games in sorted(by_day.items()):
        if len(history)>=MIN_TRAIN:
            targets={(p["local"],p["visitante"]) for p in games}
            for nombre,(half,draw) in VARIANTES.items():
                weights=([2**(-(date.fromisoformat(fecha)-date.fromisoformat(p["fecha"])).days/half) for p in history]
                         if half else None)
                preds=calcular_liga(history,min_partidos_equipo=3,objetivos=targets,pesos=weights,empate_extra=draw)
                index={(p["local"],p["visitante"]):p for p in preds}
                for p in games:
                    x=index.get((p["local"],p["visitante"]))
                    if not x:continue
                    probs=[x["probabilidades"][s]/100 for s in ("1","X","2")]
                    real={"H":0,"D":1,"A":2}[p["resultado"]]
                    guess=max(range(3),key=lambda i:probs[i])
                    out[nombre].append({"id":(fecha,p["local"],p["visitante"]),"acierto":int(real==guess),
                        "brier":sum((q-(i==real))**2 for i,q in enumerate(probs))})
        history.extend(games)
    return out

def main():
    result={"metodo":"Walk-forward por fecha, 2025/26, sin partidos futuros",
            "nota":"Experimentos exploratorios en misma temporada; no evidencia fuera de muestra para elegir hiperparámetros",
            "variantes":{}}
    for league in ("SP1","SP2"):
        matches,_=leer_sp(league)
        out=simular(matches)
        for name, rows in out.items():
            d=result["variantes"].setdefault(name,{"ligas":{},"evaluados":0,"aciertos":0,"suma_brier":0})
            n=len(rows);a=sum(x["acierto"] for x in rows);b=sum(x["brier"] for x in rows)
            d["ligas"][league]={"evaluados":n,"aciertos":a,"porcentaje":round(100*a/n,2),"brier":round(b/n,4)}
            d["evaluados"]+=n;d["aciertos"]+=a;d["suma_brier"]+=b
        print(league,{k:(len(v),sum(x["acierto"] for x in v)) for k,v in out.items()},flush=True)
    for d in result["variantes"].values():
        n=d["evaluados"];d["porcentaje"]=round(100*d["aciertos"]/n,2)
        d["brier"]=round(d.pop("suma_brier")/n,4)
    Path("data/experimento_modelo_2025_26.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("RESUMEN",[(k,v["porcentaje"],v["brier"]) for k,v in result["variantes"].items()],flush=True)
if __name__=="__main__":main()
