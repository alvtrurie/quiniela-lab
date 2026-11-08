const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("generador.js", "utf8");
const context = {console};
vm.createContext(context);
vm.runInContext(source + "\nthis.motor=qlMotor; this.opciones=qlOpciones;", context);
const filas = Array.from({length:14},(_,i)=>({partido:{posicion:i+1},probs:[.54,.26,.20],estimada:true}));
for (const [euros,max] of [[3,4],[6,8],[10,13]]) {
  const cols=context.motor(filas,euros,"equilibrado");
  assert.equal(cols.length,max);
  assert.equal(new Set(cols.map(c=>c.signos.join(""))).size,max);
  assert.ok(cols.every(c=>c.signos.length===14 && c.signos.every(s=>["1","X","2"].includes(s))));
}
assert.equal(context.motor([...filas.slice(0,13),{partido:{posicion:14},probs:null}],6,"prudente").length,0);
const fijo=filas.map((f,i)=>i===0?{...f,probs:[0,1,0]}:f);
assert.ok(context.motor(fijo,6,"diverso").every(c=>c.signos[0]==="X"));
console.log("Motor: presupuestos, unicidad, ausencia de estimaciones y signos manuales OK");

const html=fs.readFileSync("index.html","utf8");
const inline = [null, html.split("<script>")[1]?.split("</script>")[0]];
assert.ok(inline,"No se encontró script principal");
new vm.Script(inline[1],{filename:"index.html:inline"});
assert.match(html,/src="\\.\\/generador\\.js"/);
assert.match(html,/src="\\.\\/resultados\\.js"/);
assert.match(html,/data-tab="radar"/);
assert.match(html,/data-tab="resultados"/);
console.log("Integración HTML: script y pestañas correctos");
