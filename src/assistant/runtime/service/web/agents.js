// Static interaction demo only. These samples never enter execution storage.
import {
  $,
  el,
  button
} from './ui.js';
const samples = [{
  role: 'Proposer',
  task: '为论文笔记起草整理提案',
  model: '示例模型 / local',
  elapsed: '2.8s',
  input: 842,
  output: 216,
  tools: [],
  inputText: '来源：Notero。整理论文要点，并说明需要后续调查的问题。',
  outputText: '已形成整理范围、预期产物和需要确认的事实。此为界面示例。'
}, {
  role: 'Investigator',
  task: '调查论文中的相关研究',
  model: '示例模型 / codex',
  elapsed: '18.4s',
  input: 3408,
  output: 972,
  tools: [
    ['web_search', '检索原论文与相关研究'],
    ['read_source', '阅读公开来源并记录证据']
  ],
  inputText: '根据已批准的提案，核对论文主张并提供可追溯的来源。',
  outputText: '调查报告包含证据、限制与待确认问题。此为界面示例。'
}, {
  role: 'Task Worker',
  task: '核验一个简单计算',
  model: '示例模型 / local',
  elapsed: '1.2s',
  input: 528,
  output: 38,
  tools: [
    ['calculate', '校验表达式 1 + 1']
  ],
  inputText: '计算 1 + 1，返回简洁结论。',
  outputText: '1 + 1 = 2。此为界面示例。'
}];

function selectSample(index) {
  const sample = samples[index];
  $('agent-demo-title').textContent = sample.role + ' · 示例调用';
  const container = el('div');
  container.append(el('p', sample.task, 'hint'), el('p', sample.model, 'quiet-tag'));
  const metrics = el('div', undefined, 'metric-grid');
  for (const [value, label] of [
      [sample.elapsed, '耗时'],
      [sample.input, '输入 tokens'],
      [sample.output, '输出 tokens']
    ]) {
    const node = el('div', String(value), 'metric');
    node.append(el('small', label));
    metrics.append(node);
  }
  container.append(metrics);
  container.append(el('h3', '工具调用'));
  for (const [name, description] of sample.tools) {
    const node = el('div', name, 'tool-line');
    node.append(el('small', description));
    container.append(node);
  }
  if (!sample.tools.length) container.append(el('p', '此示例直接生成结构化输出。', 'hint'));
  for (const [label, text] of [
      ['任务输入', sample.inputText],
      ['模型输出', sample.outputText]
    ]) {
    const section = el('details', undefined, 'saved-section');
    section.open = true;
    section.append(el('summary', label), el('pre', text));
    container.append(section);
  }
  $('agent-demo-detail').replaceChildren(container);
  [...$('agent-demo-list').children].forEach((row, i) => row.classList.toggle('selected', i === index));
}

function bindAgentDemo() {
  samples.forEach((sample, index) => {
    const row = button('', () => selectSample(index), 'activity-row agent-demo-row');
    const copy = el('div', undefined, 'activity-copy');
    copy.append(el('strong', sample.role), el('small', sample.task));
    row.append(copy, el('span', sample.elapsed, 'quiet-tag'));
    $('agent-demo-list').append(row);
  });
  selectSample(0);
}
export {
  bindAgentDemo
};
