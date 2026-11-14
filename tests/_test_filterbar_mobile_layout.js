/* 窄屏筛选条：搜索框独占一行、下拉每行两个，不改成纵向堆叠。
 *
 * 为什么值得一个套件：
 * 上游 v2.1.2 给 `.acct-filterbar` / `.recent-filterbar` 加了一条
 * `@media (max-width:700px){flex-direction:column}`。筛选条从横排变成纵排后，
 * `.console-search` 的 `flex:1 1 220px` 里的 220px 从「宽度基准」变成了
 * 「高度基准」——搜索框在手机上被撑成 314×220 的空白块，整条筛选条 461px 高，
 * 账号列表被顶到屏幕外。这不是静态读 CSS 能看出来的：`flex-basis` 落在哪个轴上
 * 取决于 `flex-direction`，两条规则分开看都合法。
 *
 * 这里钉住三件事：
 *   1. 700px 断点内不允许出现 `flex-direction:column`（否则 basis 落到高度）；
 *   2. 搜索框在该断点内 `flex-basis` 必须是宽度语义（100%）且显式 height:auto；
 *   3. 桌面端（>700px）不受影响，筛选条仍是横排。
 *
 * Run with Node: node tests/_test_filterbar_mobile_layout.js
 */
'use strict';
const assert = require('assert');
const {dashboardHtml} = require('./_dashboard_source.js');

const html = dashboardHtml();

let checks = 0;
function check(label, ok, detail) {
  checks++;
  assert.ok(ok, label + (detail === undefined ? '' : '  -> ' + detail));
}

/* 抽出 @media (max-width:700px) 那一段（含嵌套大括号），单独断言。 */
function blockAfter(marker) {
  const start = html.indexOf(marker);
  if (start < 0) return '';
  let depth = 0;
  let i = html.indexOf('{', start);
  const from = i;
  for (; i < html.length; i++) {
    if (html[i] === '{') depth++;
    else if (html[i] === '}') {
      depth--;
      if (depth === 0) return html.slice(from, i + 1);
    }
  }
  return html.slice(from);
}

const narrow = blockAfter('@media (max-width:700px){\n  /* 窄屏沿用面板原有口径');

check('存在窄屏筛选条断点', narrow.length > 0, 'missing the max-width:700px filterbar block');
check('窄屏不把筛选条改成纵向堆叠', !/flex-direction:\s*column/.test(narrow),
  'flex-direction:column makes the search box flex-basis land on height');
check('窄屏搜索框 basis 是宽度语义', /\.console-search\{[^}]*flex:\s*1\s+1\s+100%/.test(narrow),
  'search box must take a full row via flex-basis:100%');
check('窄屏搜索框显式 height:auto', /\.console-search\{[^}]*height:\s*auto/.test(narrow),
  'without height:auto a stale basis can still stretch the box');
check('窄屏下拉按行分配宽度', /select\{[^}]*flex:\s*1\s+1\s+40%/.test(narrow),
  'selects should share a row two-up');
check('窄屏下拉有最小宽度兜底', /select\{[^}]*min-width:\s*120px/.test(narrow),
  'selects need a min-width so labels stay readable');

/* 桌面端不受影响：>700px 的基线仍是横排。 */
const baseline = html.match(/:is\(\.acct-filterbar,\s*\.recent-filterbar\)\{([^}]*)\}/);
check('筛选条基线存在', !!baseline, 'missing shared filterbar baseline');
check('筛选条基线是横排', /display:\s*flex/.test(baseline[1]) && !/flex-direction:\s*column/.test(baseline[1]),
  'the baseline bar must stay a horizontal flex row');

console.log('ok - filterbar mobile layout (' + checks + ' checks)');
