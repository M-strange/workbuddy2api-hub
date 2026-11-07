/* The recent-requests table shows where each request came from.

   record_usage() writes client_ip onto the usage row (see
   tests/_test_client_ip_logging.py), /usage/recent hands the row through
   untouched, and the table renders it in its own 来源 IP column. Rows written
   before the field existed - and rows from call sites that cannot know the
   peer address - must show a dash there, not an empty cell or a neighbour's
   address.

   Cells are addressed by the data-label the renderer already emits for the card
   layout, so the assertions say which row carries which address without
   pinning the table's column count: another column appearing elsewhere is not a
   regression in this feature.
   Run with Node.
*/
const assert = require('assert');
const {dashboardScript} = require('./_dashboard_source.js');

const script = dashboardScript();

const dom = require('./_dom_stub.js');
const {window: domWindow} = dom.installDom({
  fetch: url => {
    const payload = String(url).includes('/usage/recent')
      ? {rows: ROWS, total: 2, page: 1, total_pages: 1, accounts_map: {}}
      : {rows: [], total: 0, accounts_map: {}, accounts: [], slots: [], data: [],
         results: [], byAccount: []};
    return Promise.resolve({
      status: 200, ok: true,
      json: () => Promise.resolve(payload),
      text: () => Promise.resolve(JSON.stringify(payload)),
    });
  },
});
domWindow.ACCOUNTS = [];
global.ACCOUNTS = domWindow.ACCOUNTS;

const ROWS = [
  // Behind a reverse proxy: the trusted peer forwarded the real client address.
  {iso: '2026-11-07T11:20:00', model: 'deepseek-v4.1-flash', stream: true,
   outcome: 'completed', elapsed_ms: 1200, ttft_ms: 800, tokens_per_sec: 100,
   prompt_tokens: 10, completion_tokens: 5, reasoning_tokens: 3, cache_hit_pct: 90,
   total_tokens: 15, credit: 0, account: 'uid-1', client_ip: '203.0.113.7'},
  // Written before the field existed (or by a call site with no peer): no key.
  {iso: '2026-11-07T11:21:00', model: 'hy3', stream: false, outcome: 'completed',
   elapsed_ms: 900, ttft_ms: null, prompt_tokens: 4, completion_tokens: 2,
   total_tokens: 6, credit: 0, account: 'uid-1'},
];

function headerLabels(html) {
  const head = html.slice(html.indexOf('<thead>'), html.indexOf('</thead>'));
  return [...head.matchAll(/<th[^>]*>([\s\S]*?)<\/th>/g)].map(m => m[1].trim());
}

function bodyRows(html) {
  const body = html.slice(html.indexOf('<tbody>'), html.indexOf('</tbody>'));
  return [...body.matchAll(/<tr>([\s\S]*?)<\/tr>/g)].map(row => {
    const cells = {};
    for (const cell of row[1].matchAll(/<td([^>]*)>([\s\S]*?)<\/td>/g)) {
      const label = (cell[1].match(/data-label="([^"]*)"/) || [])[1];
      if (label) cells[label] = cell[2];
    }
    return cells;
  });
}

const api = new Function(script + `
  window.updateUI = updateUI;
  window.toast = toast;
  return { refresh };`)();

(async () => {
  window.VIEW_REALM = 'intl';
  await api.refresh();
  const rendered = dom.byId('recent').innerHTML;
  let checks = 0;
  const check = (label, cond, extra) => {
    checks += 1;
    assert.ok(cond, label + (extra ? '  [' + extra + ']' : ''));
  };

  const headers = headerLabels(rendered);
  const rows = bodyRows(rendered);
  const rowOf = model => rows.find(r => r['模型'] === model);
  const withIp = rowOf('deepseek-v4.1-flash');
  const withoutIp = rowOf('hy3');

  check('the table has a 来源 IP column', headers.includes('来源 IP'), headers.join(' | '));
  check('the row that recorded an address shows it',
        withIp && withIp['来源 IP'].trim() === '203.0.113.7', withIp && withIp['来源 IP']);
  check('the address is in the row it belongs to, not a neighbour',
        rows.filter(r => /203\.0\.113\.7/.test(r['来源 IP'] || '')).length === 1,
        rows.map(r => r['模型'] + '=' + (r['来源 IP'] || '')).join(', '));
  check('a row without the field shows a dash, not an empty cell',
        withoutIp && /—/.test(withoutIp['来源 IP']), withoutIp && withoutIp['来源 IP']);
  check('the address does not leak into another column',
        rows.every(r => Object.keys(r).every(label =>
          label === '来源 IP' || !/203\.0\.113\.7/.test(r[label]))),
        rows.map(r => Object.keys(r).filter(l => /203\.0\.113\.7/.test(r[l])).join('/')).join(', '));

  console.log('recent-requests client-ip assertions passed (' + checks + ' checks)');
})();
