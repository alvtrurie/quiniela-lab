/* Motor de columnas de Quiniela Lab. Sin servicios de pago ni probabilidades inventadas. */
const QL_PRECIO = 0.75;
let qlPresupuesto = 6;
let qlModo = "prudente";
let qlManual = {};
let qlUltimo = [];
let qlJornada = null;
function qlValida() {
  return jornada?.estado === "verificada" && estadoJornada?.publicable === true &&
    jornada?.fecha_fin >= new Date().toLocaleDateString("en-CA", {timeZone:"Europe/Madrid"}) &&
    Array.isArray(jornada?.partidos) && jornada.partidos.length === 14;
}
function qlProb(p) {
  const r = pronosticoPartido(p);
  if (!r) return null;
  const a = ["1","X","2"].map(s=>Number(r.probabilidades?.[s])/100);
  if (a.some(x=>!Number.isFinite(x)||x<0)||Math.abs(a.reduce((x,y)=>x+y,0)-1)>.03) return null;
  return a;
}
function qlOpciones(p) {
  const probs = qlProb(p);
  if (probs) return {probs, estimada:true, fuente:"Poisson · ligas españolas"};
  const manual = qlManual[p.posicion];
  if (manual && ["1","X","2"].includes(manual))
    return {probs:["1","X","2"].map(s=>s===manual?1:0),estimada:false,fuente:"Signo fijado por ti · sin modelo"};
  return {probs:null,estimada:false,fuente:"Sin modelo · debes elegir un signo"};
}
function qlCobertura() {
  return jornada.partidos.map(p=>({partido:p, ...qlOpciones(p)}));
}
function qlClasificacion(p) {
  if (!p) return "Sin estimación";
  const sorted=[...p].sort((a,b)=>b-a);
  return sorted[0]>=.62?"Favorito claro":sorted[0]-sorted[1]<.09?"Muy igualado":sorted[0]>=.48?"Favorito moderado":"Partido abierto";
}
function qlMotor(filas, presupuesto, modo) {
  const limite=Math.max(1,Math.min(100,Math.floor((Number(presupuesto)+1e-9)/QL_PRECIO)));
  if(filas.length!==14||filas.some(f=>!f.probs)) return [];
  const signos=["1","X","2"];
  // Búsqueda en haz: maximiza la probabilidad estimada conjunta; nunca afirma rentabilidad.
  let haz=[{signos:[],log:0}];
  for(const f of filas){
    const next=[];
    for(const col of haz) for(let i=0;i<3;i++) if(f.probs[i]>0)
      next.push({signos:[...col.signos,signos[i]],log:col.log+Math.log(f.probs[i])});
    next.sort((a,b)=>b.log-a.log);
    haz=next.slice(0,Math.max(600,limite*80));
  }
  if(!haz.length) return [];
  const elegidas=[haz[0]];
  const usados=new Set([haz[0].signos.join("")]);
  const penalidad=modo==="diverso"?.50:modo==="equilibrado"?.22:.06;
  while(elegidas.length<limite){
    let mejor=null,score=-Infinity;
    for(const candidata of haz){
      const key=candidata.signos.join("");
      if(usados.has(key))continue;
      const distancia=Math.min(...elegidas.map(c=>c.signos.reduce((n,s,i)=>n+(s!==candidata.signos[i]),0)));
      const puntos=candidata.log+penalidad*Math.min(4,distancia);
      if(puntos>score){score=puntos;mejor=candidata;}
    }
    if(!mejor)break;
    elegidas.push(mejor);usados.add(mejor.signos.join(""));
  }
  return elegidas;
}
function qlExplicacion(f) {
  if(!f.probs) return "No hay datos de esta competición. Elige manualmente 1, X o 2 para generar columnas.";
  if(!f.estimada) return "Signo decidido manualmente; no se ha calculado su probabilidad.";
  const ord=["1","X","2"].map((s,i)=>({s,p:f.probs[i]})).sort((a,b)=>b.p-a.p);
  return "El signo "+ord[0].s+" es el más probable ("+(ord[0].p*100).toFixed(1)+"%). "+
    (ord[0].p-ord[1].p<.10?"La diferencia con "+ord[1].s+" es pequeña: partido igualado.":"El segundo signo es "+ord[1].s+" ("+(ord[1].p*100).toFixed(1)+"%).");
}
function qlTextoColumnas(cols) {
  return cols.map((c,i)=>"Columna "+(i+1)+": "+c.signos.join(" ")+" | Pleno "+pleno.join("-")).join("\n");
}
function renderRadar() {
  if(!qlValida()){
    app.innerHTML='<div class="panel"><h2>Generador inteligente</h2><p class="error">No hay una jornada vigente y validada. No generamos columnas sobre partidos caducados o sin confirmar.</p></div>';
    return;
  }
  if(qlJornada!==jornada.numero){qlManual={};qlUltimo=[];qlJornada=jornada.numero;}
  const filas=qlCobertura(), cubiertos=filas.filter(f=>f.estimada).length, faltan=filas.filter(f=>!f.probs).length;
  const max=Math.floor(qlPresupuesto/QL_PRECIO);
  app.innerHTML='<div class="panel"><h2>Generador inteligente · Jornada '+esc(jornada.numero)+'</h2>'+
    '<p class="muted">Elige un presupuesto y construye columnas sin repetir. Coste: 0,75 € por columna sencilla. Las probabilidades son estimaciones, no garantías.</p>'+
    '<div class="grid"><div><label>Presupuesto máximo</label><select id="ql-budget">'+
    [3,6,10].map(v=>'<option value="'+v+'" '+(qlPresupuesto===v?'selected':'')+'>'+v+' € · hasta '+Math.floor(v/QL_PRECIO)+' columnas</option>').join('')+
    '</select></div><div><label>Estrategia</label><select id="ql-mode">'+
    [['prudente','Más probables'],['equilibrado','Equilibrada'],['diverso','Mayor variedad']].map(([v,n])=>'<option value="'+v+'" '+(qlModo===v?'selected':'')+'>'+n+'</option>').join('')+
    '</select></div></div><p class="small muted">'+cubiertos+'/14 partidos con probabilidades propias · '+faltan+' requieren tu elección manual. No usamos porcentajes ficticios.</p>'+
    '<div id="ql-matches">'+filas.map(f=>'<div class="game"><div class="row"><strong>'+f.partido.posicion+'. '+esc(f.partido.local)+' — '+esc(f.partido.visitante)+'</strong></div>'+
    (f.probs&&f.estimada?'<div class="probs">'+["1","X","2"].map((s,i)=>'<span>'+s+': '+(f.probs[i]*100).toFixed(1)+'%</span>').join('')+'</div><div class="small success">'+qlClasificacion(f.probs)+'</div>':
    '<div class="small error">'+esc(f.fuente)+'</div><label>Tu pronóstico para este partido</label><select data-ql-manual="'+f.partido.posicion+'"><option value="">Selecciona un signo</option>'+
    ["1","X","2"].map(s=>'<option value="'+s+'" '+(qlManual[f.partido.posicion]===s?'selected':'')+'>'+s+'</option>').join('')+'</select>')+
    '<p class="muted small">'+esc(qlExplicacion(f))+'</p></div>').join('')+'</div>'+
    '<div class="row"><button class="primary" id="ql-generate" '+(faltan?'disabled':'')+'>Generar hasta '+max+' columnas</button>'+
    '<button id="ql-autofill">Preparar signos más probables</button></div>'+
    '<p class="small muted">Los dobles y triples se representan repartiendo signos entre columnas distintas. No se crean apuestas múltiples oficiales ni reducciones garantizadas.</p></div>'+
    '<div class="panel" id="ql-output"><h3>Columnas propuestas</h3><p class="muted">Completa los partidos sin modelo y pulsa Generar.</p></div>';
  document.getElementById("ql-budget").onchange=e=>{qlPresupuesto=Number(e.target.value);qlUltimo=[];renderRadar();};
  document.getElementById("ql-mode").onchange=e=>{qlModo=e.target.value;qlUltimo=[];renderRadar();};
  document.querySelectorAll("[data-ql-manual]").forEach(s=>s.onchange=()=>{if(s.value)qlManual[+s.dataset.qlManual]=s.value;else delete qlManual[+s.dataset.qlManual];qlUltimo=[];renderRadar();});
  document.getElementById("ql-autofill").onclick=()=>{for(const f of filas)if(f.estimada){}else if(!qlManual[f.partido.posicion])qlManual[f.partido.posicion]="X";qlUltimo=[];renderRadar();};
  document.getElementById("ql-generate").onclick=()=>{
    qlUltimo=qlMotor(qlCobertura(),qlPresupuesto,qlModo);
    const coste=(qlUltimo.length*QL_PRECIO).toFixed(2).replace(".",",");
    document.getElementById("ql-output").innerHTML='<h3>'+qlUltimo.length+' columnas · '+coste+' €</h3>'+
      '<p class="small muted">Ordenadas por puntuación del modelo; la cobertura es parcial cuando has fijado signos manualmente. Pleno al 15: '+esc(jornada.pleno.local)+' — '+esc(jornada.pleno.visitante)+'. Debes escoger sus goles.</p>'+
      '<div class="grid">'+[0,1].map(i=>'<div><label>Pleno: '+(i?'visitante':'local')+'</label><select data-ql-pleno="'+i+'">'+opts(['0','1','2','M'],pleno[i])+'</select></div>').join('')+'</div>'+
      '<div style="overflow-x:auto"><table><thead><tr><th>#</th><th>Signos (1–14)</th></tr></thead><tbody>'+
      qlUltimo.map((c,i)=>'<tr><td>'+(i+1)+'</td><td style="white-space:nowrap;font-family:monospace">'+c.signos.map(esc).join(' · ')+'</td></tr>').join('')+
      '</tbody></table></div><div class="row"><button class="primary" id="ql-save">Guardar columnas</button><button id="ql-copy">Copiar</button><button id="ql-csv">Exportar CSV</button></div>';
    document.querySelectorAll("[data-ql-pleno]").forEach(s=>s.onchange=()=>{pleno[+s.dataset.qlPleno]=s.value;});
    document.getElementById("ql-save").onclick=()=>{
      columnas.push(...qlUltimo.map(c=>({signos:[...c.signos],pleno:[...pleno],jornada:jornada.numero,fecha:new Date().toISOString(),origen:"generador"})));
      save();document.getElementById("ql-save").disabled=true;document.getElementById("ql-save").textContent="Guardadas";
    };
    document.getElementById("ql-copy").onclick=()=>navigator.clipboard.writeText(qlTextoColumnas(qlUltimo)).then(()=>{document.getElementById("ql-copy").textContent="Copiado";}).catch(()=>window.prompt("Copia las columnas:",qlTextoColumnas(qlUltimo)));
    document.getElementById("ql-csv").onclick=()=>{
      const csv="columna;"+Array.from({length:14},(_,i)=>"partido_"+(i+1)).join(";")+";pleno_local;pleno_visitante\n"+
        qlUltimo.map((c,i)=>[i+1,...c.signos,...pleno].join(";")).join("\n");
      const url=URL.createObjectURL(new Blob(["\ufeff"+csv],{type:"text/csv;charset=utf-8"}));
      const a=document.createElement("a");a.href=url;a.download="quiniela-j"+jornada.numero+".csv";a.click();URL.revokeObjectURL(url);
    };
  };
}
