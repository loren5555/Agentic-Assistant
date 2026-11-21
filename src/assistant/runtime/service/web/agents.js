// Static interaction demo only. These samples never enter execution storage.
import {
  $,
  el
} from './ui.js';
import { recordList, showRecord } from './records.js';
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
  showRecord(sample.task, sample.role + ' · 调用详情（示例）', container);
}

function bindAgentDemo() {
  const rows = samples.map((sample, index) => ({
    title: sample.task,
    values: [sample.role, sample.model.split(' / ').at(-1), sample.elapsed,
             (sample.input + sample.output).toLocaleString(), String(sample.tools.length)],
    open: () => selectSample(index)
  }));
  $('agent-demo-list').replaceChildren(recordList(['任务', '智能体', '提供方', '耗时', 'Tokens', '工具'], rows));
}
export {
  bindAgentDemo
};
