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
  $('count-success').textContent = counts.SUCCESS || 0;
  $('count-error').textContent = (states.ERROR || 0) + (states.MAX_RECOVERY_ATTEMPTS_EXCEEDED || 0);
  $('nav-error-count').textContent = $('count-error').textContent;
  $('nav-error-count').hidden = Number($('count-error').textContent) === 0;
  const rows = data.recent.items.map(run => {
    const row = el('div', undefined, 'activity-row');
    row.append(el('div', run.status === 'SUCCESS' ? '✓' : run.status === 'ERROR' ? '!' : '·', 'activity-symbol'));
    const copy = el('div', undefined, 'activity-copy');
    copy.append(button(run.title, () => openDetail(run.id), 'link-button'), el('small', `${date(run.created_at)} · ${duration(run.duration_ms)}`));
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
