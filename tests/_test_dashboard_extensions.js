/* 三个新增能力（去水印 / 文本嵌入 / MCP）在面板上的接线契约。
 *
 * 这三块都是「后端先有、界面后补」的功能，最容易出的问题是两半脱节：
 * 端点加了但设置页没有控件（开关只能手改 json），或者控件在、保存时压根没把
 * 这个键发出去（前端回「保存成功」而什么都没落盘）。这个套件盯的就是那条缝：
 *
 *   1. 结构：三个区块和每个控件 id 真的在 pageMedia 里；
 *   2. 接线：loadSettings 会 apply，保存会 POST /settings/save，试用会打接口；
 *   3. 行为：把函数体抠出来喂假 DOM 跑一遍，看它到底写了什么、发了什么。
 *
 * 第 3 类是重点 —— 光有 id 不代表函数真的会用它。
 */
'use strict';
const assert = require('assert');
const {dashboardHtml, dashboardScript} = require('./_dashboard_source.js');
const html = dashboardHtml();
const script = dashboardScript();

// ---------------------------------------------------------------- 工具

// 抠出一个顶层 function 的源码。这些函数体内部所有 `}` 都带缩进，所以
// 以行首 `}` 收尾的那个就是函数自己的花括号。
function grab(name) {
  const re = new RegExp('(?:async\\s+)?function\\s+' + name + '\\s*\\([^)]*\\)\\s*\\{[\\s\\S]*?\\n\\}');
  const match = script.match(re);
  assert.ok(match, 'dashboard 里找不到函数 ' + name);
  return match[0];
}

// 假 DOM：只认 getElementById，节点同时带 input 与 text 的字段。
function fakeDoc(seed) {
  const nodes = {};
  Object.keys(seed || {}).forEach(id => {
    nodes[id] = Object.assign(
      {id: id, value: '', checked: false, textContent: '', innerHTML: '', style: {}},
      seed[id]);
  });
  return {nodes: nodes, getElementById: id => nodes[id] || null};
}

// 在受控作用域里跑一段源码，返回它的导出。
function run(body, scope, exportName) {
  const names = Object.keys(scope || {});
  const values = names.map(n => scope[n]);
  const tail = exportName ? '\nreturn ' + exportName + ';' : '';
  // eslint-disable-next-line no-new-func
  return new Function(names.join(','), body + tail)(...values);
}

// ---------------------------------------------------------------- 1. 结构

const mediaStart = html.indexOf('id="pageMedia"');
const mediaEnd = html.indexOf('id="pageAnalytics"');
assert.ok(mediaStart > 0 && mediaEnd > mediaStart, 'pageMedia 段落应能被定位');
const media = html.slice(mediaStart, mediaEnd);

['图片去水印', '文本嵌入', 'MCP 服务'].forEach(label => {
  assert.ok(media.includes(label), label + ' 应落在 pageMedia 里（而不是别处）');
});

[
  'setWatermarkState', 'setWatermarkEnabled', 'setWatermarkMinBlank',
  'setWatermarkWhiteLum', 'setWatermarkMaxPixels',
  'setEmbeddingsState', 'setEmbeddingsEnabled', 'setEmbeddingsModel',
  'setEmbeddingsMaxInputs',
  'mcpState', 'mcpToolList', 'mcpSnippet',
  'wmFile', 'wmMinBlank', 'wmKeepBlank', 'wmResult'
].forEach(id => {
  assert.ok(media.includes('id="' + id + '"'), '控件 ' + id + ' 应在 pageMedia 里');
});

assert.ok(/onclick="saveWatermarkConfig\(this\)"/.test(media), '去水印应有保存按钮');
assert.ok(/onclick="saveEmbeddingsConfig\(this\)"/.test(media), '嵌入应有保存按钮');
assert.ok(/onclick="copyMcpConfig\(\)"/.test(media), 'MCP 应有复制配置按钮');
assert.ok(/onclick="runWatermarkStrip\(this\)"/.test(media), '去水印应有就地试用按钮');
assert.ok(/accept="image\/png/.test(media), '去水印文件选择应只收 PNG');

// MCP 没有开关：它是给外部客户端连的端点，面板上出现复选框就说明设计跑偏了。
assert.ok(!/setMcpEnabled/.test(html), 'MCP 不应有开关控件');
assert.ok(!/saveMcpConfig/.test(script), 'MCP 不应有保存函数');

// ---------------------------------------------------------------- 2. 接线

assert.ok(script.includes('applyWatermarkSettings(data.watermark)'),
  'loadSettings 应把 watermark 配置交给 applyWatermarkSettings');
assert.ok(script.includes('applyEmbeddingsSettings(data.embeddings)'),
  'loadSettings 应把 embeddings 配置交给 applyEmbeddingsSettings');

const saveCalls = (script.match(/postJSON\('\/settings\/save', payload\)/g) || []).length;
assert.ok(saveCalls >= 3,
  '媒体 / 去水印 / 嵌入三组保存都应走 /settings/save，实际 ' + saveCalls);

assert.ok(script.includes("'/v1/images/strip-watermark'"), '试用区应打去水印接口');
assert.ok(!/postJSON\('\/v1\/embeddings'/.test(script),
  '嵌入不该在面板里带试用框——它是给程序调的，不是给人点的');
assert.ok(grab('loadMediaPage').includes('renderMcpTools()'),
  '进入媒体页应渲染 MCP 工具表');

// ---------------------------------------------------------------- 3. 行为：去水印配置

const escSource = (script.match(/const esc = [\s\S]*?\n/) || [''])[0];
assert.ok(escSource, 'dashboard 里应能取到 esc 转义函数');

// 配置 -> DOM
{
  const doc = fakeDoc({
    setWatermarkEnabled: {}, setWatermarkMinBlank: {}, setWatermarkWhiteLum: {},
    setWatermarkMaxPixels: {}, setWatermarkState: {}
  });
  const apply = run(grab('applyWatermarkSettings'), {document: doc}, 'applyWatermarkSettings');
  apply({enabled: true, min_blank_px: 120, white_lum: 250, max_pixels: 5000000});
  assert.strictEqual(doc.nodes.setWatermarkEnabled.checked, true, '开关应被勾上');
  assert.strictEqual(doc.nodes.setWatermarkMinBlank.value, 120);
  assert.strictEqual(doc.nodes.setWatermarkWhiteLum.value, 250);
  assert.strictEqual(doc.nodes.setWatermarkMaxPixels.value, 5000000);
  assert.strictEqual(doc.nodes.setWatermarkState.textContent, '(已开启)');
  assert.strictEqual(doc.nodes.setWatermarkState.style.color, 'var(--accent2)');

  apply({enabled: false});
  assert.strictEqual(doc.nodes.setWatermarkEnabled.checked, false, '关掉时应取消勾选');
  assert.strictEqual(doc.nodes.setWatermarkState.textContent, '(已关闭)');
  assert.strictEqual(doc.nodes.setWatermarkState.style.color, 'var(--dim)');

  // 后端旧一点、压根没有 watermark 字段时也不能炸。
  apply(undefined);
  assert.strictEqual(doc.nodes.setWatermarkState.textContent, '(已关闭)');
}

// DOM -> 请求体。postJSON 在第一个 await 之前就被调用，所以这里同步断言即可。
{
  const doc = fakeDoc({
    setWatermarkEnabled: {checked: true}, setWatermarkMinBlank: {value: '120'},
    setWatermarkWhiteLum: {value: '250.5'}, setWatermarkMaxPixels: {value: '5000000'},
    setWatermarkState: {}
  });
  const seen = [];
  const save = run(grab('saveWatermarkConfig'), {
    document: doc,
    postJSON: (url, body) => { seen.push([url, body]); return Promise.resolve({}); },
    toast: () => {},
    loadSettings: () => {}
  }, 'saveWatermarkConfig');
  save({});
  assert.strictEqual(seen.length, 1, '保存应只发一次');
  assert.strictEqual(seen[0][0], '/settings/save');
  assert.deepStrictEqual(seen[0][1].watermark, {
    enabled: true, min_blank_px: 120, white_lum: 250.5, max_pixels: 5000000
  }, '去水印保存的键必须与 wb_settings.validate_watermark_patch 的白名单一致');
  assert.strictEqual(seen[0][1].media, undefined, '不应顺手把媒体配置一起发出去');
  assert.strictEqual(seen[0][1].embeddings, undefined, '不应顺手把嵌入配置一起发出去');
}

// ---------------------------------------------------------------- 4. 行为：嵌入配置

{
  const doc = fakeDoc({
    setEmbeddingsEnabled: {}, setEmbeddingsModel: {}, setEmbeddingsMaxInputs: {},
    setEmbeddingsState: {}
  });
  const apply = run(grab('applyEmbeddingsSettings'), {document: doc},
    'applyEmbeddingsSettings');
  apply({enabled: true, model: 'bge-m3', max_inputs: 64});
  assert.strictEqual(doc.nodes.setEmbeddingsEnabled.checked, true);
  assert.strictEqual(doc.nodes.setEmbeddingsModel.value, 'bge-m3');
  assert.strictEqual(doc.nodes.setEmbeddingsMaxInputs.value, 64);
  assert.strictEqual(doc.nodes.setEmbeddingsState.textContent, '(已开启)');
  assert.strictEqual(doc.nodes.setEmbeddingsState.style.color, 'var(--accent2)');
}

{
  const doc = fakeDoc({
    setEmbeddingsEnabled: {checked: true}, setEmbeddingsModel: {value: '   '},
    setEmbeddingsMaxInputs: {value: '64'}, setEmbeddingsState: {}
  });
  const seen = [];
  const save = run(grab('saveEmbeddingsConfig'), {
    document: doc,
    postJSON: (url, body) => { seen.push([url, body]); return Promise.resolve({}); },
    toast: () => {},
    loadSettings: () => {}
  }, 'saveEmbeddingsConfig');
  save({});
  assert.deepStrictEqual(seen[0][1].embeddings, {
    enabled: true, model: 'bge-m3', max_inputs: 64
  }, '模型留空应回落到 bge-m3，而不是把空串发给上游');
}

// ---------------------------------------------------------------- 5. 行为：去水印结果渲染

{
  const doc = fakeDoc({wmResult: {}});
  const render = run(escSource + grab('renderWatermarkResult'), {document: doc},
    'renderWatermarkResult');
  render({
    width: 1024, height: 260, out_width: 1024, out_height: 140,
    blank_px: 120, blank_ratio: 0.4615, blank_lum: 255, safe: true,
    data_url: 'data:image/png;base64,AAAA'
  }, 'data:image/png;base64,BBBB');
  const out = doc.nodes.wmResult.innerHTML;
  assert.ok(out.includes('1024 × 260'), '应显示原图尺寸');
  assert.ok(out.includes('1024 × 140'), '应显示输出尺寸');
  assert.ok(out.includes('120 px'), '应显示裁掉的像素');
  assert.ok(out.includes('46.2%'), '留白占比应换算成百分比');
  assert.ok(out.includes('够高够白'), 'safe 为真时应说正常裁');
  assert.ok(out.includes('data:image/png;base64,AAAA'), '应带上输出图');
  assert.ok(out.includes('download="stripped.png"'), '应给出下载链接');

  render({width: 10, height: 10, out_width: 10, out_height: 4, blank_px: 6,
          blank_ratio: 0.6, blank_lum: 210, safe: false, data_url: ''}, '');
  assert.ok(doc.nodes.wmResult.innerHTML.includes('偏窄或偏灰'), 'safe 为假时应说明是强裁');
}

// ---------------------------------------------------------------- 6. 行为：MCP 说明

const mcpDocSource = (script.match(/const MCP_TOOLS_DOC = \[[\s\S]*?\n\];/) || [''])[0];
assert.ok(mcpDocSource, '应能取到 MCP 工具清单常量');

{
  const url = run(escSource + mcpDocSource + grab('mcpEndpointUrl'),
    {location: {origin: 'http://127.0.0.1:8788'}}, 'mcpEndpointUrl');
  assert.strictEqual(url(), 'http://127.0.0.1:8788/mcp', '端点应跟着当前 origin 走');
}

{
  // 没有 location（被嵌进别的容器）时要回落到默认地址，而不是抛错。
  const url = run(escSource + mcpDocSource + grab('mcpEndpointUrl'),
    {location: undefined}, 'mcpEndpointUrl');
  assert.strictEqual(url(), 'http://127.0.0.1:8788/mcp');
}

{
  const text = run(escSource + mcpDocSource + grab('mcpEndpointUrl') + grab('mcpConfigText'),
    {location: {origin: 'http://box:9000'}}, 'mcpConfigText')();
  const cfg = JSON.parse(text);
  assert.ok(cfg.mcpServers && cfg.mcpServers.workbuddy2api, '配置片段应有 mcpServers 段');
  assert.strictEqual(cfg.mcpServers.workbuddy2api.url, 'http://box:9000/mcp');
  assert.strictEqual(cfg.mcpServers.workbuddy2api.type, 'http');
  assert.ok(/^Bearer /.test(cfg.mcpServers.workbuddy2api.headers.Authorization),
    '应给出 Authorization: Bearer 头');
}

{
  const doc = fakeDoc({mcpToolList: {}, mcpSnippet: {}, mcpState: {}});
  const render = run(
    escSource + mcpDocSource + grab('mcpEndpointUrl') + grab('mcpConfigText')
      + grab('renderMcpTools'),
    {document: doc, location: {origin: 'http://127.0.0.1:8788'}}, 'renderMcpTools');
  render();
  const table = doc.nodes.mcpToolList.innerHTML;
  ['list_generation_models', 'generate_image', 'edit_image', 'generate_video',
   'get_video_task', 'strip_watermark'].forEach(name => {
    assert.ok(table.includes(name), '工具表应列出 ' + name);
  });
  assert.ok(table.includes('bge-m3') === false, 'MCP 工具表不该混进嵌入模型');
  assert.ok(doc.nodes.mcpSnippet.textContent.includes('mcpServers'),
    '代码块应填入可复制的客户端配置');
  assert.ok(doc.nodes.mcpState.textContent.includes('6 个工具'),
    '状态位应报工具数量，实际：' + doc.nodes.mcpState.textContent);
  assert.ok(doc.nodes.mcpState.textContent.includes('http://127.0.0.1:8788/mcp'),
    '状态位应带上端点地址');
}

console.log('_test_dashboard_extensions.js: all assertions passed');
