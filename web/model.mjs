export function numberOf(v) {
  return Array.isArray(v) ? v[0] : typeof v === "number" ? v : null;
}
export function dollars(n) {
  return new Intl.NumberFormat("en-CA",{style:"currency",currency:"CAD",maximumFractionDigits:0}).format(n);
}
export function show(v) {
  const amount = numberOf(v);
  if (amount !== null) return dollars(amount) + (Array.isArray(v) ? " (" + v[1] + ")" : "");
  return ({x:"Suppressed", "...":"Not applicable", F:"Too unreliable to publish"})[v] || "Unavailable";
}
export function slug(name) {
  return name.toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g,"").replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"");
}
export function yearsFor(...series) {
  return [...new Set(series.flatMap(row => Object.keys(row || {})))].sort().reverse();
}
export function diffText(left, right, a, b) {
  const first=numberOf(a), second=numberOf(b);
  if(first===null || second===null) return "A comparison requires published figures for both places.";
  if(first===second) return "Both selections have the same published average.";
  return (first>second?left:right) + " is " + dollars(Math.abs(first-second)) + " higher for the year.";
}
