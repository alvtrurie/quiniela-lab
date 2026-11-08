/* Dashboard: únicamente estadísticas de partidos finalizados presentes en los datos publicados. */
function qlCanon(nombre){
  const alias={'valladolid':'valladolid','real valladolid':'valladolid','sp gijon':'sporting gijon','sporting gijon':'sporting gijon','sociedad b':'real sociedad b','real sociedad b':'real sociedad b','ath madrid':'atletico madrid','atletico madrid':'atletico madrid','ath bilbao':'athletic bilbao','athletic club':'athletic bilbao','la coruna':'deportivo la coruna','deportivo':'deportivo la coruna','espanol':'espanyol','oviedo':'oviedo','real oviedo':'oviedo','andorra':'andorra','fc andorra':'andorra','eibar':'eibar','sd eibar':'eibar','sociedad':'real sociedad','real sociedad':'real sociedad'};
  const k=claveEquipo(nombre).replace(/\s+f$/,'').replace(/\s+femenino$/,'');
  return alias[k]||k;
}
function qlFecha(s){
  if(!s)return 0;
  const v=String(s).split(/[\/\-]/);
  if(v.length!==3)return 0;
  const iso=v[0].length===4?v[0]+'-'+v[1]+'-'+v[2]:(v[2].length===2?'20'+v[2]:v[2])+'-'+v[1]+'-'+v[0];
  return Date.parse(iso+'T12:00:00Z')||0;
}
function qlHistorial(p){
  if(!p?.liga)return null;
  const filas=stats?.competiciones?.[p.liga];
  if(!Array.isArray(filas))return null;
  const cutoff=qlFecha(jornada?.fecha_inicio)||Date.now();
  const local=qlCanon(p.local), visitante=qlCanon(p.visitante);
  const prev=historico?.competiciones?.[p.liga]||[];
  const matches=[...filas,...prev].filter(x=>x&&Number.isFinite(+x.goles_local)&&Number.isFinite(+x.goles_visitante)&&
    x.goles_local!==''&&x.goles_visitante!==''&&qlFecha(x.fecha)<cutoff)
    .map(x=>({...x,home:qlCanon(x.local),away:qlCanon(x.visitante),gl:+x.goles_local,gv:+x.goles_visitante}))
    .sort((a,b)=>qlFecha(b.fecha)-qlFecha(a.fecha));
  const equipo=(nombre,ambito)=>matches.filter(x=>(ambito==='casa'?x.home===nombre:ambito==='fuera'?x.away===nombre:x.home===nombre||x.away===nombre));
  const h2h=matches.filter(x=>(x.home===local&&x.away===visitante)||(x.home===visitante&&x.away===local));
  return {local,visitante,localUlt:equipo(local).slice(0,5),visUlt:equipo(visitante).slice(0,5),
    casa:equipo(local,'casa'),fuera:equipo(visitante,'fuera'),h2h,localTodos:equipo(local),visTodos:equipo(visitante),total:matches.length};
}
function qlResumenEstadistico(partidos,nombre){
  const r={pj:partidos.length,g:0,e:0,p:0,gf:0,gc:0,mas25:0,ambos:0,porterias0:0};
  for(const x of partidos){
    const casa=x.home===nombre,gf=casa?x.gl:x.gv,gc=casa?x.gv:x.gl;
    r.gf+=gf;r.gc+=gc;
    if(gf>gc)r.g++;else if(gf===gc)r.e++;else r.p++;
    if(gf+gc>2.5)r.mas25++;
    if(gf>0&&gc>0)r.ambos++;
    if(gc===0)r.porterias0++;
  }
  return r;
}
function qlN(n){return Number(n).toFixed(2).replace('.',',')}
function qlPct(a,b){return b?(100*a/b).toFixed(0)+'%':'—'}
function qlRacha(xs,nombre){
  if(!xs.length)return '<span class="muted">Sin partidos registrados</span>';
  return xs.map(x=>{
    const gf=x.home===nombre?x.gl:x.gv,gc=x.home===nombre?x.gv:x.gl;
    const signo=gf>gc?'V':gf===gc?'E':'D';
    return '<span class="racha '+(signo==='V'?'racha-v':signo==='E'?'racha-e':'racha-d')+'" title="'+esc(x.local)+' '+x.gl+'-'+x.gv+' '+esc(x.visitante)+'">'+signo+'</span>';
  }).join('');
}
function qlStatEquipo(xs,nombre,titulo){
  const s=qlResumenEstadistico(xs,nombre);
  return '<div class="stat"><strong>'+esc(titulo)+'</strong><p class="muted small">'+s.pj+' partidos · '+s.g+'V / '+s.e+'E / '+s.p+'D</p>'+
  '<div class="metric"><span>Goles a favor / partido</span><b>'+(s.pj?qlN(s.gf/s.pj):'—')+'</b></div>'+
  '<div class="metric"><span>Goles en contra / partido</span><b>'+(s.pj?qlN(s.gc/s.pj):'—')+'</b></div>'+
  '<div class="metric"><span>Más de 2,5 goles</span><b>'+qlPct(s.mas25,s.pj)+'</b></div>'+
  '<div class="metric"><span>Ambos marcan</span><b>'+qlPct(s.ambos,s.pj)+'</b></div>'+
  '<div class="metric"><span>Portería a cero</span><b>'+qlPct(s.porterias0,s.pj)+'</b></div></div>';
}
function qlTablaPartidos(xs,max=8){
  if(!xs.length)return '<p class="muted">No hay enfrentamientos registrados en esta temporada.</p>';
  return '<div style="overflow-x:auto"><table><thead><tr><th>Fecha</th><th>Local</th><th>Resultado</th><th>Visitante</th></tr></thead><tbody>'+
    xs.slice(0,max).map(x=>'<tr><td>'+esc(x.fecha)+'</td><td>'+esc(x.local)+'</td><td><strong>'+x.gl+' – '+x.gv+'</strong></td><td>'+esc(x.visitante)+'</td></tr>').join('')+'</tbody></table></div>';
}
function qlBarras(probs){
  return '<div class="bar-grid">'+['1','X','2'].map((s,i)=>{
    const v=Math.max(0,Math.min(100,Number(probs[s])||0));
    return '<div class="bar-item"><div class="bar-head"><b>'+s+'</b><strong>'+v.toFixed(1)+'%</strong></div><div class="bar-track"><div class="bar-fill bar-'+i+'" style="width:'+v+'%"></div></div></div>';
  }).join('')+'</div>';
}
function qlDashboard(p,pr){
  const hist=qlHistorial(p),coverage=data?.cobertura_xg?.[p.liga];
  let out='<section class="dashboard"><h3>Probabilidades del modelo</h3>'+qlBarras(pr.probabilidades)+
    '<div class="grid"><div class="stat"><strong>Goles esperados · '+esc(p.local)+'</strong><h2>'+esc(pr.goles_esperados?.local??'—')+'</h2></div>'+
    '<div class="stat"><strong>Goles esperados · '+esc(p.visitante)+'</strong><h2>'+esc(pr.goles_esperados?.visitante??'—')+'</h2></div></div>'+
    '<p><strong>Lectura:</strong> '+esc(qlResumen(p))+'</p>';
  if(hist){
    out+='<h3>Momento de forma · últimos 5 partidos</h3><div class="grid">'+
      '<div class="stat"><strong>'+esc(p.local)+'</strong><p>'+qlRacha(hist.localUlt,hist.local)+'</p><p class="small muted">Del más reciente al más antiguo</p></div>'+
      '<div class="stat"><strong>'+esc(p.visitante)+'</strong><p>'+qlRacha(hist.visUlt,hist.visitante)+'</p><p class="small muted">Del más reciente al más antiguo</p></div></div>'+
      '<h3>Rendimiento en casa y fuera</h3><div class="grid">'+qlStatEquipo(hist.casa,hist.local,p.local+' · local')+
      qlStatEquipo(hist.fuera,hist.visitante,p.visitante+' · visitante')+'</div>'+
      '<h3>Estadísticas de temporada</h3><div class="grid">'+qlStatEquipo(hist.localTodos,hist.local,p.local+' · total')+
      qlStatEquipo(hist.visTodos,hist.visitante,p.visitante+' · total')+'</div>'+
      '<h3>Enfrentamientos directos</h3><p class="muted small">'+hist.h2h.length+' enfrentamientos en las temporadas disponibles (actual y hasta tres anteriores). No equivale al historial completo entre ambos clubes.</p>'+
      qlTablaPartidos(hist.h2h)+
      '<h3>Últimos resultados</h3><div class="grid"><div><h4>'+esc(p.local)+'</h4>'+qlTablaPartidos(hist.localUlt,5)+'</div>'+
      '<div><h4>'+esc(p.visitante)+'</h4>'+qlTablaPartidos(hist.visUlt,5)+'</div></div>';
  }else{
    out+='<h3>Forma, tendencias e histórico</h3><p class="muted">No hay una fuente histórica compatible y verificada para este enfrentamiento. No se muestran datos estimados como si fueran hechos.</p>';
  }
  out+='<h3>Disponibilidad y contexto</h3><div class="grid">'+
    '<div class="stat"><strong>Lesiones y bajas</strong><p class="muted small">Sin información verificada para este partido.</p></div>'+
    '<div class="stat"><strong>Sanciones</strong><p class="muted small">Sin información verificada para este partido.</p></div>'+
    '<div class="stat"><strong>Rivalidad y contexto</strong><p class="muted small">Sin fuente contrastada para clasificar el enfrentamiento.</p></div></div>'+
    '<h3>Fuentes y fiabilidad</h3><p class="muted small">Resultados históricos: football-data.co.uk, temporada '+esc(stats?.temporada||'actual')+' y hasta tres temporadas anteriores+
    '. Solo se utilizan partidos finalizados anteriores a la jornada. '+
    (coverage?'Cobertura xG PitchAPI: '+coverage.partidos_con_xg+' de '+coverage.partidos_totales+' partidos de liga emparejados.':'No consta cobertura xG en esta competición.')+
    ' Los porcentajes son estimaciones del modelo, no cuotas de apuestas. No se ha validado aquí el historial de lesiones ni sanciones.</p></section>';
  return out;
}
