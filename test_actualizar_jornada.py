"""Pruebas sin red del extractor y la normalización."""
import unittest
from bs4 import BeautifulSoup
from actualizar_jornada import extraer_filas, fechas_tabla, coinciden, fuente_quinielafutbol, fuente_losilla, fuente_quiniprats

def tabla():
    filas = ''.join(
        f'<tr><td>{i}</td><td>Equipo {i} - Rival {i}</td><td>17/11/2026</td></tr>'
        for i in range(1, 16)
    )
    return '<table><tr><th>P.</th><th>Equipos</th><th>Fecha</th></tr>' + filas + '</table>'

class TestFuentes(unittest.TestCase):
    def test_quinielafutbol(self):
        soup = BeautifulSoup('<h2>JORNADA Nº 22 Martes</h2>'+tabla(), 'html.parser')
        resultado = fuente_quinielafutbol(soup)
        self.assertEqual(len(resultado[22]['partidos']), 15)
        self.assertEqual(str(resultado[22]['fechas'][0]), '2026-11-17')

    def test_losilla(self):
        soup = BeautifulSoup('<h1>JORNADA 22 - 26/27</h1>'+tabla(), 'html.parser')
        self.assertEqual(len(fuente_losilla(soup)[22]['partidos']), 15)

    def test_quiniprats(self):
        cuerpo = '<h1>Quiniela — Jornada 22</h1>'
        for i in range(1, 16):
            cuerpo += f'<section><h2>#{i}</h2><p>Equipo {i}</p><p>mar 17 nov · 19:45</p><p>Rival {i}</p></section>'
        cuerpo += '<p>La jornada se disputa entre el 17 noviembre y el 19 noviembre.</p>'
        encontrado = fuente_quiniprats(BeautifulSoup(cuerpo, 'html.parser'), 22)
        self.assertEqual(len(encontrado[22]['partidos']), 15)
        self.assertEqual(encontrado[22]['fechas'][1].isoformat(), '2026-11-19')

    def test_contraste(self):
        p = extraer_filas(BeautifulSoup(tabla(), 'html.parser').table)
        self.assertTrue(coinciden({'partidos':p},{'partidos':p}))
        q = dict(p)
        q[7] = ('Otro equipo','Rival 7')
        self.assertFalse(coinciden({'partidos':p},{'partidos':q}))

    def test_rechaza_incompleto(self):
        soup = BeautifulSoup('<h2>JORNADA Nº 22</h2><table><tr><td>1</td><td>A - B</td></tr></table>', 'html.parser')
        self.assertEqual(fuente_quinielafutbol(soup), {})

if __name__ == '__main__':
    unittest.main()
