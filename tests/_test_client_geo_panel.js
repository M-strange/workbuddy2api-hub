/* 「来源 IP 自动显示地区」在面板上的两处落点。

   Why this suite exists: the backend resolves an address to a region
   (wb_client_geo, cached for 7 days, looked up in the background) and hands it
   to the panel as client_ip_geo on /usage/recent rows and geo on
   /usage/by-client-ip rows. This file pins what the panel does with that field:

     - the request log shows the region under the address, in the same cell,
     - a row without the field (old row, or a lookup that has not landed yet)
       renders the address alone - no stray line, no invented label,
     - the search box matches the region too, so "江苏" finds those requests,
     - the aggregate view has its own region column and an em dash when the
       lookup is still pending.

   Run with Node. */
'use strict';

const assert = require('assert');
const {dashboardScript} = require('./_dashboard_source.js');

const script = dashboardScript();
const dom = require('./_dom_stub.js');

const ROWS = [
  {iso: '2026-11-09T12:00:00', model: 'deepseek-v4.1-flash', stream: true,
   outcome: 'completed', elapsed_ms: 1000, ttft_ms: 500, tokens_per_sec: 10,
   prompt_tokens: 10, completion_tokens: 5, reasoning_tokens: 0,
   total_tokens: 15, credit: 0, account: 'uid-1',
   client_ip: '221.227.155.89', client_ip_geo: '江苏 苏州'},
  {iso: '2026-11-09T12:01:00', model: 'hy3', stream: false, outcome: 'completed',
   elapsed_ms: 800, ttft_ms: null, prompt_tokens: 4, completion_tokens: 2,
   total_tokens: 6, credit: 0, account: 'uid-2',
   client_ip: '10.0.0.7', client_ip_geo: '内网'},
  // A row whose region has not landed yet (or the switch is off): no field.
  {iso: '2026-11-09T12:02:00', model: 'hy3', stream: false, outcome: 'completed',
   elapsed_ms: 700, ttft_ms: null, prompt_tokens: 4, completion_tokens: 2,
   total_tokens: 6, credit: 0, account: 'uid-3', client_ip: '203.0.113.7'},
];

let IPS = {
  ips: [
    {ip: '221.227.155.89', geo: '江苏 苏州', requests: 12, total_tokens: 4200,
     prompt_tokens: 3000, completion_tokens: 800, reasoning_tokens: 400,
     cached_tokens: 1000, first_at: 1762400000, last_at: 1762480000,
     models: [['deepseek-v4.1-flash', 12]], accounts: [['uid-1', 12]]},
    {ip: '203.0.113.7', geo: '', requests: 3, total_tokens: 300,
     prompt_tokens: 200, completion_tokens: 100, reasoning_tokens: 0,
     cached_tokens: 0, first_at: 1762400000, last_at: 1762470000,
     models: [['hy3', 3]], accounts: [['uid-2', 3]]},
  ],
  accounts: [
    {account: 'uid-1', requests: 12, last_at: 1762480000,
     ips: [['221.227.155.89', 12]]},
  ],
};

const domWindow = dom.installDom({
  fetch: url => {
    const target = String(url);
    let payload = {rows: [], total: 0, accounts_map: {}, accounts: [], slots: [],
                   data: [], results: [], byAccount: [], ips: [], models: []};
    if (target.includes('/usage/recent')) {
      payload = {rows: ROWS, total: ROWS.length, page: 1, total_pages: 1,
                 accounts_map: {}};
    } else if (target.includes('/usage/by-client-ip')) {
      payload = IPS;
    }
    return Promise.resolve({
      status: 200, ok: true,
      json: () => Promise.resolve(payload),
      text: () => Promise.resolve(JSON.stringify(payload)),
    });
  },
});
domWindow.ACCOUNTS = [];
global.ACCOUNTS = domWindow.ACCOUNTS;

const api = new Function(script + [
  'window.updateUI = updateUI;',
  'window.toast = toast;',
  'return {refresh: refresh, renderRecentView: renderRecentView,',
  '  filters: RECENT_FILTERS, clientIps: (window.wbaClientIps || null)};',
].join('\n'))();

// 请求记录表是整个 <table>（含 tbody），来源 IP 表只有 tbody 的 innerHTML；
// 两者都只认 <tr>，不假设外层包了什么。
function bodyRows(html) {
  return [...html.matchAll(/<tr>([\s\S]*?)<\/tr>/g)].map(row => {
    const cells = {};
    for (const cell of row[1].matchAll(/<td([^>]*)>([\s\S]*?)<\/td>/g)) {
      const label = (cell[1].match(/data-label="([^"]*)"/) || [])[1];
      if (label) cells[label] = cell[2];
    }
    return cells;
  }).filter(cells => Object.keys(cells).length);  // 表头那行没有 <td>
}

let checks = 0;
function check(label, cond, extra) {
  checks += 1;
  assert.ok(cond, label + (extra ? '  [' + extra + ']' : ''));
}

(async () => {
  window.VIEW_REALM = 'intl';
  await api.refresh();
  const rendered = dom.byId('recent').innerHTML;
  const rows = bodyRows(rendered);
  const byModel = (model) => rows.find(r => (r['模型'] || '') === model);
  const withGeo = rows[0];
  const withoutGeo = rows[2];

  check('请求记录：地址与地区在同一个单元格',
        withGeo && withGeo['来源 IP'].includes('221.227.155.89')
          && withGeo['来源 IP'].includes('江苏 苏州'),
        withGeo && withGeo['来源 IP']);
  check('请求记录：内网地址显示内网', rows[1] && rows[1]['来源 IP'].includes('内网'),
        rows[1] && rows[1]['来源 IP']);
  check('请求记录：没有地区的行只显示地址',
        withoutGeo && withoutGeo['来源 IP'].includes('203.0.113.7')
          && !withoutGeo['来源 IP'].includes('<div'),
        withoutGeo && withoutGeo['来源 IP']);

  // 搜索框认地区：输「江苏」应当只剩那条请求。
  api.filters.query = '江苏';
  api.renderRecentView();
  let filtered = bodyRows(dom.byId('recent').innerHTML);
  check('搜索地区命中请求', filtered.length === 1, 'rows=' + filtered.length);
  check('命中的就是江苏那条',
        filtered[0] && filtered[0]['来源 IP'].includes('江苏 苏州'),
        filtered[0] && filtered[0]['来源 IP']);

  api.filters.query = '内网';
  api.renderRecentView();
  filtered = bodyRows(dom.byId('recent').innerHTML);
  check('搜索内网命中内网请求', filtered.length === 1, 'rows=' + filtered.length);

  api.filters.query = '';
  api.renderRecentView();

  // ---- 来源 IP 聚合视图 ----
  await api.clientIps.load();
  const html = dom.byId('clientIpBody').innerHTML;
  const ipRows = bodyRows(html);
  // 表头是静态标记（渲染器只换 tbody），所以直接查源文件而不是 DOM。
  const fs = require('fs');
  const path = require('path');
  const source = fs.readFileSync(path.join(__dirname, '..', 'dashboard.html'), 'utf8');
  check('来源 IP 表有地区列',
        /<th>来源 IP<\/th>\s*<th>地区<\/th>/.test(source), '静态表头里没有地区列');
  check('来源 IP 行显示地区', ipRows[0] && ipRows[0]['地区'] === '江苏 苏州', ipRows[0] && ipRows[0]['地区']);
  check('还没查到的地址显示破折号', ipRows[1] && ipRows[1]['地区'].trim() === '—', ipRows[1] && ipRows[1]['地区']);

  IPS = {ips: [], accounts: []};
  await api.clientIps.load();
  const empty = dom.byId('clientIpBody').innerHTML;
  check('空载荷仍是空状态且列数对得上', empty.includes('暂无数据') && empty.includes('colspan="6"'),
        empty.slice(0, 160));

  console.log('client-geo panel assertions passed (' + checks + ' checks)');
})().catch(err => {
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
});
