/* Seguimiento local de resultados: solo datos introducidos por el usuario. */
const qlResultadosKey = "ql_resultados_v1";
function qlLeerResultados(){try{return JSON.parse(localStorage.getItem(qlResultadosKey)||"{}")}catch{return {}}}
function renderResultados(){
  if(!jornada?.partidos?.length){app.innerHTML='<div class="panel">No hay jornada disponible.</div>';return;}
  const numero=String(jornada.numero), todos=qlLeerResultados(), resultado=todos[numero]||{};
  const cols=columnas.filter(c=>c.jornada===jornada.numero);
  const completos=jornada.partidos.every(p=>["1","X","2"].includes(resultado[p.posicion]));
  app.innerHTML='<div class="panel"><h2>Resultados y aciertos · Jornada '+esc(numero)+'</h2>'+
    '<p class="muted">Introduce los resultados 1-X-2 cuando finalicen los partidos. Se guardan solo en este navegador. No son resultados oficiales ni se descargan automáticamente.</p>'+
    jornada.partidos.map(p=>'<div class="game"><div class="row"><strong>'+p.posicion+'. '+esc(p.local)+' — '+esc(p.visitante)+'</strong>'+
    '<select style="max-width:175px" data-ql-resultado="'+p.posicion+'"><option value="">Pendiente</option>'+
    ["1","X","2"].map(s=>'<option value="'+s+'" '+(resultado[p.posicion]===s?'selected':'')+'>'+s+'</option>').join('')+'</select></div></div>').join('')+
    '<div class="row"><button id="ql-clear">Borrar resultados de esta jornada</button></div></div>'+
    '<div class="panel"><h3>Evaluación de columnas guardadas</h3>'+
    (!cols.length?'<p class="muted">Todavía no tienes columnas generadas y guardadas para esta jornada.</p>':
    '<p class="muted">'+(completos?'Resultados completos.':'Evaluación parcial: faltan resultados.')+' No se evalúa el Pleno al 15.</p>'+
    '<div style="overflow-x:auto"><table><thead><tr><th>Columna</th><th>Aciertos</th><th>Evaluados</th></tr></thead><tbody>'+
    cols.map((c,i)=>{let evaluados=0,aciertos=0;for(let k=0;k<14;k++){let s=resultado[k+1];if(["1","X","2"].includes(s)){evaluados++;if(c.signos[k]===s)aciertos++;}}return '<tr><td>'+(i+1)+'</td><td>'+aciertos+'</td><td>'+evaluados+'/14</td></tr>';}).join('')+
    '</tbody></table></div>')+'</div>';
  document.querySelectorAll("[data-ql-resultado]").forEach(s=>s.onchange=()=>{const all=qlLeerResultados(),r=all[numero]||{};if(s.value)r[s.dataset.qlResultado]=s.value;else delete r[s.dataset.qlResultado];all[numero]=r;localStorage.setItem(qlResultadosKey,JSON.stringify(all));renderResultados();});
  document.getElementById("ql-clear").onclick=()=>{if(!confirm("¿Borrar los resultados introducidos para esta jornada?"))return;const all=qlLeerResultados();delete all[numero];localStorage.setItem(qlResultadosKey,JSON.stringify(all));renderResultados();};
}
