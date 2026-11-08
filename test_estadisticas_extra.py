import unittest
from datetime import date
from unittest.mock import patch
import estadisticas_extra as ex

class TestExtra(unittest.TestCase):
    def test_completados_sin_inventar(self):
        def ev(i, estado, score):
            return {"id":str(i),"date":"2026-11-02T12:00:00Z",
                    "competitions":[{"status":{"type":{"completed":estado}},
                    "competitors":[
                        {"homeAway":"home","score":str(score),"team":{"displayName":"Equipo A"}},
                        {"homeAway":"away","score":"1","team":{"displayName":"Equipo B"}}
                    ]}]}
        rows=ex.parse_events({"events":[ev(1,True,2),ev(2,False,3)]},date(2026,11,8))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["resultado"],"H")
    def test_rechaza_sin_eventos(self):
        with self.assertRaises(ValueError):
            ex.parse_events({"message":"error"},date(2026,11,8))
    def test_liga_fuente_espn(self):
        self.assertEqual(ex.LEAGUES["LIGAF"],"esp.w.1")
        self.assertEqual(set(ex.LEAGUES),{"LIGAF","UCL","UEL","UECL"})
    def test_descarga_y_deduplica(self):
        event={"id":"123","date":"2026-09-02T12:00:00Z","competitions":[{"status":{"type":{"completed":True}},"competitors":[{"homeAway":"home","score":"0","team":{"displayName":"A"}},{"homeAway":"away","score":"0","team":{"displayName":"B"}}]}]}
        with patch.object(ex,"request_json",return_value={"events":[event,event]}) as mock:
            rows,url=ex.obtener_liga("esp.w.1",date(2026,11,8))
        self.assertEqual(len(rows),1)
        self.assertIn("esp.w.1",url)
        self.assertIn("dates=2026",url)
if __name__=="__main__":
    unittest.main()
