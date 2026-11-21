import {lines, showCall} from './agents.js';
import {
  $,
  state,
  labels,
  terminal,
  el,
  button,
  notice,
  date,
  duration,
  badge,
  api,
  confirmDialog,
  requestRefresh
} from './ui.js';

function selection() {
  $('selected-count').textContent = state.selected.size ? `已选 ${state.selected.size} 条` : '';
  $('delete-selected').disabled = !state.selected.size;
  $('select-page').checked = state.items.length > 0 && state.items.every(item => state.selected.has(item.id));
  $('select-page').indeterminate = state.items.some(item => state.selected.has(item.id)) && !$('select-page').checked;
}

function renderRuns(data) {
  state.page = data.page;
  state.items = data.items;
  const rows = document.createDocumentFragment();
  for (const run of data.items) {
    const row = el('tr');
    const check = el('td', undefined, 'check');
    const input = el('input');
    input.type = 'checkbox';
    input.checked = state.selected.has(run.id);
    input.setAttribute('aria-label', `选择 ${run.title}`);
    input.onchange = () => {
      if (input.checked && state.selected.size >= 50) {
        input.checked = false;
        notice('每次最多选择 50 条记录。请先处理当前选择。', true);
      } else {
        input.checked ? state.selected.add(run.id) : state.selected.delete(run.id);
      }
      selection();
    };
    check.append(input);
    row.append(check);
    const title = el('td');
    title.append(button(run.title, () => openDetail(run.id), 'run-title'));
    row.append(title);
    const status = el('td');
    status.append(badge(run.status));
    row.append(status);
    row.append(el('td', date(run.created_at)), el('td', duration(run.duration_ms)));
    const action = el('td');
    action.append(button('查看 →', () => openDetail(run.id), 'row-open'));
    row.append(action);
    rows.append(row);
  }
  $('runs').replaceChildren(rows);
  $('empty').hidden = !!data.items.length;
  $('page-info').textContent = `共 ${data.total} 条 · 第 ${data.page} / ${Math.max(1,Math.ceil(data.total/data.page_size))} 页`;
  $('previous').disabled = data.page <= 1;
  $('next').disabled = data.page * data.page_size >= data.total;
  selection();
}

function links(title, items) {
  const group = el('div');
  group.append(el('h3', title));
  if (!items.length) group.append(el('p', '无', 'hint'));
  for (const item of items) group.append(button(`${item.title} · ${labels[item.status]||item.status}`, () => openDetail(item.id), 'link-button'));
  return group;
}
async function openDetail(id) {
  state.detail = id;
  state.detailSignature = null;
  $('drawer').hidden = false;
  $('drawer-backdrop').hidden = false;
  $('detail-title').textContent = '读取执行详情…';
  $('detail-content').replaceChildren();
  $('detail-actions').replaceChildren();
  $('detail-meta').replaceChildren();
  await refreshDetail();
}
async function refreshDetail() {
  const id = state.detail;
  if (!id) return;
  try {
    const data = await api(`/panel/runs/${encodeURIComponent(id)}/activity`);
    if (state.detail !== id) return;
    if (!data.run) throw new Error('服务版本需要更新');
    const signature = JSON.stringify({
      ...data,
      run: {
        ...data.run,
        duration_ms: null
      }
    });
    if (state.detailSignature === signature) {
      const elapsed = $('detail-duration');
      if (elapsed) elapsed.textContent = duration(data.run.duration_ms);
      return;
    }
    state.detailSignature = signature;
    const run = data.run;
    $('detail-title').textContent = data.subject || run.title;
    const meta = el('div');
    meta.append(badge(run.status));
    const fields = el('div', undefined, 'detail-kv');
    for (const [key, value] of [
        ['工作流', run.title],
        ['创建时间', date(run.created_at)],
        ['结束时间', date(run.completed_at)],
        ['耗时', duration(run.duration_ms)]
      ]) {
      const entry = el('span', value);
      if (key === '耗时') entry.id = 'detail-duration';
      fields.append(el('div', key), entry);
    }
    meta.append(fields);
    $('detail-meta').replaceChildren(meta);
    const actions = [];
    if (!terminal.has(run.status)) actions.push(button('取消任务', () => confirmCancel(run)));
    if (['ERROR', 'CANCELLED', 'MAX_RECOVERY_ATTEMPTS_EXCEEDED'].includes(run.status)) actions.push(button('恢复执行', () => resume(run)));
    if (terminal.has(run.status)) actions.push(button('删除记录', () => deletePreview([id]), 'danger subtle'));
    $('detail-actions').replaceChildren(...actions);
    const content = document.createDocumentFragment();
    if (data.error.length) content.append(lines('错误信息', data.error));
    if (data.input.length) content.append(lines('任务输入', data.input));
    if (data.result.length) content.append(lines('执行结果', data.result));
    if (data.steps.length) content.append(el('h3','处理过程'));
    for (const step of data.steps) {
      const node = el('details', undefined, 'activity-step');
      node.id='activity-step-'+step.workflow+'-'+step.number;
      const heading=el('summary',step.action);
      heading.append(el('span',step.module,'quiet-tag'));
      node.append(heading);
      if (step.subject) node.append(el('strong',step.subject));
      for (const text of step.error.concat(step.result)) node.append(el('p',text));
      if (!step.result.length && !step.error.length) node.append(el('p','已执行，此步骤没有单独的输出。','hint'));
      if (step.call) node.append(button('查看 Agent 调用',()=>showCall(step,step.workflow,step.subject || data.subject || run.title),'link-button'));
      content.append(node);
    }
    if (data.more_steps) content.append(el('p','已显示前 120 个业务步骤，打开下级任务可继续查看。','hint'));
    if (data.children.length) content.append(links('下级任务', data.children));
    if (data.parents.length) content.append(links('所属任务', data.parents));
    if (!data.steps.length && !data.children.length && !data.result.length && !data.error.length)
      content.append(el('p','当前没有已保存的业务结果。','hint'));
    // Preserve folded sections during periodic refresh.
    const previous = [...$('detail-content').querySelectorAll('details')].map(node => node.open);
    $('detail-content').replaceChildren(content);
    [...$('detail-content').querySelectorAll('details')].forEach((node, index) => {
      if (index < previous.length) node.open = previous[index];
    });
  } catch (error) {
    if (state.detail === id) $('detail-content').replaceChildren(el('p', '无法加载业务记录。请确认服务已运行新版后端。', 'hint'));
  }
}

function closeDetail() {
  state.detail = null;
  $('drawer').hidden = true;
  $('drawer-backdrop').hidden = true;
}

function confirmCancel(run) {
  confirmDialog('取消当前任务？', '取消只针对本条执行。正在进行的模型、网络或脚本调用可能继续到返回；子任务不会自动取消。', el('strong', run.title), async () => {
    const result = await api(`/panel/runs/${encodeURIComponent(run.id)}/cancel`, {
      method: 'POST'
    });
    notice(`取消已记录：${run.title}。${result.note}`);
  }, '确认取消');
}
async function resume(run) {
  try {
    const result = await api(`/workflows/${encodeURIComponent(run.id)}/resume`, {
      method: 'POST',
      body: JSON.stringify({
        request_id: crypto.randomUUID()
      })
    });
    notice(`恢复请求已提交：${run.title}。恢复任务 ID：${result.id}`);
    await requestRefresh();
  } catch (error) {
    notice(error.message, true);
  }
}
async function deletePreview(ids) {
  try {
    const data = await api('/panel/delete-preview', {
      method: 'POST',
      body: JSON.stringify({
        ids
      })
    });
    const content = el('div');
    for (const item of data.items) {
      const node = el('div', undefined, 'preview-item');
      node.append(el('strong', item.title), el('span', item.allowed ? `可删除 · ${item.references.step_count} 个检查点` : `保留 · ${item.reasons.join('；')}`));
      if (item.allowed) node.append(el('small', ` · 保留 ${item.references.children.length} 个子任务`));
      content.append(node);
    }
    confirmDialog('删除执行记录', '仅删除所选 DBOS 记录及其检查点。Notion 内容和业务索引保留；子任务不会被递归删除。删除后将无法从这些检查点恢复。', content, async () => {
      const result = await api('/panel/delete', {
        method: 'POST',
        body: JSON.stringify({
          ids,
          token: data.token
        })
      });
      const removed = result.items.filter(item => item.status === 'deleted');
      for (const item of removed) {
        state.selected.delete(item.id);
        if (state.detail === item.id) closeDetail();
      }
      notice(`已删除 ${removed.length} 条记录。` + result.items.filter(item => item.status !== 'deleted').map(item => `\n保留 ${data.items.find(row=>row.id===item.id)?.title||item.id}：${item.error||item.reasons.join('；')}`).join(''));
    }, `删除 ${data.allowed_count} 条记录`);
    $('confirm-action').disabled = !data.allowed_count;
  } catch (error) {
    notice(error.message, true);
  }
}

async function refreshExecutions() {
  const params = new URLSearchParams({
    page: state.page,
    page_size: 25,
    scope: $('all-levels').checked ? 'all' : 'roots',
    status: $('status').value,
    job: $('job').value,
    search: $('search').value.trim(),
    since: $('since').value
  });
  const data = await api(`/panel/runs?${params}`);
  renderRuns(data);

}

function bindExecutions() {
  $('filters').onsubmit = event => {
    event.preventDefault();
    state.page = 1;
    state.selected.clear();
    requestRefresh();
  };
  for (const id of ['job', 'status', 'since', 'all-levels']) $(id).onchange = () => {
    state.page = 1;
    state.selected.clear();
    requestRefresh();
  };
  $('previous').onclick = () => {
    state.page--;
    requestRefresh();
  };
  $('next').onclick = () => {
    state.page++;
    requestRefresh();
  };

  $('select-page').onchange = event => {
    for (const item of state.items) {
      if (!event.target.checked) state.selected.delete(item.id);
      else if (state.selected.size < 50) state.selected.add(item.id);
      else notice('每次最多选择 50 条记录。', true);
    }
    [...$('runs').querySelectorAll('input[type=checkbox]')].forEach((input, index) => {
      input.checked = state.selected.has(state.items[index].id);
    });
    selection();
  };
  $('delete-selected').onclick = () => deletePreview([...state.selected]);
  $('close-detail').onclick = closeDetail;
  $('drawer-backdrop').onclick = closeDetail;
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !$('confirm').open) closeDetail();
  });

  $('show-errors').onclick = () => {
    $('status').value = 'FAILED';
    $('search').value = '';
    $('job').value = '';
    $('since').value = 'all';
    $('all-levels').checked = true;
    state.page = 1;
    state.selected.clear();
    requestRefresh();
  };
}
export {
  openDetail,
  closeDetail,
  refreshDetail,
  refreshExecutions,
  bindExecutions
};
