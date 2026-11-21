// A keyboard-accessible master list with a shared, focus-trapped detail sheet.
import { $, el, button } from './ui.js';

export function recordList(headings, records) {
  const table = el('table', undefined, 'record-table');
  const header = table.createTHead().insertRow();
  for (const heading of headings) {
    const cell = el('th', heading);
    cell.scope = 'col';
    header.append(cell);
  }
  const body = table.createTBody();
  for (const {title, values, open} of records) {
    const row = body.insertRow();
    const link = button(title, open, 'record-link');
    link.setAttribute('aria-haspopup', 'dialog');
    row.insertCell().append(link);
    for (const value of values) row.insertCell().append(value);
    row.onclick = event => { if (!event.target.closest('button')) link.click(); };
  }
  return table;
}

export function showRecord(title, category, content, actions = []) {
  const dialog = $('record-dialog');
  $('record-title').textContent = title;
  $('record-category').textContent = category;
  $('record-body').replaceChildren(content);
  $('record-actions').replaceChildren(...actions);
  if (!dialog.open) dialog.showModal();
}

export function fields(entries) {
  const list = el('dl', undefined, 'record-fields');
  for (const [name, value] of entries) list.append(el('dt', name), el('dd', value));
  return list;
}
