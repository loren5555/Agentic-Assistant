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

function specFromForm() {
  const frequency = $('schedule-frequency').value;
  const [hour, minute] = $('schedule-time').value.split(':').map(Number);
  let cron = $('schedule-cron').value.trim();
  if (frequency === 'daily') cron = `0 ${minute} ${hour} * * *`;
  if (frequency === 'weekly') cron = `0 ${minute} ${hour} * * ${$('schedule-weekday').value}`;
  if (frequency === 'monthly') cron = `0 ${minute} ${hour} ${$('schedule-monthday').value} * *`;
  if (frequency === 'hourly') cron = `0 ${$('schedule-minute').value} * * * *`;
  return {
    cron,
    timezone: $('schedule-timezone').value,
    enabled: $('schedule-enabled').checked
  };
}

function frequencyFields() {
  const mode = $('schedule-frequency').value;
  $('schedule-time-label').hidden = ['custom', 'hourly'].includes(mode);
  $('schedule-time').required = !$('schedule-time-label').hidden;
  $('schedule-weekday-label').hidden = mode !== 'weekly';
  $('schedule-monthday-label').hidden = mode !== 'monthly';
  $('schedule-cron-label').hidden = mode !== 'custom';
  $('schedule-minute-label').hidden = mode !== 'hourly';
  $('schedule-cron').required = mode === 'custom';
  for (const [field, label] of [
      ['schedule-time', 'schedule-time-label'],
      ['schedule-weekday', 'schedule-weekday-label'],
      ['schedule-monthday', 'schedule-monthday-label'],
      ['schedule-minute', 'schedule-minute-label'],
      ['schedule-cron', 'schedule-cron-label']
    ]) {
    $(field).disabled = $(label).hidden;
    $(field).required = !$(label).hidden;
  }
}
async function preview() {
  const sequence = ++previewSequence;
  $('schedule-preview').textContent = '计算执行时间…';
  const spec = specFromForm();
  $('schedule-expression').textContent = `${spec.cron} · ${spec.timezone}`;
  try {
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

function describe(item) {
  const fields = item.cron.split(/\s+/);
  if (fields[0] !== '0') return '自定义时间';
  if (/^\d+$/.test(fields[1]) && /^\d+$/.test(fields[2])) {
    const time = `${fields[2].padStart(2,'0')}:${fields[1].padStart(2,'0')}`;
    if (fields.slice(3).join(' ') === '* * *') return `每天 ${time}`;
    if (fields[3] === '*' && fields[4] === '*' && /^\d$/.test(fields[5])) return `每周${'日一二三四五六'[Number(fields[5])]} ${time}`;
    if (/^\d+$/.test(fields[3]) && fields[4] === '*' && fields[5] === '*') return `每月 ${fields[3]} 日 ${time}`;
  }
  if (/^\d+$/.test(fields[1]) && fields.slice(2).join(' ') === '* * * *') return `每小时 ${fields[1]} 分`;
  return '自定义时间';
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
  $('schedule-frequency').value = 'daily';
  $('schedule-time').value = '07:00';
  $('schedule-minute').value = '0';
  $('schedule-weekday').value = '1';
  $('schedule-monthday').value = '1';
  const zone = existing?.timezone || 'Asia/Shanghai';
  if (![...$('schedule-timezone').options].some(option => option.value === zone)) $('schedule-timezone').append(new Option(zone, zone));
  $('schedule-timezone').value = zone;
  $('schedule-enabled').checked = existing?.enabled ?? true;
  $('schedule-cron').value = existing?.cron || '0 0 7 * * *';
  if (existing) {
    $('schedule-frequency').value = 'custom';
    const text = describe(existing);
    const fields = existing.cron.split(/\s+/);
    if (text.startsWith('每天')) $('schedule-frequency').value = 'daily';
    if (text.startsWith('每周')) {
      $('schedule-frequency').value = 'weekly';
      $('schedule-weekday').value = fields[5];
    }
    if (text.startsWith('每月') && Number(fields[3]) <= 28) {
      $('schedule-frequency').value = 'monthly';
      $('schedule-monthday').value = fields[3];
    }
    if (text.startsWith('每小时')) {
      $('schedule-frequency').value = 'hourly';
      $('schedule-minute').value = fields[1];
    }
    if (/^\d+$/.test(fields[2])) $('schedule-time').value = `${fields[2].padStart(2,'0')}:${fields[1].padStart(2,'0')}`;
  }
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
  $('schedule-summary').textContent = `${data.items.length} 个定时计划 · ${data.items.filter(item=>item.enabled).length} 个已启用${data.pending_removals?.length?` · ${data.pending_removals.length} 条远端计划待移除`:""}`;
  $('new-schedule').disabled = !data.editable;
  const version = JSON.stringify([data.items, data.editable]);
  if (version !== listVersion) {
    listVersion = version;
    const rows = data.items.map(item => ({
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
  "propose-tasks": "读取 Inbox 新条目和标为 Elevated 的 TODO，将待办整理成 Workbench 提案供你审批。",
  "organize-papers": "读取 Notero 中待处理的论文，为每篇起草整理提案。执行并验收后，再将阅读成果存入 Papers 等目标库。",
  "organize-articles": "读取简悦收藏的待处理文章，提炼要点并提交 Workbench，由你决定哪些剪辑值得进一步整理。",
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
  $('schedule-frequency').onchange = () => {
    frequencyFields();
    preview();
  };
  $('preview-schedule').onclick = preview;
  for (const id of ['schedule-time', 'schedule-weekday', 'schedule-monthday', 'schedule-minute', 'schedule-cron', 'schedule-timezone']) $(id).onchange = preview;
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
