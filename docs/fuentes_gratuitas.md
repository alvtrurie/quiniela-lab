# Fuentes gratuitas candidatas para QUINIELA LAB

Revisión inicial: 2026-11-08. **No implica que exista API gratuita utilizable para cada fuente**.

| Fuente | Variables candidatas | Límites y cautelas | Prioridad |
|---|---|---|---|
| FootyStats | xG/xGA, tiros, tiros a puerta, estadísticas por equipo, cuotas históricas | API gratuita limitada; verificar cobertura SP1/SP2, permisos de uso y acceso antes de conectar | Alta, pendiente |
| Biwenger | Lesiones, sanciones, estados de jugadores | Estados orientativos, cambios continuos, comprobar condiciones de reutilización | Alta, pendiente |
| Biwtools | Onces probables, lesionados y dudas | Datos de LaLiga, requieren comprobar acceso y licencia; sin histórico garantizado | Alta, pendiente |
| Clausulazo | Onces, sanciones, lesiones, titularidad | Comprobar acceso, licencia y fiabilidad de pronósticos | Media, pendiente |
| Fantasy Tracker | Minutos, titularidades, estadísticas individuales | Datos parciales sin cuenta; comprobar disponibilidad y licencia | Media, pendiente |

## Requisitos para integrar

1. No utilizar scraping masivo ni endpoints privados/no autorizados.
2. Solo consumir fuentes gratuitas y con condiciones compatibles.
3. Guardar instante de captura y fecha de vigencia; no atribuir a un partido histórico datos actuales.
4. Alinear IDs y nombres de jugadores y equipos, y evitar duplicidades entre proveedores.
5. Diferenciar 'confirmado', 'probable' y 'dudoso' para bajas y alineaciones.
6. Introducir nuevas variables de forma opcional y medir Brier score, log loss y aciertos por columna en pruebas cronológicas.
7. Mantener Poisson actual como referencia; no cambiar producción hasta probar mejora fuera de muestra.

Fuentes:
- https://footystats.org/es/api
- https://footystats.org/es/api/documentations/faq
- https://www.biwenger.com/faq/jugadores-lesionados-o-sancionados/
- https://biwtools.es/
- https://clausulazo.es/
- https://fantasy-tracker.com/jugadores/
