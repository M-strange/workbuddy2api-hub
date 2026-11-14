/* 手机端抽屉的遮罩必须真的显示，否则点右侧内容收不起抽屉。
 *
 * 为什么值得一个套件：
 * 文件上方有一条给「旧 / 页面」藏壳子的规则
 *
 *   #nextSidebar, #nextTopbar, #nextBottomNav, #nextMoreSheet,
 *   #nextSidebarBackdrop{display:none}
 *
 * 它是 ID 选择器（特异度 1,0,0）。窄屏 media query 里原先写的是
 *
 *   html[data-ui="next"] .next-sidebar-backdrop{display:block; ...}
 *
 * 类型 + 属性 + 类（0,2,1），永远压不过上面的 ID 规则。于是遮罩的
 * `display` 恒为 `none`：尺寸 0×0，`onclick="nextOpenSidebar(false)"` 收不到
 * 任何点击，点击直接穿透到下面的页面——抽屉展开后点右侧内容没反应。
 *
 * 这类问题静态读 CSS 很容易漏：两条规则分别看都合法，只有把特异度算一遍才
 * 知道哪条生效。这里钉住「必须用 ID 选择器」，防止有人为了统一风格把它改回类
 * 选择器。
 *
 * Run with Node: node tests/_test_sidebar_backdrop.js
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

/* 抽出 @media (max-width: 860px) 里「包含遮罩规则」的那一段。
   文件里有三处同名断点（经典布局、next 布局的其它区块），按字符串第一次出现
   取会拿到不相干的那块，所以这里按大括号配对逐块扫描，挑含有遮罩的那块。 */
function narrowBlockWith(fragment) {
  const marker = '@media (max-width: 860px){';
  let from = 0;
  while (true) {
    const start = html.indexOf(marker, from);
    if (start < 0) return '';
    let depth = 0;
    let i = html.indexOf('{', start);
    const bodyFrom = i;
    for (; i < html.length; i++) {
      if (html[i] === '{') depth++;
      else if (html[i] === '}') {
        depth--;
        if (depth === 0) break;
      }
    }
    const block = html.slice(bodyFrom, i + 1);
    if (block.indexOf(fragment) >= 0) return block;
    from = i + 1;
  }
}

/* 1. 遮罩元素本身带着 id 与 class。 */
check('遮罩元素存在且带 id',
  /<div id="nextSidebarBackdrop"/.test(html));
check('遮罩元素点击时收起抽屉',
  /id="nextSidebarBackdrop"[^>]*onclick="nextOpenSidebar\(false\)"/.test(html));

/* 2. 上方那条藏壳子的 ID 规则还在（修复的前提，不是要删它）。 */
const hideRule = html.match(/#nextSidebar,\s*#nextTopbar[^{]*\{display:none\}/);
check('旧页面的藏壳子规则仍在', !!hideRule,
  'the shell-hiding rule is what makes a class selector lose');

/* 3. 窄屏里放开遮罩必须用 ID 选择器。 */
const narrow = narrowBlockWith('#nextSidebarBackdrop');
check('存在窄屏抽屉断点', narrow.length > 0, 'missing the max-width:860px block');
check('窄屏用 ID 选择器放开遮罩',
  /html\[data-ui="next"\]\s+#nextSidebarBackdrop\s*\{[^}]*display:\s*block/.test(narrow),
  'a class selector loses to the ID rule above; the backdrop stays 0x0');
check('窄屏不再用类选择器放开遮罩',
  !/html\[data-ui="next"\]\s+\.next-sidebar-backdrop\s*\{[^}]*display:\s*block/.test(narrow),
  'the class-selector form cannot win against the ID rule');
check('展开时遮罩接收点击',
  /body\.next-sidebar-open\s+#nextSidebarBackdrop\{[^}]*pointer-events:\s*auto/.test(narrow),
  'without pointer-events:auto the backdrop still lets clicks through');
check('收起状态不拦截点击',
  /#nextSidebarBackdrop\s*\{[^}]*pointer-events:\s*none/.test(narrow),
  'a closed drawer must not swallow clicks on the page');

/* 4. 展开/收起由 body 类驱动，两条规则必须挂在同一个类上。 */
check('展开态由 next-sidebar-open 驱动',
  /body\.next-sidebar-open\s+#nextSidebar\b/.test(narrow),
  'the drawer and the backdrop must open on the same body class');
check('抽屉与遮罩共用同一个展开类',
  (narrow.match(/body\.next-sidebar-open/g) || []).length >= 2,
  'drawer and backdrop must both key off next-sidebar-open');

/* 5. 桌面端不受影响：遮罩在断点外保持隐藏。 */
check('断点外遮罩仍是隐藏的',
  /html\[data-ui="next"\]\s+\.next-sidebar-backdrop\{display:none\}/.test(html),
  'on desktop the sidebar is always visible, so the backdrop must stay hidden');

console.log('ok - sidebar backdrop (' + checks + ' checks)');
