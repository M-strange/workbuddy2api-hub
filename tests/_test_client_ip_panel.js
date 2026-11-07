/* 数据看板「来源 IP」：按客户端地址汇总，以及「这个号被哪些客户端用过」。

   Why this suite exists: the gateway now records client_ip on every usage row
   (tests/_test_client_ip_logging.py) and the request log shows it per request
   (tests/_test_recent_client_ip.js). This panel is the aggregate view: one row
   per address with its request/token totals, and the reverse index (per
   account, which addresses it was used from) that answers "is one person
   cycling through many accounts" or "is one account shared".

   The assertions pin the parts a regression would break silently:
     - the address bucket renders with its counts,
     - rows written before the field existed are labelled, not silently counted
       as a real address,
     - the reverse index names both addresses of a shared account,
     - an empty payload says so instead of leaving a blank table.

   Run with Node.
*/
'use strict';

const assert = require('assert');
const {dashboardScript} = require('./_dashboard_source.js');

const script = dashboardScript();
const dom = require('./_dom_stub.js');

const PAYLOAD = {
  ips: [
    {ip: '203.0.113.7', requests: 12, total_tokens: 4200, prompt_tokens: 3000,
     completion_tokens: 800, reasoning_tokens: 400, cached_tokens: 1000,
     first_at: 1762400000, last_at: 1762480000,
     models: [['deepseek-v4.1-flash', 9], ['hy3', 3]],
     accounts: [['uid-1', 9], ['uid-2', 3]]},
    {ip: '(未知)', requests: 40, total_tokens: 900, prompt_tokens: 600,
     completion_tokens: 300, reasoning_tokens: 0, cached_tokens: 0,
     first_at: 1761000000, last_at: 1762000000, models: [['hy3', 40]],
     accounts: [['uid-1', 40]]},
  ],
  accounts: [
    {account: 'uid-1', requests: 49, last_at: 1762480000,
     ips: [['203.0.113.7', 9], ['(未知)', 40]]},
    {account: 'uid-2', requests: 3, last_at: 1762470000, ips: [['203.0.113.7', 3]]},
  ],
};

let served = PAYLOAD;
const domWindow = dom.installDom({
  fetch: url => {
    const payload = String(url).includes('/usage/by-client-ip')
      ? served
      : {rows: [], total: 0, accounts: [], slots: [], data: [], results: [],
         byAccount: [], ips: [], models: []};
    return Promise.resolve({
      status: 200, ok: true,
      json: () => Promise.resolve(payload),
      text: () => Promise.resolve(JSON.stringify(payload)),
    });
  },
});
domWindow.ACCOUNTS = [];
global.ACCOUNTS = domWindow.ACCOUNTS;

const api = new Function(script + '\n return window.wbaClientIps;')();

let checks = 0;
function check(label, cond, extra) {
  checks += 1;
  assert.ok(cond, label + (extra ? '  [' + extra + ']' : ''));
}

function bodyRows(html) {
  return [...html.matchAll(/<tr>([\s\S]*?)<\/tr>/g)].map(m => m[1]);
}

(async () => {
  await api.load();

  const ipHtml = dom.byId('clientIpBody').innerHTML;
  const ipRows = bodyRows(ipHtml);
  check('每个来源地址一行', ipRows.length === 2, 'rows=' + ipRows.length);
  check('地址按原样渲染', ipHtml.includes('203.0.113.7'), ipHtml.slice(0, 200));
  check('请求数出现在该行', /12/.test(ipRows[0] || ''), ipRows[0]);
  check('token 总量出现在该行', /4[,.]?200/.test(ipRows[0] || ''), ipRows[0]);
  check('同一 IP 用过的账号以徽章列出', ipHtml.includes('uid-1') && ipHtml.includes('×9'), ipHtml.slice(0, 400));
  check('IP 字段上线前的行被标注，而不是当成真实地址',
        ipHtml.includes('IP 上线前'), ipHtml.slice(0, 400));
  check('最近活动按相对时间渲染', /前/.test(ipRows[0] || ''), ipRows[0]);

  const acctHtml = dom.byId('accountIpBody').innerHTML;
  check('账号方向的两个账号都渲染', acctHtml.includes('uid-1') && acctHtml.includes('uid-2'), acctHtml.slice(0, 200));
  check('一个账号的两个来源地址都在',
        /uid-1[\s\S]*203\.0\.113\.7[\s\S]*\(未知\)/.test(acctHtml)
        || /uid-1[\s\S]*\(未知\)[\s\S]*203\.0\.113\.7/.test(acctHtml),
        acctHtml.slice(0, 500));

  // 空载荷：说「暂无数据」，而不是留一张空表让人以为挂了。
  served = {ips: [], accounts: []};
  await api.load();
  const emptyHtml = dom.byId('clientIpBody').innerHTML;
  check('空载荷给出空状态', emptyHtml.includes('暂无数据'), emptyHtml);

  console.log('analytics client-ip panel assertions passed (' + checks + ' checks)');
})().catch(err => {
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
});
