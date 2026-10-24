const els=[...document.querySelectorAll('.a')];
const ease=x=>x<=0?0:x>=1?1:1-Math.pow(1-x,3);
const cl=x=>Math.max(0,Math.min(1,x));
window.render=function(t){
  for(const e of els){const i=+e.dataset.in,o=+e.dataset.out;const pi=ease(cl((t-i)/0.55)),po=ease(cl((t-o)/0.35));
    e.style.opacity=pi*(1-po); e.style.transform=`translateY(${(1-pi)*50-po*30}px)`;}
  document.querySelectorAll('.grow').forEach(g=>{const k=ease(cl((t-g.dataset.t0)/2.6)); g.style.height=(12+88*k)+'%';});
  document.querySelectorAll('.cnt').forEach(c=>{const k=ease(cl((t-c.dataset.t0)/2.6)); const v=+c.dataset.from+(c.dataset.to-c.dataset.from)*k; c.textContent=Math.round(v)+' '+c.dataset.unit;});
  document.getElementById('prog').firstChild.style.width=(cl(t/TOTAL)*100)+'%';
  document.getElementById('glow').style.transform=`translate(${Math.sin(t/5)*60}px,${Math.cos(t/6)*50}px)`;
};
render(0);
