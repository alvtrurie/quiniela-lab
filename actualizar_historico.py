"""Histórico de tres temporadas completadas para análisis descriptivo de enfrentamientos."""
import csv,io,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone
out={"actualizado":datetime.now(timezone.utc).isoformat(),"fuente":"football-data.co.uk","competiciones":{}}
for liga in ("SP1","SP2"):
    partidos=[]
    for temporada in ("2324","2425","2526"):
        url=f"https://www.football-data.co.uk/mmz4281/{temporada}/{liga}.csv"
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"QuinielaLab/1.0"})
            with urllib.request.urlopen(req,timeout=25) as response:
                raw=response.read().decode("utf-8-sig",errors="replace")
            for p in csv.DictReader(io.StringIO(raw)):
                if p.get("FTR") not in ("H","D","A") or not p.get("HomeTeam") or not p.get("AwayTeam"):continue
                try:gl=int(p["FTHG"]);gv=int(p["FTAG"])
                except (ValueError,TypeError):continue
                partidos.append({"fecha":p.get("Date"),"local":p["HomeTeam"],"visitante":p["AwayTeam"],"goles_local":gl,"goles_visitante":gv,"temporada":temporada})
            print(liga,temporada,"cargado")
        except Exception as e:print(liga,temporada,"no disponible",type(e).__name__)
    out["competiciones"][liga]=partidos
Path("data/historico.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
