// Calendar dates arrive in the service host's time zone. Use UTC only for civil-date arithmetic.
import {$, el} from './ui.js';
const weekdays = ['周一','周二','周三','周四','周五','周六','周日'];
let previous;
function place(grid, node, x, y) {
  node.style.gridColumn = x;
  node.style.gridRow = y;
  grid.append(node);
}
function tile(count, label) {
  const node = el('span', undefined, 'heat-cell');
  node.dataset.level = [1,5,15,30].filter(n => count >= n).length;
  node.title = label + ' · ' + count + ' 次执行';
  node.setAttribute('aria-label', node.title);
  node.setAttribute('role','img');
  return node;
}
function finish(id, content) {
  const root = $(id);
  root.replaceChildren(content);
  if (root.parentElement.nextElementSibling?.className === 'heat-key') return;
  const key = el('div', undefined, 'heat-key');
  for (const [count,label] of [[0,'0'],[1,'1–4'],[5,'5–14'],[15,'15–29'],[30,'30+ 次']]) {
    key.append(tile(count,'色阶'),el('small',label));
  }
  root.parentElement.after(key);
}
export function renderActivity({days,hours}) {
  const signature = JSON.stringify([days,hours]);
  if (previous === signature) return;
  previous = signature;
  const year = document.createDocumentFragment(), clock = document.createDocumentFragment();
  const offset = (new Date(days[0].day+'T00:00:00Z').getUTCDay()+6)%7;
  for (let i=0;i<7;i++) {
    if ([0,2,4,6].includes(i)) place(year,el('small',weekdays[i]),1,i+2);
    place(clock,el('small',weekdays[i]),1,i+2);
  }
  days.forEach(({day,count},i) => {
    const week=Math.floor((i+offset)/7)+2;
    if (day.endsWith('-01')) place(year,el('small',Number(day.slice(5,7))+'月'),week,1);
    place(year,tile(count,day),week,(i+offset)%7+2);
  });
  for (let h=0;h<24;h++) {
    const hour=String(h).padStart(2,'0');
    place(clock,el('small',hour),h+2,1);
    hours.forEach((row,d)=>place(clock,tile(row[h],weekdays[d]+' '+hour+':00–'+hour+':59'),h+2,d+2));
  }
  finish('year-map',year); finish('hour-map',clock);
  const total=days.reduce((n,d)=>n+d.count,0);
  $('year-caption').textContent=days[0].day+' 至 '+days.at(-1).day+' · '+total+' 次顶层任务执行 · '+days.filter(d=>d.count).length+' 个活跃日';
  $('hour-caption').textContent=days.at(-30).day+' 至 '+days.at(-1).day+' · 按服务本机时间累计顶层任务执行次数';
}
