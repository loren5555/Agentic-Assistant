// Daily-job configuration and dispatch. Recurrence edits never execute a job.
import {
  $,
  state,
  el,
  button,
  notice,
  date,
  api,
  confirmDialog,
  requestRefresh
} from './ui.js';
import { recordList, showRecord, fields } from './records.js';
let listVersion;
let data = {
  items: [],
  revision: null,
  editable: false
};
let editorRevision = null;
let previewSequence = 0;
let dispatch = null;

const pickerFields = {
  weekdays: {start: 0, end: 6, label: n => '周' + '日一二三四五六'[n]},
  monthdays: {start: 1, end: 31, label: n => n + '日'},
  hours: {start: 0, end: 23, label: n => n + '时'},
  minutes: {start: 0, end: 59, label: n => String(n).padStart(2, '0')}
};

function fillPicker(name, selected) {
  const {start, end, label} = pickerFields[name];
  const choices = [];
  for (let index = start; index <= end; index++) {
    const n = name === 'weekdays' ? (index + 1) % 7 : index;
    const choice = el('label');
    const input = el('input');
    input.type = 'checkbox';
    input.value = n;
    input.checked = selected.includes(n);
    choice.append(input, el('span', label(n)));
    choices.push(choice);
  }
  $('schedule-' + name).querySelector('.schedule-choices').replaceChildren(...choices);
}

function selectedField(name) {
  const group = $('schedule-' + name);
  const numbers = [...group.querySelectorAll(':checked')].map(input => Number(input.value)).sort((a,b) => a-b);
  if (!numbers.length) throw new Error('请选择' + group.querySelector('legend').textContent + '。');
  const parts = [];
  for (let i = 0; i < numbers.length; i++) {
    const first = numbers[i];
    while (numbers[i+1] === numbers[i]+1) i++;
    const last = numbers[i];
    parts.push(last === first ? first : first + '-' + last);
  }
  return parts.join(',');
}

function specFromForm() {
  const frequency = $('schedule-frequency').value;
  let cron = $('schedule-cron').value.trim();
  if (frequency !== 'custom') {
    const clock = $('schedule-clock').value;
    let hour, minute;
    if (clock === 'once') {
      if (!$('schedule-time').value) throw new Error('请选择执行时间。');
      [hour, minute] = $('schedule-time').value.split(':').map(Number);
    } else {
      hour = clock === 'hourly' ? '*' : selectedField('hours');
      minute = selectedField('minutes');
    }
    const day = frequency === 'monthly' ? selectedField('monthdays') : '*';
    const weekday = frequency === 'weekly' ? selectedField('weekdays') : '*';
    cron = `0 ${minute} ${hour} ${day} * ${weekday}`;
  }
  return {cron, timezone: $('schedule-timezone').value, enabled: $('schedule-enabled').checked};
}

function frequencyFields() {
  const mode = $('schedule-frequency').value;
  const visual = mode !== 'custom';
  const clock = $('schedule-clock').value;
  $('schedule-clock-label').hidden = !visual;
  $('schedule-time-label').hidden = !visual || clock !== 'once';
  $('schedule-time').disabled = $('schedule-time-label').hidden;
  $('schedule-weekdays').hidden = mode !== 'weekly';
  $('schedule-monthdays').hidden = mode !== 'monthly';
  $('schedule-hours').hidden = !visual || clock !== 'multiple';
  $('schedule-minutes').hidden = !visual || clock === 'once';
  $('schedule-cron-label').hidden = visual;
  $('schedule-cron').required = !visual;
}

async function preview() {
  const sequence = ++previewSequence;
  $('schedule-preview').textContent = '计算执行时间…';
  $('schedule-expression').textContent = '';
  try {
    const spec = specFromForm();
    $('schedule-expression').textContent = `${describe(spec)} · ${spec.timezone}`;
    const result = await api('/panel/schedules/preview', {
      method: 'POST',
      body: JSON.stringify(spec)
    });
    if (sequence !== previewSequence) return;
    $('schedule-preview').replaceChildren(...result.next_runs.map(value => el('div', new Date(value).toLocaleString('zh-CN', {
      timeZone: spec.timezone,
      hour12: false
    }), 'preview-time')));
  } catch (error) {
    if (sequence === previewSequence) $('schedule-preview').textContent = error.message;
  }
}

// Keep inclusive ranges compact even for schedules that cover many hours.
function cronList(field, format) {
  return field.split(',').map(part => part.split('-').map(format).join('至')).join('、');
}

const numericList = /^\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*$/;
const integer = /^\d+$/;
const pad = value => value.padStart(2, '0');

function describe({cron}) {
  const [second, minute, hour, day, month, weekday] = cron.trim().split(/\s+/);
  const fallback = `Cron · ${cron}`;
  if (second !== '0' || month !== '*') return fallback;

  let period = '每天';
  if (day === '*' && numericList.test(weekday)) {
    period = '每' + cronList(weekday, n => '周' + '日一二三四五六'[Number(n) % 7]);
  } else if (weekday === '*' && numericList.test(day)) {
    period = '每月' + cronList(day, n => Number(n) + '日');
  } else if (day !== '*' || weekday !== '*') {
    return fallback;
  }

  if (hour === '*') {
    const prefix = period === '每天' ? '' : period + '，';
    if (minute === '*') return prefix + '每分钟';
    const interval = /^\*\/(\d+)$/.exec(minute);
    if (interval && 60 % Number(interval[1]) === 0) return `${prefix}每 ${Number(interval[1])} 分钟`;
    if (numericList.test(minute)) return prefix + '每小时的' + cronList(minute, n => Number(n) + '分');
  } else if (numericList.test(hour) && numericList.test(minute)) {
    if (!hour.includes('-') && integer.test(minute)) {
      return period + ' ' + cronList(hour, n => pad(n) + ':' + pad(minute));
    }
    return period + ' ' + cronList(hour, n => Number(n) + '点') + '，各小时的' + cronList(minute, n => Number(n) + '分');
  }
  return fallback;
}

// Only load fields the picker can represent exactly. Other rules stay in advanced mode.
function expandField(field, {start, end}) {
  const numbers = new Set();
  for (const part of field.split(',')) {
    const match = /^(\*|\d+(?:-\d+)?)(?:\/(\d+))?$/.exec(part);
    if (!match) return null;
    const [a, b] = match[1].split('-').map(Number);
    const first = match[1] === '*' ? start : a;
    const last = match[1] === '*' || (match[2] && b === undefined) ? end : b ?? a;
    const stride = Number(match[2] || 1);
    if (stride < 1 || first < start || last > end || first > last) return null;
    for (let n = first; n <= last; n += stride) numbers.add(n);
  }
  return [...numbers];
}

function loadRule(cron) {
  const [second, minute, hour, day, month, weekday] = cron.trim().split(/\s+/);
  const hours = expandField(hour, pickerFields.hours);
  const minutes = expandField(minute, pickerFields.minutes);
  const weekdays = expandField(weekday, pickerFields.weekdays);
  const monthdays = expandField(day, pickerFields.monthdays);
  const visual = second === '0' && month === '*' && (weekday === '*' || day === '*')
    && hours && minutes && weekdays && monthdays;
  $('schedule-cron').value = cron;
  $('schedule-frequency').value = !visual ? 'custom' : weekday !== '*' ? 'weekly' : day !== '*' ? 'monthly' : 'daily';
  $('schedule-clock').value = !visual ? 'once' : hour === '*' ? 'hourly' :
    hours.length === 1 && minutes.length === 1 ? 'once' : 'multiple';
  $('schedule-time').value = pad(String(hours?.[0] ?? 7)) + ':' + pad(String(minutes?.[0] ?? 0));
  fillPicker('hours', hour === '*' ? [7] : hours ?? [7]);
  fillPicker('minutes', minutes ?? [0]);
  fillPicker('weekdays', weekday === '*' ? [1] : weekdays ?? [1]);
  fillPicker('monthdays', day === '*' ? [1] : monthdays ?? [1]);
}

function editor(job = null) {
  if (!data.editable) {
    notice('当前服务没有可写配置来源。', true);
    return;
  }
  const existing = data.items.find(item => item.job === job);
  const available = Object.keys(state.jobs).filter(key => !data.items.some(item => item.job === key));
  if (!existing && !available.length) {
    notice('所有可用工作流均已编排，请编辑现有计划。');
    return;
  }
  $('schedule-job').replaceChildren(...Object.entries(state.jobs).filter(([key]) => existing ? key === job : available.includes(key)).map(([key, title]) => new Option(title, key)));
  $('schedule-job').disabled = !!existing;
  if (job && available.includes(job)) $('schedule-job').value = job;
  editorRevision = data.revision;
  $('schedule-editor-title').textContent = existing ? '编辑定时计划' : '新建定时计划';
  loadRule(existing?.cron || '0 0 7 * * *');
  const zone = existing?.timezone || 'Asia/Shanghai';
  if (![...$('schedule-timezone').options].some(option => option.value === zone)) $('schedule-timezone').append(new Option(zone, zone));
  $('schedule-timezone').value = zone;
  $('schedule-enabled').checked = existing?.enabled ?? true;
  $('schedule-error').hidden = true;
  frequencyFields();
  $('schedule-dialog').showModal();
  preview();
}
async function change(job, spec) {
  await api(`/panel/schedules/${encodeURIComponent(job)}`, {
    method: 'PUT',
    body: JSON.stringify({
      ...spec,
      revision: data.revision
    })
  });
  notice(`计划已${spec.enabled?'启用':'暂停'}：${state.jobs[job]}。已保存本地配置并同步 DBOS。`);
  await requestRefresh();
}

function remove(item) {
  confirmDialog('删除定时计划？', '删除后不再产生新的定时任务。已经提交的执行和历史记录会保留。', el('strong', item.title), async () => {
    await api(`/panel/schedules/${encodeURIComponent(item.job)}`, {
      method: 'DELETE',
      body: JSON.stringify({
        revision: data.revision
      })
    });
    notice(`定时计划已删除：${item.title}。`);
  }, '删除计划');
}
async function refreshSchedules() {
  data = await api('/panel/schedules');
  $('nav-schedule-count').textContent = data.items.filter(item => item.enabled).length;
  $('home-schedules').textContent = $('nav-schedule-count').textContent;
  $('schedule-summary').textContent = `${data.items.length} 个定时计划 · ${data.items.filter(item=>item.enabled).length} 个已启用${data.pending_removals?.length?` · ${data.pending_removals.length} 条远端计划待移除`:""}`;
  $('new-schedule').disabled = !data.editable;
  const version = JSON.stringify([data.items, data.editable]);
  if (version !== listVersion) {
    listVersion = version;
    const nextTime = item => item.enabled && item.next_runs.length ? Date.parse(item.next_runs[0]) : Infinity;
    const ordered = [...data.items].sort((a,b) => nextTime(a)-nextTime(b));
    const first = ordered.find(item => Number.isFinite(nextTime(item)));
    $('schedule-next').replaceChildren(el('small','下次执行'), first ? button(first.title, () => showSchedule(first), 'record-link') : el('strong','暂无安排'),
      el('time', first ? date(first.next_runs[0]) : ''));
    const rows = ordered.map(item => ({
      title: item.title,
      values: [describe(item), scheduleBadge(item), date(item.next_runs[0])],
      open: () => showSchedule(item)
    }));
    const content = rows.length
      ? recordList(['工作流', '触发规则', '状态', '下次执行（本机时间）'], rows)
      : el('p', '还没有定时计划。选择下方工作流，安排第一项日常任务。', 'empty-card');
    $('schedule-list').replaceChildren(content);
  }
  const upcoming = data.items.filter(item => item.enabled && item.next_runs.length).sort((a, b) => new Date(a.next_runs[0]) - new Date(b.next_runs[0]));
  $('upcoming-runs').replaceChildren(...(upcoming.length ? upcoming.slice(0, 5).map(item => {
    const row = el('div', undefined, 'activity-row');
    row.append(el('span', new Date(item.next_runs[0]).toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit'
    }), 'schedule-clock'));
    const copy = el('div', undefined, 'activity-copy');
    copy.append(el('strong', item.title), el('small', date(item.next_runs[0])));
    row.append(copy);
    return row;
  }) : [el('p', '还没有启用的定时计划。可在任务编排中添加。', 'empty')]));
}

function scheduleBadge(item) {
  const status = !item.synced ? '待同步' : item.enabled ? '已启用' : '已暂停';
  return el('span', status, 'badge ' + (!item.synced ? 'ERROR' : item.enabled ? 'SUCCESS' : 'CANCELLED'));
}

function showSchedule(item) {
  const content = el('div');
  content.append(scheduleBadge(item), fields([
    ['工作流', item.job], ['触发规则', describe(item)], ['时区', item.timezone], ['Cron', item.cron]
  ]), el('h3', '接下来执行（本机时间）'));
  const times = el('ol', undefined, 'record-times');
  for (const time of item.next_runs) times.append(el('li', date(time)));
  content.append(times.children.length ? times : el('p', '当前没有排定的执行时间。', 'hint'));
  function action(label, callback, style) {
    return button(label, () => {
      $('record-dialog').close();
      callback();
    }, style);
  }
  const actions = [action('运行一次', () => openRun(item.job), 'primary')];
  if (data.editable) {
    actions.push(action('编辑', () => editor(item.job)),
      action(item.enabled ? '暂停' : '启用', async () => {
        try {
          await change(item.job, {cron: item.cron, timezone: item.timezone, enabled: !item.enabled});
        } catch (error) { notice(error.message, true); }
      }), action('删除', () => remove(item), 'danger subtle'));
  }
  showRecord(item.title, '定时计划', content, actions);
}

function openRun(job) {
  dispatch = null;
  $('run-job-select').value = job || Object.keys(state.jobs)[0];
  $('run-page').value = '';
  $('run-refresh').checked = false;
  $('run-error').hidden = true;
  runFields();
  $('run-dialog').showModal();
}

function runFields() {
  const canRefresh = $('run-job-select').value.startsWith('brainstorm-') && Boolean($('run-page').value.trim());
  $('run-refresh-label').hidden = !canRefresh;
  if (!canRefresh) $('run-refresh').checked = false;
  $('run-page-label').hidden = !['organize-papers', 'organize-articles', 'brainstorm-material', 'brainstorm-idea'].includes($('run-job-select').value);
}

const descriptions = {
  "brainstorm-material": "从一篇论文、知识笔记或 Idea 研究记录出发，结合历史积累与公开资料寻找关联。报告中的独立提议可分别审批。",
  "brainstorm-idea": "围绕一个在研 Idea 寻找解释、方法和可验证的实验，把值得决策的条目提交 Workbench。",
  "propose-tasks": "归档 Inbox 中可复用的材料，将后续工作和 Elevated TODO 提交至 Workbench。",
  "organize-papers": "读取 Notero 中待处理的论文，将有依据的阅读摘要存入 Papers，有后续任务时再向 Workbench 提案。",
  "organize-articles": "读取简悦收藏的待处理文章，将有价值的材料归入 Knowledge 或 Papers，需要跟进时提交 Workbench。",
  "process-signals": "把 Papers 和 Research Feed 中勾选 Follow Up 的条目，以及 Research Interests 中待处理的方向，转成 Workbench 提案。",
  "reconcile-feedback": "将补充说明、修改要求或验收意见写回原始条目，供下次重新提案；驳回的提案则结束处理。",
  "process-workbench": "执行已批准的任务，或接收你提交的已有报告。验收通过后，提取值得归档的成果。",
  "recommend-papers": "按配置的星期自动选择深度或轻量采集，从 Discovery Pool 精选条目，生成当日 Research Feed。",
  "recommend-papers-deep": "用 Codex 搜索公开研究并探索新方向，补充候选池，保存后续检索线索，并生成当日推荐。",
  "recommend-papers-light": "优先沿用每周留下的检索线索，从 OpenReview 补充候选池，并生成当日推荐。"
};

function bindSchedules() {
  for (const [key, title] of Object.entries(state.jobs)) $('run-job-select').append(new Option(title, key));
  for (const [key, title] of Object.entries(state.jobs)) {
    const item = el('div', undefined, 'catalog-item');
    const copy = el('div', undefined, 'catalog-copy');
    copy.append(el('strong', title), el('small', key));
    if (descriptions[key]) copy.append(el('p', descriptions[key], 'catalog-description'));
    item.append(copy, button('运行一次', () => openRun(key)), button('安排计划', () => editor(key)));
    $('job-catalog').append(item);
  }
  $('run-job').onclick = () => openRun();
  $('new-schedule').onclick = () => editor();
  $('close-schedule').onclick = $('cancel-schedule').onclick = () => $('schedule-dialog').close();
  $('close-run').onclick = () => $('run-dialog').close();
  $('run-job-select').onchange = runFields;
  $('run-page').oninput = runFields;
  $('schedule-form').onchange = () => {
    frequencyFields();
    preview();
  };
  $('preview-schedule').onclick = preview;
  $('schedule-form').onsubmit = async event => {
    event.preventDefault();
    $('save-schedule').disabled = true;
    $('schedule-error').hidden = true;
    try {
      await api(`/panel/schedules/${encodeURIComponent($('schedule-job').value)}`, {
        method: 'PUT',
        body: JSON.stringify({
          ...specFromForm(),
          revision: editorRevision
        })
      });
      $('schedule-dialog').close();
      notice('定时计划已保存并应用，无需重启服务。');
      await requestRefresh();
    } catch (error) {
      $('schedule-error').textContent = error.message;
      $('schedule-error').hidden = false;
    } finally {
      $('save-schedule').disabled = false;
    }
  };
  $('sync-schedules').onclick = async () => {
    try {
      await api('/panel/schedules/sync', {
        method: 'POST'
      });
      notice('本地计划配置已同步至 DBOS。');
      await requestRefresh();
    } catch (error) {
      notice(error.message, true);
    }
  };
  $('run-form').onsubmit = async event => {
    event.preventDefault();
    $('submit-run').disabled = true;
    $('run-error').hidden = true;
    try {
      const job = $('run-job-select').value;
      const page = $('run-page-label').hidden ? null : $('run-page').value.trim() || null;
      const refresh = $('run-refresh').checked;
      const signature = JSON.stringify({ job, page, refresh });
      if (!dispatch || dispatch.signature !== signature) dispatch = {
        signature,
        request_id: crypto.randomUUID()
      };
      await api('/jobs', {
        method: 'POST',
        body: JSON.stringify({
          job,
          page,
          refresh,
          request_id: dispatch.request_id
        })
      });
      $('run-dialog').close();
      notice(`任务已提交：${state.jobs[job]}。可在执行记录中查看结果。`);
      location.hash = 'executions';
      await requestRefresh();
    } catch (error) {
      $('run-error').textContent = error.message;
      $('run-error').hidden = false;
    } finally {
      $('submit-run').disabled = false;
    }
  };
}
export {
  refreshSchedules,
  bindSchedules
};
