import {renderActivity} from './heatmaps.js';
import {renderUsage} from './usage.js';
// Real execution and scheduling summaries for the operations landing page.
import {
  $,
  el,
  button,
  date,
  duration,
  badge,
  api
} from './ui.js';
import {
  openDetail
} from './executions.js';

async function refreshDashboard() {
  const data = await api('/panel/overview');
  const counts = data.recent.counts;
  const states = data.states;
  $('count-all').textContent = Object.values(counts).reduce((a, b) => a + b, 0);
  $('count-running').textContent = states.PENDING || 0;
  $('home-completed').textContent = '已完成 ' + (counts.SUCCESS || 0) + ' 次 · 查看记录 →';
  $('count-error').textContent = (states.ERROR || 0) + (states.MAX_RECOVERY_ATTEMPTS_EXCEEDED || 0);
  $('nav-error-count').textContent = $('count-error').textContent;
  $('nav-error-count').hidden = Number($('count-error').textContent) === 0;
  if (!$('view-statistics').hidden) renderActivity(data.activity);
  const usage = data.usage;
  $('review-count').textContent = usage.reviewed;
  $('artifact-count').textContent = usage.artifacts;
  $('home-calls').textContent = usage.calls.toLocaleString('zh-CN');
  const tokens = usage.input + usage.output;
  $('home-tokens').textContent = usage.measured ? new Intl.NumberFormat('en', {notation:'compact', maximumFractionDigits:2}).format(tokens) : '—';
  $('home-tokens').title = usage.measured ? tokens.toLocaleString('zh-CN') + ' Token' : '暂无完整用量记录';
  if (!$('view-statistics').hidden || !$('view-agents').hidden) renderUsage(usage.series);
  const rows = data.recent.items.slice(0, 4).map(run => {
    const row = el('div', undefined, 'activity-row');
    row.append(el('div', run.status === 'SUCCESS' ? '✓' : run.status === 'ERROR' ? '!' : '·', 'activity-symbol'));
    const copy = el('div', undefined, 'activity-copy');
    copy.append(button(run.title, () => openDetail(run.id), 'link-button'));
    if (run.trigger) copy.append(el('span', run.trigger + '触发', 'trigger-tag'));
    copy.append(el('small', `${date(run.created_at)} · ${duration(run.duration_ms)}`));
    row.append(copy, badge(run.status));
    return row;
  });
  $('recent-runs').replaceChildren(...(rows.length ? rows : [el('p', '过去 24 小时还没有执行记录。可提交一个任务，或安排定时计划。', 'empty')]));
  const queues = new Map();
  for (const item of data.queues) {
    if (!queues.has(item.queue_name)) queues.set(item.queue_name, []);
    queues.get(item.queue_name).push(`${item.status} ${item.count}`);
  }
  $('queues').replaceChildren(...([...queues].length ? [...queues].map(([name, counts]) => {
    const node = el('div', name, 'queue-chip');
    node.append(el('small', counts.join(' · ')));
    return node;
  }) : [el('p', '暂无队列记录。', 'hint')]));
}

export {
  refreshDashboard
};
