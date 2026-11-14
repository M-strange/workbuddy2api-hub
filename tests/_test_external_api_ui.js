/* Static contract for the API 接入 dashboard page. */

'use strict';

const assert = require('assert');
const {dashboardHtml, dashboardScript} = require('./_dashboard_source.js');

const html = dashboardHtml();
const script = dashboardScript();
let checks = 0;
function check(ok, message){ assert.ok(ok, message); checks += 1; }

try { new Function(script); }
catch (error) { throw new Error('dashboard inline script must parse: ' + error.message); }
checks += 1;

check(/id="btnNavApi"[^>]*onclick="switchMainTab\('api'\)"/.test(html),
  '侧栏应提供独立的 API 接入入口');
const nextNav = html.slice(html.indexOf('<nav class="next-nav"'), html.indexOf('</nav>', html.indexOf('<nav class="next-nav"')));
const nextNavTabs = [...nextNav.matchAll(/data-next-tab="([^"]+)"/g)].map(m => m[1]);
check(JSON.stringify(nextNavTabs) === JSON.stringify([
  'overview', 'gateway', 'accounts', 'api', 'analytics', 'tasks', 'agents', 'media', 'settings', 'logs'
]), '新导航顺序应为总览、网关、账号、接口、用量、自动化、智能体、媒体、设置、日志');
check(/data-next-tab="api"[\s\S]*?<span>接口<\/span>/.test(nextNav),
  '新导航应使用两字菜单名「接口」');
const moreSheet = html.slice(html.indexOf('<div id="nextMoreSheet"'), html.indexOf('<div class="modal-mask"', html.indexOf('<div id="nextMoreSheet"')));
check(/data-next-tab="api"[\s\S]*?<span>接口<\/span>/.test(moreSheet),
  '移动端更多菜单应使用两字菜单名「接口」');
check(nextNavTabs.indexOf('api') === 3, '新导航中接口应紧跟账号');
check(/id="btnNavApi"[^>]*>[\s\S]*?接口/.test(html),
  '兼容导航应使用两字菜单名「接口」');
check(/id="pageApi" class="main-page/.test(html),
  '应有独立的 API 接入页面容器');
check(html.includes('id="apiKeyTab"') && html.includes('id="apiDocsTab"'),
  'API 接入页应包含 API Key 和接口文档两个页签');

const pageStart = html.indexOf('<div id="pageApi"');
const pageEnd = html.indexOf('<div id="pageAgents"', pageStart);
check(pageStart >= 0 && pageEnd > pageStart, 'API 接入页面范围可定位');
const page = html.slice(pageStart, pageEnd);
check(page.includes('id="externalApiKeys"'), 'API Key 页应有 Key 列表容器');
check(page.includes('id="externalApiRecords"'), 'API Key 页应有调用记录容器');
check(!page.includes('API 功能') && !page.includes('调用流程'),
  'API Key 页不应重复展示已移除的 API 功能/调用流程模块');
check(page.includes('id="apiDocList"') && page.includes('id="apiDocDetail"'),
  '接口文档页应有列表与详情双栏');

for(const endpoint of [
  '/v1/accounts/authorize',
  '/v1/accounts/authorize/{request_id}',
  '/v1/accounts?realm=intl',
]) check(page.includes(endpoint), '文档页缺少接口：' + endpoint);

for(const route of [
  "getJSON('/api/external/keys')",
  "postJSON('/api/external/keys'",
  "getJSON('/api/external/call-records",
]) check(script.includes(route), '前端缺少接口调用：' + route);

check(/const\s+EXTERNAL_API_DOCS\s*=/.test(script), '缺少外部 API 文档合同定义');
check(/function\s+renderExternalApiDoc\(id\)/.test(script),
  '缺少动态接口文档渲染函数');
check(/function\s+selectExternalApiDoc\(id/.test(script),
  '缺少接口选择函数');
check(/request_id[\s\S]{0,300}auth_url/.test(script),
  '授权接口示例应包含完整 request_id 与 auth_url 参数/响应');
check(/method:\s*'POST'[\s\S]{0,220}headers:[\s\S]{0,220}body:\s*\{realm:\s*'intl'\}/.test(script),
  '授权请求实例应包含方法、路径、鉴权、请求头和完整请求体');
check(/method:\s*'GET'[\s\S]{0,220}query:\s*\{realm:\s*'intl'\}/.test(script),
  '账号列表请求实例应包含方法、路径、鉴权和完整查询参数');
check(/curl[\s\S]{0,300}Authorization: Bearer/.test(script),
  '文档应动态提供带 Bearer 鉴权的完整 cURL 示例');
check(/function\s+loadExternalApiPage\(\)/.test(script),
  '切换 API 接入页时应有独立加载函数');
check(/EXTERNAL_API_RECORD_PAGE_SIZE\s*=\s*20/.test(script),
  '调用记录默认每页 20 条');
check(/external\/call-records\?page=/.test(script) && /page_size=/.test(script),
  '调用记录请求应带分页参数');
check(/externalApiRecordPagination/.test(script) && /function\s+gotoExternalApiRecordPage\(/.test(script),
  '调用记录应提供分页容器与翻页函数');
check(/externalApiRecordRequestSeq/.test(script) &&
      /requestSeq\s*!==\s*externalApiRecordRequestSeq/.test(script),
  '调用记录应忽略乱序返回的旧分页响应');
check(/\['api',\s*btnApi,\s*pageApi\]/.test(script),
  '主页面切换数组应注册 API 接入页');

for(const [zh, en] of [
  ['API 接入', 'API access'],
  ['接口文档', 'API docs'],
  ['调用记录', 'Call records'],
  ['创建账号授权请求', 'Create an account authorization request'],
  ['查询账号授权状态', 'Query authorization status'],
  ['读取账号列表', 'Read the account list'],
  ['密钥', 'Key'],
  ['权限', 'Permissions'],
  ['参数', 'Parameter'],
  ['类型', 'Type'],
  ['必填', 'Required'],
  ['耗时', 'Duration'],
  ['是', 'Yes'],
  ['调用方', 'Caller'],
  ['需要 account:auth', 'Requires account:auth'],
  ['需要 account:read', 'Requires account:read'],
  ['管理外部 API Key、调用记录和账号接口文档。', 'Manage external API keys, call records, and account API documentation.'],
  ['cn / intl；决定本次授权使用的版本。', 'cn or intl; selects the account version for this authorization.'],
  ['创建授权请求时返回的请求标识。', 'Request identifier returned when the authorization request was created.'],
  ['cn / intl；筛选账号版本。', 'cn or intl; filters the account version.'],
]) check(html.includes("'" + zh + "': '" + en + "'"), '英文词典缺少：' + zh);

check(html.indexOf('id="btnNavAccounts"') < html.indexOf('id="btnNavApi"') &&
      html.indexOf('id="btnNavApi"') < html.indexOf('id="btnNavModels"'),
  '兼容导航中接口应紧跟账号并位于模型入口之前');

console.log('OK ' + checks + ' checks');
