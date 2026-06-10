/* ============================================================
   SPEECHLESS COCKPIT — engine
   ============================================================ */
(() => {
'use strict';
const $ = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => [...r.querySelectorAll(s)];
const clamp = (v,a,b) => Math.min(b, Math.max(a, v));
const lerp = (a,b,t) => a + (b-a)*t;
const delay = ms => new Promise(r => setTimeout(r, ms));
const pad2 = n => String(n).padStart(2,'0');

/* ---------- scale stage to viewport ---------- */
const stage = $('#stage');
function scale(){
  const s = Math.min(innerWidth/1920, innerHeight/1080);
  stage.style.transform = `translate(-50%,-50%) scale(${s})`;
}
addEventListener('resize', scale); scale();

/* ---------- clock ---------- */
function tickClock(){
  const d = new Date();
  $('#clock-time').textContent = `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}
tickClock(); setInterval(tickClock, 15000);

/* ============================================================
   SPEEDOMETER geometry
   ============================================================ */
const G_MIN=-125, G_MAX=125, V_MAX=200, CX=180, CY=180;
const polar = (r,g) => { const a=(g-90)*Math.PI/180; return {x:CX+r*Math.cos(a), y:CY+r*Math.sin(a)}; };
const speedToG = v => G_MIN + (clamp(v,0,V_MAX)/V_MAX)*(G_MAX-G_MIN);
function arcPath(r){
  const p0=polar(r,G_MIN), p1=polar(r,G_MAX);
  return `M ${p0.x.toFixed(2)} ${p0.y.toFixed(2)} A ${r} ${r} 0 1 1 ${p1.x.toFixed(2)} ${p1.y.toFixed(2)}`;
}
function buildSpeedo(){
  const R=138;
  $('#speed-track').setAttribute('d', arcPath(R));
  const fill = $('#speed-fill'); fill.setAttribute('d', arcPath(R));
  fillLen = fill.getTotalLength();
  fill.style.strokeDasharray = fillLen;
  fill.style.strokeDashoffset = fillLen;
  // ticks + labels
  const tg = $('#speed-ticks'); let svg='';
  for(let v=0; v<=V_MAX; v+=10){
    const g=speedToG(v), major=v%50===0;
    const o=polar(major?122:120, g), i=polar(major?104:110, g);
    svg += `<line class="tick${major?' major':''}" x1="${o.x.toFixed(1)}" y1="${o.y.toFixed(1)}" x2="${i.x.toFixed(1)}" y2="${i.y.toFixed(1)}"/>`;
    if(major){ const l=polar(88,g); svg += `<text class="tick-label" x="${l.x.toFixed(1)}" y="${l.y.toFixed(1)}" text-anchor="middle" dominant-baseline="central">${v}</text>`; }
  }
  tg.innerHTML = svg;
}
let fillLen=0;
function renderSpeed(v){
  const g=speedToG(v);
  $('#speed-needle').style.transform = `rotate(${g}deg)`;
  $('#speed-fill').style.strokeDashoffset = fillLen*(1 - clamp(v,0,V_MAX)/V_MAX);
  const num=$('#speed-num'); num.textContent=Math.round(v);
  num.className = 'speed-num' + (v>=160?' crit':v>=100?' warn':'');
}

/* ============================================================
   NAV MAP setup
   ============================================================ */
let routeLen=0, routeEl=null;
function buildMap(){
  // route dash reveal
  routeEl=$('#route-done');
  routeLen=routeEl.getTotalLength();
  routeEl.style.strokeDasharray=routeLen;
  routeEl.style.strokeDashoffset=routeLen;
  // pois
  $$('.poi').forEach(p=>{
    p.setAttribute('transform', `translate(${p.dataset.x},${p.dataset.y})`);
  });
  setMapProgress(0.05);
}
function setMapProgress(t){
  t=clamp(t,0,1);
  routeEl.style.strokeDashoffset = routeLen*(1-t);
  const pt = routeEl.getPointAtLength(routeLen*t);
  $('#map-car').setAttribute('transform', `translate(${pt.x.toFixed(1)},${pt.y.toFixed(1)})`);
}

/* ============================================================
   ECG + NET spark (rAF)
   ============================================================ */
let hrBpm=72, ecgPhase=0, netQuality=1, netSamples=[];
function ecgY(p){ // p in 0..1 within a beat -> y in -1..1
  if(p<0.12) return 0;
  if(p<0.18) return 0.18*Math.sin((p-0.12)/0.06*Math.PI);      // P
  if(p<0.40) return 0;
  if(p<0.44) return -0.22*((p-0.40)/0.04);                      // Q
  if(p<0.48) return lerp(-0.22, 1.0, (p-0.44)/0.04);            // R up
  if(p<0.52) return lerp(1.0, -0.35, (p-0.48)/0.04);            // S down
  if(p<0.56) return lerp(-0.35, 0, (p-0.52)/0.04);
  if(p<0.72) return 0;
  if(p<0.86) return 0.30*Math.sin((p-0.72)/0.14*Math.PI);       // T
  return 0;
}
function renderECG(){
  const beats = clamp(hrBpm/34, 1.4, 6);
  let pts='';
  for(let i=0;i<=120;i++){
    const xN=i/120, x=xN*200;
    const p=((xN*beats + ecgPhase)%1+1)%1;
    const y=28 - ecgY(p)*20;
    pts += `${x.toFixed(1)},${y.toFixed(1)} `;
  }
  $('#ecg-line').setAttribute('points', pts.trim());
}
function renderNetSpark(){
  // push slight jitter sample
  const last = netSamples.length? netSamples[netSamples.length-1] : netQuality;
  const target = netQuality + (Math.random()-0.5)*0.06;
  netSamples.push(clamp(lerp(last,target,0.5),0,1));
  if(netSamples.length>42) netSamples.shift();
  const n=netSamples.length;
  const span=Math.max(n-1,1);
  const pts=netSamples.map((q,i)=>`${(i/span*160).toFixed(1)},${(36-q*30).toFixed(1)}`).join(' ');
  $('#net-line').setAttribute('points', pts);
}

/* ---------- tween + animation loop ---------- */
const target={speed:0, steer:0};
const disp={speed:0, steer:0};
let lastT=performance.now(), netAccum=0;
function frame(now){
  const dt=Math.min(0.05,(now-lastT)/1000); lastT=now;
  disp.speed = lerp(disp.speed, target.speed, 1-Math.pow(0.001,dt));
  disp.steer = lerp(disp.steer, target.steer, 1-Math.pow(0.0005,dt));
  renderSpeed(disp.speed);
  $('#car-body').style.transform = `rotate(${(disp.steer*0.32).toFixed(2)}deg)`;
  const wr=`rotate(${(disp.steer*0.8).toFixed(2)}deg)`;
  $('#wfl').style.transform=wr; $('#wfr').style.transform=wr;
  $('#val-steer').textContent = `${Math.round(disp.steer)}°`;
  // ecg
  ecgPhase = (ecgPhase + dt*(hrBpm/60)) % 1;
  renderECG();
  // net spark ~every 380ms
  netAccum+=dt; if(netAccum>0.38){ netAccum=0; renderNetSpark(); }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

/* ============================================================
   ROUTING flow
   ============================================================ */
function firePkt(id){
  const p=$(id); if(!p) return;
  p.classList.remove('fire'); void p.offsetWidth; p.classList.add('fire');
}
function fmtLat(ms){ return ms<1000 ? `${Math.round(ms)} ms` : `${(ms/1000).toFixed(1)} s`; }

async function doRoute(step){
  setPhase('thinking'); setOrbStatus('ROUTING');
  $('#router-intent').textContent = step.intent;
  $('#rt-router').classList.add('active');
  firePkt('#pkt-in');
  await delay(260);
  const edge=$('#branch-edge'), cloud=$('#branch-cloud');
  edge.classList.remove('active','dim'); cloud.classList.remove('active','dim');
  const chosen = step.to==='edge' ? edge : cloud;
  const other = step.to==='edge' ? cloud : edge;
  chosen.classList.add('active'); other.classList.add('dim');
  firePkt(step.to==='edge' ? '#pkt-edge' : '#pkt-cloud');
  // readout
  $('#rt-route').querySelector('.rtc-v').textContent = step.to.toUpperCase();
  $('#rt-route').querySelector('.rtc-v').style.color = step.to==='edge' ? 'var(--mint)' : 'var(--cloud)';
  $('#rt-lat').querySelector('.rtc-v').textContent = fmtLat(step.lat);
  $('#rt-crit').querySelector('.rtc-v').textContent = step.cls || '—';
  $('#rt-fallback').classList.toggle('show', !!step.fallback);
  // safety sub-50ms accent
  $('#rt-lat').querySelector('.rtc-v').style.color = (step.crit==='safety' && step.lat<50) ? 'var(--mint)' : '';
  // stats
  stats.total++; stats.sumLat+=step.lat;
  if(step.to==='edge') stats.edge++; else stats.cloud++;
  renderStats();
  await delay(520);
  $('#rt-router').classList.remove('active');
}

const stats={total:0, edge:0, cloud:0, sumLat:0};
function renderStats(){
  $('#stat-total').textContent=stats.total;
  $('#stat-edge').textContent=stats.edge;
  $('#stat-cloud').textContent=stats.cloud;
  const avg = stats.total? stats.sumLat/stats.total : 0;
  $('#stat-lat').innerHTML = `${Math.round(avg)}<small>ms</small>`;
  $('#stat-success').innerHTML = `100<small>%</small>`;
}

/* ============================================================
   ORB / phases / typing
   ============================================================ */
const cockpit=$('#cockpit');
function setPhase(p){ cockpit.dataset.phase=p; }
function setOrbStatus(t){ $('#orb-status').textContent=t; }
function setMood(m){ cockpit.dataset.mood=m; }

let typeSkip=false;
async function type(el, text, cps){
  typeSkip=false; el.textContent='';
  const cur=document.createElement('span'); cur.className='cursor'; el.appendChild(cur);
  for(let i=0;i<text.length;i++){
    if(typeSkip){ el.textContent=text; return; }
    cur.insertAdjacentText('beforebegin', text[i]);
    await delay(1000/cps);
  }
  cur.remove();
}

/* ============================================================
   NETWORK conditions
   ============================================================ */
const NET = {
  excellent:{lat:48, loss:0, q:4, label:'Excellent', state:'ONLINE', conn:true},
  good:     {lat:120, loss:1, q:3, label:'Good', state:'ONLINE', conn:true},
  degraded: {lat:480, loss:5, q:2, label:'Degraded', state:'WEAK', conn:true},
  offline:  {lat:9999, loss:100, q:0, label:'No Signal', state:'OFFLINE', conn:false},
};
function setNet(cond){
  const n=NET[cond]||NET.excellent;
  netQuality = n.q/4;
  $('#signal').className = 'signal q'+n.q;
  $('#conn-state').textContent = n.state;
  $('#conn-lat').textContent = n.conn ? n.lat+' ms' : '—';
  $('#conn-pill').classList.toggle('off', !n.conn);
  $('#net-cond').textContent = n.label;
  $('#net-loss').textContent = n.loss.toFixed ? n.loss.toFixed(1)+'% loss' : n.loss+'% loss';
  $('#cloud-health').textContent = n.conn ? (liveBackend?'LIVE':'LINKED') : 'OFFLINE';
}

/* ============================================================
   VSS ticker
   ============================================================ */
const vssTicker=$('#vss-ticker');
const MAX_VSS=5;
function pushVSS(step){
  $('.vss-dot').classList.add('live');
  const line=document.createElement('div');
  line.className='vss-line';
  const icon = step.op==='write' ? '✎' : '↧';
  const shortPath = step.path.replace(/^Vehicle\./,'');
  line.innerHTML =
    `<span class="vss-op${step.op==='read'?' read':''}">${icon}</span>`+
    `<span class="vss-path">${shortPath}</span>`+
    `<span class="vss-eq">=</span><span class="vss-val">${step.value}</span>`+
    `<span class="vss-lat">${step.lat.toFixed(1)}ms ${step.ok?'<span class=vss-ok>✓</span>':'⚠'}</span>`;
  vssTicker.prepend(line);
  while(vssTicker.children.length>MAX_VSS) vssTicker.lastChild.remove();
}
function seedVSS(){
  pushVSS({op:'read',path:'Vehicle.CurrentLocation.Latitude',value:'48.1351',lat:9.1,ok:true});
  pushVSS({op:'read',path:'Vehicle.Powertrain.FuelSystem.Level',value:'15%',lat:7.6,ok:true});
  pushVSS({op:'read',path:'Vehicle.Speed',value:'0',lat:7.9,ok:true});
}

/* ============================================================
   VEHICLE state apply
   ============================================================ */
function setVehicle(s){
  if(s.speed!==undefined) target.speed=s.speed;
  if(s.steering!==undefined) target.steer=s.steering;
  if(s.temperature!==undefined){ $('#val-temp').textContent=Math.round(s.temperature)+'°'; $('#chip-climate').classList.add('active'); }
  if(s.headlights!==undefined){
    $('#val-lights').textContent=s.headlights?'ON':'OFF';
    $('#chip-lights').classList.toggle('active', s.headlights);
    $('#hl-l').classList.toggle('on', s.headlights); $('#hl-r').classList.toggle('on', s.headlights);
    $('#beams').classList.toggle('on', s.headlights);
  }
  if(s.doors!==undefined){
    $('#val-doors').textContent=s.doors?'UNLK':'LOCK';
    $('#door-l').classList.toggle('unlocked', s.doors); $('#door-r').classList.toggle('unlocked', s.doors);
  }
  if(s.hazard!==undefined){
    ['#hz-fl','#hz-fr','#hz-rl','#hz-rr'].forEach(id=>$(id).classList.toggle('on', s.hazard));
  }
  if(s.brake!==undefined){
    $('#bl-l').classList.toggle('on', s.brake); $('#bl-r').classList.toggle('on', s.brake);
  }
}
function brakeSnap(){
  target.speed=0; disp.speed=0; renderSpeed(0);
  setVehicle({brake:true, hazard:true});
  cockpit.animate(
    [{filter:'brightness(1.6) saturate(1.2)'},{filter:'brightness(1)'}],
    {duration:420, easing:'ease-out'}
  );
}

/* ============================================================
   HR / fuel / alert / nav
   ============================================================ */
function setHR(step){
  hrBpm=step.bpm;
  $('#hr-bpm').textContent=step.bpm;
  $('#hr-state').textContent=step.state;
  $('#tele-hr').classList.toggle('alert', !!step.alert);
}
function setFuel(step){
  $('#fuel-pct').textContent=step.pct+'%';
  const f=$('#fuel-fill'); f.style.width=step.pct+'%'; f.classList.toggle('low', !!step.low);
  $('#fuel-range').textContent=step.range;
}
function setAlert(step){
  const b=$('#alert-banner');
  if(step.on){ $('#ab-title').textContent=step.title; $('#ab-sub').textContent=step.sub; b.classList.add('show'); }
  else b.classList.remove('show');
}
function setNav(step){
  if(step.dest!==undefined) $('#nav-dest').textContent=step.dest;
  if(step.eta!==undefined) $('#nav-eta-min').textContent=step.eta;
  if(step.dist!==undefined) $('#nav-dist').textContent=step.dist;
  if(step.next!==undefined) $('#nav-next').textContent=step.next;
  if(step.prog!==undefined) setMapProgress(step.prog);
}
function litPOI(id){ const m={food:'#poi-food',gas:'#poi-gas',hosp:'#poi-hosp'}; $(m[id])?.classList.add('lit'); }
function setTunnel(on){ $('#tunnel-banner').classList.toggle('show', on); }

/* ============================================================
   SCENE
   ============================================================ */
function setScene(n, name){
  $('#scene-idx').textContent=pad2(n);
  $('#scene-name').textContent=name;
  $('#scene-tag').classList.add('show');
}

/* ============================================================
   STEP dispatcher
   ============================================================ */
async function apply(step){
  switch(step.t){
    case 'scene': setScene(step.n, step.name); break;
    case 'net': setNet(step.cond); break;
    case 'mood': setMood(step.m); break;
    case 'vehicle': setVehicle(step.set); break;
    case 'driver':
      setPhase('listening'); setOrbStatus('LISTENING');
      await type($('#driver-text'), step.text, 40);
      break;
    case 'route': await doRoute(step); break;
    case 'assistant':
      setPhase('speaking'); setOrbStatus('SPEAKING');
      await type($('#assistant-text'), step.text, 36);
      setPhase('idle'); setOrbStatus('READY');
      break;
    case 'vss': pushVSS(step); break;
    case 'poi': litPOI(step.id); break;
    case 'map': setNav(step); break;
    case 'tunnel': setTunnel(step.on); break;
    case 'hr': setHR(step); break;
    case 'fuel': setFuel(step); break;
    case 'alert': setAlert(step); break;
    case 'brake': brakeSnap(); break;
    case 'chip': { const c=$('#'+step.id); c.classList.add('flash'); setTimeout(()=>c.classList.remove('flash'),900); break; }
    case 'phase': setPhase(step.p); break;
    case 'orbstatus': setOrbStatus(step.text); break;
    case 'summary': finish(); break;
    case 'wait': break;
  }
}

/* ============================================================
   RUNNER (play / pause / skip / reset)
   ============================================================ */
const SCEN = window.SPEECHLESS_SCENARIO;
const DWELL_SCALE = 1.8;   // pacing — stretches read/narration pauses (target 2.5 min)
let idx=0, running=false, paused=false;
let skipResolve=null, resumeResolve=null, sleepTimer=null;

function sleep(ms){
  return new Promise(res=>{
    skipResolve=()=>{ clearTimeout(sleepTimer); skipResolve=null; res(); };
    sleepTimer=setTimeout(()=>{ skipResolve=null; res(); }, ms);
  });
}
function gate(){ return paused ? new Promise(r=>resumeResolve=r) : Promise.resolve(); }

async function loop(){
  running=true;
  for(; idx<SCEN.length; idx++){
    await gate(); if(!running) return;
    await apply(SCEN[idx]);
    if(!running) return;
    await gate(); if(!running) return;
    await sleep((SCEN[idx].d || 0) * DWELL_SCALE);
  }
  running=false;
}

function hideOverlay(){
  const ov=$('#start-overlay');
  ov.getAnimations().forEach(x=>x.cancel());
  ov.style.transition='opacity .4s ease';
  ov.style.opacity='0'; ov.style.pointerEvents='none';
  setTimeout(()=>{ ov.style.display='none'; }, 400);
}
function showOverlay(){
  const ov=$('#start-overlay');
  ov.getAnimations().forEach(x=>x.cancel());
  ov.style.display=''; ov.style.opacity=''; ov.style.visibility=''; ov.style.pointerEvents='';
}

function start(){
  hideOverlay();
  $('#scene-tag').classList.add('show');
  if(running) return;
  if(idx===0){ setOrbStatus('STANDBY'); }
  if(liveBackend) fetch('/api/start-demo').catch(()=>{});
  loop();
}
function togglePause(){
  if(!running && idx===0){ start(); return; }
  if(idx>=SCEN.length){ reset(); return; }
  paused=!paused;
  setOrbStatus(paused?'PAUSED':'READY');
  if(!paused && resumeResolve){ resumeResolve(); resumeResolve=null; }
}
function next(){
  typeSkip=true;
  if(paused){ paused=false; if(resumeResolve){ resumeResolve(); resumeResolve=null; } }
  if(skipResolve) skipResolve();
}
function finish(){
  setOrbStatus('DEMO COMPLETE · PRESS R TO REPLAY');
  setScene(15,'Demo Complete · Press R to replay');
}

function reset(){
  running=false; paused=false; idx=0;
  if(skipResolve){ skipResolve(); } if(resumeResolve){ resumeResolve(); resumeResolve=null; }
  clearTimeout(sleepTimer);
  // state
  Object.assign(stats,{total:0,edge:0,cloud:0,sumLat:0}); renderStats();
  target.speed=0; target.steer=0; disp.speed=0; disp.steer=0;
  setMood('normal'); setPhase('idle');
  setNet('excellent'); setTunnel(false); setAlert({on:false});
  setHR({bpm:72,state:'Normal',alert:false});
  setFuel({pct:15,range:'~88 km',low:false});
  setVehicle({temperature:22, headlights:false, doors:false, hazard:false, brake:false});
  $('#val-temp').textContent='22°'; $('#chip-climate').classList.remove('active');
  $('#driver-text').textContent='—';
  $('#assistant-text').textContent="Tap Start, or press Space — I'm listening.";
  $('#router-intent').textContent='intent';
  ['#rt-route','#rt-lat','#rt-crit'].forEach(s=>$(s).querySelector('.rtc-v').textContent='—');
  $('#rt-fallback').classList.remove('show');
  $('#branch-edge').classList.remove('active','dim'); $('#branch-cloud').classList.remove('active','dim');
  $$('.poi').forEach(p=>p.classList.remove('lit'));
  vssTicker.innerHTML=''; $('.vss-dot').classList.remove('live'); seedVSS();
  setNav({dest:'Pasta Perfetto', eta:18, dist:14.2, next:'via A9', prog:0.05});
  setOrbStatus('STANDBY');
  $('#scene-idx').textContent='00'; $('#scene-name').textContent='Standby';
  showOverlay();
}

/* ---------- controls ---------- */
$('#start-btn').addEventListener('click', start);
addEventListener('keydown', e=>{
  if(e.code==='Space'){ e.preventDefault(); togglePause(); }
  else if(e.code==='ArrowRight'){ e.preventDefault(); next(); }
  else if(e.key==='r' || e.key==='R'){ e.preventDefault(); reset(); }
});

/* ============================================================
   LIVE BACKEND detection (optional — visuals stay scripted)
   ============================================================ */
let liveBackend=false;
async function detectBackend(){
  try{
    const r=await fetch('/api/state',{cache:'no-store'});
    if(r.ok){ liveBackend=true; $('#edge-health').textContent='LIVE'; $('#cloud-health').textContent='LIVE'; }
  }catch(_){ /* standalone — scripted demo only */ }
}

/* ---------- init ---------- */
buildSpeedo();
buildMap();
renderStats();
seedVSS();
detectBackend();
})();
