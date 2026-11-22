// One set of filters drives the trend, composition, totals and model table.
import {$, el} from './ui.js';

const format = n => n.toLocaleString('zh-CN');
const compact = new Intl.NumberFormat('en', {notation:'compact', maximumFractionDigits:1});
const fields = ['calls','inputs','outputs','measured','cached','cache_inputs','cache_samples','elapsed','timed'];
function sum(rows) {
  return Object.fromEntries(fields.map(key => [key, rows.reduce((total,row) => total + row[key], 0)]));
}
const latency = r => r.timed ? (r.elapsed / r.timed / 1000).toFixed(1) + ' s' : '—';
let last = '';
export function renderUsage(series) {
  const period = $('usage-period'), model = $('usage-model');
  const now = Math.floor(Date.now() / 3600000);
  const signature = JSON.stringify([series, period.value, model.value, now]);
  if (signature === last) return;
  last = signature;
  const models = [...new Set(series.map(row => row.model))].sort();
  const selected = model.value;
  model.replaceChildren(new Option('全部模型',''), ...models.map(name => new Option(name,name)));
  model.value = models.includes(selected) ? selected : '';
  period.onchange = model.onchange = () => renderUsage(series);
  const available = series.filter(row => !model.value || row.model === model.value);
  const from = period.value === 'all' ? available.reduce((v,r)=>r.hour ? Math.min(v,r.hour) : v, now) : now - Number(period.value) + 1;
  const rows = available.filter(row => period.value === 'all' || (row.hour >= from && row.hour <= now));
  showCallers('caller-rows', rows);
  showCallers('agent-callers', series);
  const totals = sum(rows), total = totals.inputs + totals.outputs;
  const metrics = [
    ['Agent 调用',format(totals.calls),'已保存的调用记录'],
    ['总 Token',totals.measured ? compact.format(total) : '—',format(totals.measured)+' 次上报用量'],
    ['缓存输入占比',totals.cache_inputs ? (100*totals.cached/totals.cache_inputs).toFixed(1)+'%' : '—',totals.cache_samples+' 次上报缓存'],
    ['平均步骤耗时',latency(totals),totals.timed+' 次有计时']
  ];
  $('usage-kpis').replaceChildren(...metrics.map(([label,value,hint]) => {
    const cell=el('div'); cell.append(el('dt',label),el('dd',value),el('small',hint)); return cell;
  }));
  const width = Math.max(1, Math.ceil((now-from+1)/30));
  const bins = Array.from({length:Math.ceil((now-from+1)/width)},()=>({inputs:0,outputs:0}));
  for (const row of rows) {
    const bin=bins[Math.floor((row.hour-from)/width)];
    if (bin) {bin.inputs+=row.inputs; bin.outputs+=row.outputs;}
  }
  const peak=Math.max(1,...bins.map(b=>b.inputs+b.outputs));
  const stamp = h => new Date(h*3600000).toLocaleString('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',hour12:false});
  $('trend-unit').textContent = width+' 小时 / 柱';
  $('trend-axis').replaceChildren(...[peak,peak/2,0].map(n=>el('small',compact.format(n))));
  $('token-trend').replaceChildren(...bins.map((bin,i)=>{
    const col=el('div',undefined,'trend-col');
    col.title=stamp(from+i*width)+' 至 '+stamp(Math.min(now,from+(i+1)*width-1))+' · 输入 '+format(bin.inputs)+' · 输出 '+format(bin.outputs);
    for(const key of ['inputs','outputs']) {
      const bar=el('i',undefined,key); bar.style.height=100*bin[key]/peak+'%'; col.append(bar);
    }
    return col;
  }));
  $('trend-labels').replaceChildren(...[from,now].map(h=>el('small',stamp(h))));
  const parts=[['未缓存输入',totals.cache_inputs-totals.cached,'--blue'],['缓存读取',totals.cached,'--mint'],
    ['输出',totals.outputs,'--amber'],['缓存状态未知的输入',totals.inputs-totals.cache_inputs,'--soft']];
  const stops=[]; let offset=0;
  $('ring-key').replaceChildren(...parts.filter(([,n],i)=>i<3 || n).map(([label,n,color])=>{
    const line=el('div'), dot=el('i'); dot.style.background='var('+color+')';
    line.append(dot,el('dt',label),el('dd',totals.measured ? format(n) : '—'));
    if(total && n) {const end=offset+100*n/total; stops.push('var('+color+') '+offset+'% '+end+'%'); offset=end;}
    return line;
  }));
  $('usage-ring').style.background=stops.length ? 'conic-gradient('+stops.join(',')+')' : 'var(--line)';
  $('ring-value').textContent=totals.measured ? compact.format(total) : '—';
  const byModel= [...new Set(rows.map(r=>r.model))].map(name=>[name,sum(rows.filter(r=>r.model===name))])
    .sort((a,b)=>(b[1].inputs+b[1].outputs)-(a[1].inputs+a[1].outputs));
  const tableRows=byModel.map(([name,m])=>{
    const tr=el('tr'); tr.append(...[name,format(m.calls),m.measured?format(m.inputs):'—',m.measured?format(m.outputs):'—',latency(m)].map(v=>el('td',v)));
    return tr;
  });
  if(!tableRows.length) { const tr=el('tr'), td=el('td','所选时段暂无调用记录。'); td.colSpan=5; tr.append(td); tableRows.push(tr); }
  $('model-rows').replaceChildren(...tableRows);
}

function showCallers(id, rows) {
  const groups = new Map();
  for (const row of rows) {
    if (!groups.has(row.caller)) groups.set(row.caller, []);
    groups.get(row.caller).push(row);
  }
  const callers = [...groups].map(([name, group]) => [name, sum(group)])
    .sort((a,b) => b[1].calls - a[1].calls || a[0].localeCompare(b[0]));
  const total = sum(rows).calls;
  const body = callers.map(([name,m]) => {
    const tr = el('tr');
    for (const text of [name, format(m.calls), (100*m.calls/total).toFixed(1)+'%',
      m.measured ? format(m.inputs+m.outputs) : '—', latency(m)]) tr.append(el('td',text));
    return tr;
  });
  if (!body.length) {
    const tr = el('tr'), td = el('td','暂无已保存的调用。');
    td.colSpan = 5; tr.append(td); body.push(tr);
  }
  $(id).replaceChildren(...body);
}
