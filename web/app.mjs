import {diffText, numberOf, show, slug, yearsFor} from "./model.mjs";

const el=(tag, value, cls) => {
  const node=document.createElement(tag);
  if (value != null) node.textContent=value;
  if (cls) node.className=cls;
  return node;
};
function anchor(path,label) {const a=el("a", label); a.href=path; return a;}
function select(form, name, list, preferred) {
  const input=form.elements[name];
  input.replaceChildren(...list.map(key=>new Option(key,key)));
  input.value=list.includes(preferred)?preferred:list[0];
  return input.value;
}
function table(headers, rows, caption) {
  const t=el("table");
  t.append(el("caption",caption));
  const head=t.createTHead().insertRow();
  for (const title of headers) {
    const th=el("th",title); th.scope="col"; head.append(th);
  }
  const body=t.createTBody();
  for(const [label,...values] of rows){
    const tr=body.insertRow(), th=el("th",label); th.scope="row"; tr.append(th);
    for(const value of values) tr.append(el("td",value));
  }
  return t;
}
function explorer(data,defaults) {
  const feeForm=document.querySelector("#fees"), incomeForm=document.querySelector("#income");
  const state={...defaults};
  function render(){
    const f=select(feeForm,"field",Object.keys(data.tuition),state.field), places=data.tuition[f];
    const left=select(feeForm,"left",Object.keys(places),state.left);
    const right=select(feeForm,"right",Object.keys(places),state.right);
    const years=yearsFor(places[left],places[right]);
    const y=select(feeForm,"year",years,state.year), a=places[left][y], b=places[right][y];
    const context=f+" · "+y+(data.preliminary.includes(y)?" · preliminary":"")+" · annual CAD";
    const body=document.querySelector("#tuition-output"),cards=el("div",null,"cards");
    const links=el("p",null,"result-links");
    for(const place of new Set([left,right])){
      if(Object.values(places[place]).some(v=>numberOf(v)!==null)){
        if(links.childNodes.length) links.append(" · ");
        links.append(anchor("./records/"+slug(f)+"/"+slug(place)+"/",place+" tuition history"));
      }
    }
    for (const [name,v] of [[left,a],[right,b]]) {
      const c=el("div",null,"card");c.append(el("span",name),el("strong",show(v)));cards.append(c);
    }
    body.replaceChildren(el("p",context,"context"),cards,el("p",diffText(left,right,a,b)),links);
    document.querySelector("#fee-history").replaceChildren(table(["Academic year",left,right],years.map(t=>[t+(data.preliminary.includes(t)?" (p)":""),show(places[left][t]),show(places[right][t])]),f+" annual tuition in current CAD · (p) preliminary"));
    const group=select(incomeForm,"incomeField",Object.keys(data.earnings),state.incomeField);
    const g=select(incomeForm,"incomePlace",Object.keys(data.earnings[group]),state.incomePlace);
    const byYear=data.earnings[group][g],cohort=select(incomeForm,"cohort",yearsFor(byYear),state.cohort);
    const rows=[2,5,10].map(n=>[n+" years ("+(Number(cohort)+n)+")",show(byYear[cohort][n])]);
    document.querySelector("#income-output").replaceChildren(table(["After graduation","Median income"],rows,group+" · "+g+" · "+cohort+" cohort · "+data.income_units),anchor("./records/graduate-income/"+slug(group)+"/","Read the full "+group.toLowerCase()+" graduate record"));
    Object.assign(state,{field:f,left,right,year:y,incomeField:group,incomePlace:g,cohort});
    feeForm.hidden=false;incomeForm.hidden=false;
  }
  function restore(){
    const params=new URLSearchParams(location.search);
    for(const k of ["field","left","right","year","incomeField","incomePlace","cohort"]) state[k]=params.get(k)||defaults[k];
    render();
  }
  function change(event){
    state[event.target.name]=event.target.value;
    render();
    const url=new URL(location.href);
    for(const [k,v] of Object.entries(state)) url.searchParams.set(k,v);
    history.replaceState(null,"",url);
  }
  feeForm.addEventListener("change",change);incomeForm.addEventListener("change",change);
  window.addEventListener("popstate",restore);
  restore();
}
try {
  const load=async path=>{const response=await fetch(path); if(!response.ok) throw Error(); return response.json();};
  const [data,defaults]=await Promise.all([load("./data/edition.json"),load("./settings.json")]);
  explorer(data,defaults);
} catch {
  document.querySelector("#load-note").prepend("Interactive comparisons could not load. ");
}
