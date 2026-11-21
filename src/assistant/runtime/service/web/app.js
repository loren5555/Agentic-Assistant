import {
  refreshDashboard
} from './overview.js';
// Console navigation and refresh coordinate independent maintenance views.
import {
  $,
  state,
  notice,
  api,
  setRefresh
} from './ui.js';
import {
  refreshExecutions,
  refreshDetail,
  bindExecutions
} from './executions.js';
import {
  refreshSchedules,
  bindSchedules
} from './schedules.js';
import {
  bindAgentDemo
} from './agents.js';
const views = {
  overview: ['运行概览', '运行概览', '关注正在运行的任务、接下来的安排，以及需要处理的异常。'],
  schedules: ['任务编排', '日常任务编排', '创建与调整重复任务；保存后立即应用，重启后继续保留。'],
  executions: ['执行记录', '执行历史与结果', '查看任务状态、检查已保存的产物，恢复或清理需要关注的记录。'],
  agents: ['Agent 调用', 'Agent 调用记录', '模型调用观测的交互 Demo。真实调用记录将在后续接入。']
};

function navigate() {
  const key = Object.hasOwn(views, location.hash.slice(1)) ? location.hash.slice(1) : 'overview';
  for (const name of Object.keys(views)) $('view-' + name).hidden = name !== key;
  for (const link of document.querySelectorAll('[data-view]')) {
    if (link.dataset.view === key) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
  const [name, title, description] = views[key];
  $('view-breadcrumb').textContent = name;
  $('view-title').textContent = title;
  $('view-description').textContent = description;
  $('view-eyebrow').textContent = 'OPERATIONS / ' + key.toUpperCase();
}
async function refresh() {
  if (!state.runtime) return;
  if (state.busy) {
    state.refreshAgain = true;
    return;
  }
  state.busy = true;
  try {
    await Promise.all([refreshDashboard(), refreshSchedules(), refreshExecutions(), refreshDetail()]);
    $('connection').textContent = '服务在线';
    $('connection').className = 'connection';
    $('updated').textContent = `更新于 ${new Date().toLocaleTimeString('zh-CN',{hour12:false})}`;
  } catch (error) {
    $('connection').textContent = '刷新失败';
    $('connection').className = 'connection offline';
    notice(`无法刷新：${error.message}`, true);
  } finally {
    state.busy = false;
    if (state.refreshAgain) {
      state.refreshAgain = false;
      queueMicrotask(refresh);
    }
  }
}
async function start() {
  navigate();
  bindExecutions();
  bindAgentDemo();
  setRefresh(refresh);
  window.addEventListener('hashchange', navigate);
  $('refresh').onclick = refresh;
  for (const card of document.querySelectorAll('.stat')) card.onclick = () => {
    location.hash = 'executions';
    $('status').value = card.dataset.status;
    $('search').value = '';
    $('job').value = '';
    $('since').value = ['PENDING', 'FAILED'].includes(card.dataset.status) ? 'all' : '24h';
    $('all-levels').checked = false;
    state.page = 1;
    state.selected.clear();
    refresh();
  };
  try {
    const data = await api('/panel/bootstrap');
    state.runtime = data.runtime;
    state.jobs = data.jobs;
    $('version').textContent = `Runtime ${data.application_version.slice(0,12)}`;
    for (const [key, title] of Object.entries(data.jobs)) $('job').append(new Option(title, key));
    bindSchedules();
    await refresh();
  } catch (error) {
    notice(`服务连接失败：${error.message}。请刷新页面重试。`, true);
    $('connection').textContent = '未连接';
  }
  setInterval(() => {
    if (!document.hidden && !document.querySelector('dialog[open]')) refresh();
  }, 5000);
}
start();
