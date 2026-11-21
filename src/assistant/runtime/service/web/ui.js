// Same-origin observer and explicit maintenance client. Saved content is always text.
const $ = id => document.getElementById(id);
const state = {
  runtime: '',
  page: 1,
  items: [],
  selected: new Set(),
  detail: null,
  busy: false,
  refreshAgain: false
};
const labels = {
  PENDING: '执行中',
  ENQUEUED: '排队中',
  DELAYED: '延后执行',
  SUCCESS: '已完成',
  ERROR: '失败',
  CANCELLED: '已取消',
  MAX_RECOVERY_ATTEMPTS_EXCEEDED: '恢复次数耗尽'
};
const terminal = new Set(['SUCCESS', 'ERROR', 'CANCELLED', 'MAX_RECOVERY_ATTEMPTS_EXCEEDED']);

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function button(text, handler, className) {
  const node = el('button', text, className);
  node.type = 'button';
  node.onclick = handler;
  return node;
}

function notice(text, error = false) {
  $('notice').textContent = text;
  $('notice').className = error ? 'error' : '';
  $('notice').hidden = false;
}

function date(value) {
  return value ? new Date(value).toLocaleString('zh-CN', {
    hour12: false
  }) : '—';
}

function duration(value) {
  if (value === null || value === undefined) return '—';
  const seconds = Math.floor(value / 1000);
  return seconds < 60 ? `${seconds} 秒` : seconds < 3600 ? `${Math.floor(seconds/60)} 分 ${seconds%60} 秒` : `${Math.floor(seconds/3600)} 小时 ${Math.floor(seconds%3600/60)} 分`;
}

function badge(status) {
  return el('span', labels[status] || status, `badge ${status}`);
}
async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      'X-Assistant-Runtime': state.runtime,
      'Content-Type': 'application/json',
      ...options.headers
    }
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}


let refreshHandler = async () => {};

function setRefresh(handler) {
  refreshHandler = handler;
}
async function requestRefresh() {
  return refreshHandler();
}

function confirmDialog(title, note, content, action, actionLabel = '确认') {
  $('confirm-title').textContent = title;
  $('confirm-note').textContent = note;
  $('confirm-content').replaceChildren(content);
  $('confirm-action').textContent = actionLabel;
  $('confirm-action').disabled = false;
  $('confirm-action').onclick = async () => {
    $('confirm-action').disabled = true;
    try {
      await action();
      $('confirm').close();
      await requestRefresh();
    } catch (error) {
      notice(error.message, true);
      $('confirm').close();
    } finally {
      $('confirm-action').disabled = false;
    }
  };
  $('confirm').showModal();
}


export {
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
  setRefresh,
  requestRefresh
};
