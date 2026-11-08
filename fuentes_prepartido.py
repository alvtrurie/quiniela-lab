"""Validación de observaciones prepartido de fuentes gratuitas.
No descarga ni reutiliza contenido de terceros sin permiso.
"""
from datetime import datetime, timezone
from typing import Mapping

FUENTES = {
    "biwtools": {"tipo": ("alineacion_probable", "baja", "duda"), "competicion": ("SP1",)},
    "asesorias_fantasy": {"tipo": ("alineacion_probable", "baja", "sancion"), "competicion": ("SP1", "SP2")},
    "pitchapi": {"tipo": ("xg", "xga"), "competicion": ("SP1", "SP2")},
}
ESTADOS = {"confirmado", "probable", "dudoso"}

def validar_observacion(registro: Mapping, inicio_partido: str):
    """Retorna copia normalizada. Exige evidencia de captura ANTES del inicio.
    No permite backtests a partir de páginas actuales sin histórico fechado.
    """
    requeridos = ("fuente", "competicion", "equipo", "tipo", "capturado_en", "valor", "url_origen")
    faltan = [k for k in requeridos if not registro.get(k)]
    if faltan:
        raise ValueError("Campos obligatorios ausentes: " + ", ".join(faltan))
    fuente = str(registro["fuente"])
    cfg = FUENTES.get(fuente)
    if not cfg or registro["tipo"] not in cfg["tipo"] or registro["competicion"] not in cfg["competicion"]:
        raise ValueError("Fuente/tipo/competición no admitidos o cobertura no validada")
    def fecha(valor):
        d = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        if d.tzinfo is None:
            raise ValueError("Las fechas deben incluir zona horaria")
        return d.astimezone(timezone.utc)
    captura = fecha(registro["capturado_en"])
    inicio = fecha(inicio_partido)
    if captura >= inicio:
        raise ValueError("Filtración temporal: dato capturado al comenzar o después del partido")
    if registro.get("estado") and registro["estado"] not in ESTADOS:
        raise ValueError("Estado no reconocido")
    if not str(registro["url_origen"]).startswith("https://"):
        raise ValueError("Se requiere URL HTTPS de procedencia")
    return dict(registro, capturado_en=captura.isoformat(), inicio_partido=inicio.isoformat())

if __name__ == "__main__":
    import unittest
    class Test(unittest.TestCase):
        def setUp(self):
            self.reg = {"fuente":"biwtools","competicion":"SP1","equipo":"Equipo A",
                "tipo":"baja","capturado_en":"2026-11-07T18:00:00+01:00",
                "valor":"Jugador B","url_origen":"https://biwtools.es/"}
        def test_prepartido(self):
            self.assertEqual(validar_observacion(self.reg,"2026-11-08T18:00:00+01:00")["tipo"],"baja")
        def test_futuro(self):
            with self.assertRaises(ValueError):
                validar_observacion(self.reg,"2026-11-06T18:00:00+01:00")
        def test_sin_fecha(self):
            with self.assertRaises(ValueError):
                validar_observacion(dict(self.reg,capturado_en="2026-11-07T18:00:00"),"2026-11-08T18:00:00+01:00")
    unittest.main()
