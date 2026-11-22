// Real provider traces projected from the step that owns each invocation.
import {$, api, el, button, date, notice} from './ui.js';
import {recordList, showRecord, fields} from './records.js';
import {openDetail} from './executions.js';

export function lines(title, entries) {
  const group = el('section', undefined, 'activity-section');
  group.append(el('h3', title));
  for (const value of entries) {
    const link = value.match(/^(?:页面：)?(https?:\/\/\S+)$/);
    if (link) {
      const a = el('a', '打开成果页面 ↗');
      a.href = link[1]; a.target = '_blank'; a.rel = 'noopener noreferrer';
      group.append(a);
    } else group.append(el('p', value));
  }
  return group;
}

function tokens(count) {
  return Number.isFinite(count) ? count.toLocaleString('zh-CN') : '未记录';
}

function totalTokens(call) {
  if (Number.isFinite(call.tokens_in) && Number.isFinite(call.tokens_out)) {
    return tokens(call.tokens_in + call.tokens_out);
  }
  return '未记录';
}

export function showCall(step, workflow, task) {
  const call = step.call;
  const body = el('div');
  body.append(fields([['所属任务',task],['业务步骤',step.action],['供应商',call.provider || '未记录'],
    ['模型',call.model || '未记录'],['总 Token',totalTokens(call)],
    ['输入 Token',tokens(call.tokens_in)],['输出 Token',tokens(call.tokens_out)]]));
  if (call.tools.length) body.append(lines('使用的工具', call.tools));
  body.append(lines('调用输入',call.input.length ? call.input : ['该次调用未单独保存可展示的输入。']));
  body.append(lines('调用结果',step.result.length ? step.result : ['该次调用未单独保存可展示的结果。']));
  showRecord(call.module, 'Agent 调用', body, [button('查看所属步骤', async () => {
    $('record-dialog').close();
    location.hash='executions';
    await openDetail(workflow);
    const node=document.getElementById('activity-step-'+workflow+'-'+step.number);
    if (node) { node.open=true; node.scrollIntoView({block:'center'}); node.querySelector('summary').focus(); }
  })]);
}

let next=null;
let calls=[];
let loading=false;
let browsingHistory=false;
let signature;
export async function loadCalls(more=false, background=false) {
  if (loading || (background && browsingHistory)) return;
  loading=true;
  try {
    const data=await api('/panel/calls'+(more && next ? '?before='+next : ''));
    calls=more ? calls.concat(data.calls) : data.calls;
    next=data.next;
    browsingHistory=more;
    const version=JSON.stringify([calls,next]);
    if (version===signature) return;
    signature=version;
    const container=$('agent-demo-list');
    container.replaceChildren(calls.length ? recordList(['所属任务','模块','业务步骤','供应商','模型','总 Token','调用时间'],calls.map(s=>({
      title:s.task,values:[s.module,s.action,s.call.provider || '未记录',s.call.model || '未记录',totalTokens(s.call),date(s.time)],open:()=>showCall(s,s.workflow,s.task)
    }))) : el('p','当前范围内没有已保存的 Agent 调用。','empty'));
    if(next) container.append(button('查看更早记录',()=>loadCalls(true).catch(error=>notice(error.message,true)),'link-button'));
  } catch (error) {
    signature=undefined;
    $('agent-demo-list').replaceChildren(el('p','暂时无法读取调用记录，请确认管理服务已更新。','empty'));
    throw error;
  } finally { loading=false; }
}
