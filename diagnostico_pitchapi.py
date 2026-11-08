"""Diagnóstico mínimo de xG por liga: no guarda claves ni datos personales."""
import json
from pitchapi_cliente import partidos_liga, tiros_partido
for nombre, lid in (("SP1","l_0ErfuF"),("SP2","l_3kyHLd")):
    try:
        matches=partidos_liga(lid,"2025/2026")
        print(json.dumps({"liga":nombre,"partidos_recibidos":len(matches),
                          "campos_partido":list(matches[0]) if matches else [],
                          "ejemplo_id":matches[0].get("id") if matches else None},ensure_ascii=False))
        if matches and matches[0].get("id"):
            try:
                shots=tiros_partido(str(matches[0]["id"]))
                print(json.dumps({"liga":nombre,"campos_tiros":list(shots) if isinstance(shots,dict) else type(shots).__name__,
                                  "tipo_tiros":type(shots).__name__, "muestra_periodos":str(shots.get("periods",[]))[:1200]},ensure_ascii=False))
            except Exception as e:print(json.dumps({"liga":nombre,"error_tiros":str(e)}))
    except Exception as e:print(json.dumps({"liga":nombre,"error_partidos":str(e)}))
