# WorkBuddy2API-Hub — 国际版、国内版多账号网关中枢

> [!NOTE]
> **本仓库是社区维护分支**：在官方 [ardeyouxipianyi/workbuddy2api-hub](https://github.com/ardeyouxipianyi/workbuddy2api-hub) v2.0.3 的基础上合并了本分支的增强（请求来源 IP 全链路与聚合视图、账号池排队与自动探活、上游超时收紧等）。官方已于 2026-11-08 恢复维护，上游修复优先从官方同步；本分支的版本号从 2.1.0 起独立递增，避免与官方 2.0.x 的 tag 撞名。

> [!IMPORTANT]
> **官方群聊**：[https://t.me/wb2apihub](https://t.me/wb2apihub)
>
> **凭证安全**：本项目是本地部署网关，运行时需要在本地读取用户自行导入的账号凭证，才能调用官方接口；凭证保存在用户自己的 `accounts/` 目录。项目不会把凭证上传到本项目的第三方服务器，也没有隐藏的凭证收集或上传逻辑。请立即关闭公网暴露，联系官方吊销全部 OAuth / 设备授权，确认旧 token 返回 `401` 后再重新授权。

> [!WARNING]
> **WorkBuddy 上游正在收紧对非官方客户端的识别与拦截。**
>
> - **封禁**：2026-10-23 下午起，非官方客户端的识别与拦截明显收紧。
> - **维护者**：近期工作压力增大，无法保证及时更新与响应。
> - **可用性**：上游可能随时进一步收紧，导致本项目不可用。
> - **账号风险**：使用非官方客户端造成的风控、限流或封禁，由使用者自行承担。
>
> **Upstream enforcement** tightened detection and blocking of unofficial clients from the afternoon of 2026-10-23. The maintainer is under increased workload and cannot guarantee timely updates or replies. The upstream may tighten further at any time; rate limits, account restrictions or bans caused by using an unofficial client are the user's responsibility.

本项目仅用于协议学习、研究与个人自用。请优先使用官方客户端，不要使用主账号，不要共享账号，也不要用于商业转售。

This project is for protocol research and personal use only. Prefer the official client, do not use your primary account, and do not resell or share access.

<p align="center">
  <a href="https://github.com/M-strange/workbuddy2api-hub/releases"><img src="https://img.shields.io/badge/Release-v2.2.0-2496ED?style=flat-square" alt="Version 2.2.0"></a>
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg?style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/API-OpenAI_Compatible-412991?style=flat-square" alt="OpenAI API">
  <img src="https://img.shields.io/badge/Dual_Realm-Intl_&_CN-0DBD8B?style=flat-square" alt="Dual Realm">
  <img src="https://img.shields.io/badge/License-MIT-green.svg?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Maintenance-Resumed-0DBD8B?style=flat-square" alt="Maintenance resumed">
</p>

## 核心特性

- **标准 API 兼容**：将 WorkBuddy（国际版/国内版）与 CodeArts 封装为标准 OpenAI 格式（Chat Completions / Responses），无缝支持 Codex、Claude Code、NextChat 等各类客户端。
- **开箱即用与多端部署**：便携版免装环境（Windows 自带精简运行时），支持 Docker、NAS（群晖/飞牛）一键部署及 OpenWrt 路由器固件。
- **多账号池与出口隔离**：支持浏览器 OAuth 快速导入、每账号独立出口代理槽绑定、设备指纹隔离、自动故障转移与配额轮转。
- **自动化福利与签到**：内置国内版成长任务、星巴克 / 记者节运营活动、小程序任务、加油站签到与猫猫旅行，支持国际版每日活跃会话与 CodeArts 自动签到；手机 App 对话、公众号关注与公益捐赠等必须真实完成的任务只提示、不伪造。
- **可视化管理看板**：提供 Web 仪表盘，支持实时请求日志、Token/积分透视、多 API Key 权限分发（模型/账号白名单）与额度护栏。
- **一键工作台启动**：`start-workbuddy-all.bat` 先用 `--probe-only` 检查端口上的实例是否健康，未运行才拉起网关并打开 WorkBuddy 工作台，避免重复启动或误连陌生服务。

### 社区 Rust 版本

[YTjungle666/workbuddy2api-hub](https://github.com/YTjungle666/workbuddy2api-hub) 是社区独立维护的 Rust 重写分支。网关后端与启动器均使用 Rust 实现，提供单文件静态二进制，不依赖 Python 运行时；功能以上游 `v2.0.1` 为对齐基线。它不是本仓库的官方发布物，问题反馈与版本更新请前往对应仓库。

> ⚡ **Vibe Coding 产物**：本项目为 100% Vibe Coding 协同产物——人类开发者提出架构与业务意图，AI 助手端到端完成逆向分析、链路调度、WAF 指纹脱敏与界面编写。

> 📌 **提交代码贡献前**：请先查看并**严格遵循**贡献手册 [`CONTRIBUTING.md`](CONTRIBUTING.md)——提交格式、测试门禁与端到端冒烟要求都在那里（AI / 智能体请特别注意其中的硬性规则节）。

---

## 💖 赞助商

> 想出现在这里？联系 [ardeyouxipianyi@gmail.com](mailto:ardeyouxipianyi@gmail.com)

<table>
<tr>
<td width="180" align="center" valign="middle">
  <a href="https://agentrouter.org/register?aff=unrV"><img src="https://raw.githubusercontent.com/88lin/picx-images-hosting/master/90C5FAD072EA247822CB88BB32512A41.webp" alt="Agent Router" width="150"></a>
</td>
<td valign="middle"><b><a href="https://agentrouter.org/register?aff=unrV">Agent Router</a></b>&nbsp;是免费公益大模型 API 平台，支持 Claude-opus-5.5、GPT-6 Astra、GPT-6.1 Sol、deepseek-v4-flash 等主流模型，国内直连。注册送 ＄175（每日签到得 ＄25，被邀得 ＄50），支持 GitHub / LinuxDo 登录。</td>
</tr>
</table>


---

## 一、快速启动

### 1. 本机运行

- **Windows**：双击 `start-wb-proxy.bat`（静默后台运行 + 独立日志窗口）；如需前台控制台窗口，双击 `start-wb-proxy-visible.bat`。
- **macOS / Linux**：双击 `start-wb-proxy.command` 或在终端执行 `./start-wb-proxy.sh [端口]`（默认 8788，需要 Python 3.9+）。
- **局域网共享模式**：运行 `start-wb-proxy-lan.bat`（Windows）或 `./start-wb-proxy-lan.sh`（macOS/Linux），首次启动将自动生成高强度 API Key 并在控制台打印。
- 启动后访问：
  - **Web 看板**：`http://127.0.0.1:8788/`（默认访问密码 `admin`，首次登录请在设置中修改）
  - **API 地址**：`http://127.0.0.1:8788/v1`

### 2. Docker 部署

预编译多架构镜像发布在 GHCR，无需本地构建：

**方式一：一键脚本（推荐）**

```bash
# 官方源（直连 GitHub 环境）：
curl -fsSL https://raw.githubusercontent.com/ardeyouxipianyi/workbuddy2api-hub/main/quick-deploy.sh | bash

# 国内网络 / NAS 加速：
curl -fsSL https://gh-proxy.com/https://raw.githubusercontent.com/ardeyouxipianyi/workbuddy2api-hub/main/quick-deploy.sh | sudo bash
```

> 公网部署或配合反向代理：在管道前指定 `WB_DEPLOY_MODE=public bash`，并搭配 Nginx / Caddy / Cloudflare Tunnel 配置 TLS。

**方式二：单文件 Docker Compose**

```yaml
services:
  wb-proxy:
    image: ghcr.io/ardeyouxipianyi/workbuddy2api-hub:latest
    container_name: wb-proxy
    restart: unless-stopped
    ports:
      - "8788:8788"
    environment:
      - HOST=0.0.0.0
      - PORT=8788
      - TZ=Asia/Shanghai
    volumes:
      - ./accounts:/app/accounts    # 账号凭据与配置（持久化）
      - ./usage:/app/usage          # 用量流水日志（持久化）
```

更新镜像：`docker compose pull && docker compose up -d`。

Docker 镜像在构建阶段已经编译好当前架构的 Go/uTLS 桥，容器内不需要 Go。
未设置 `WB_TLS_FINGERPRINT` 时默认 `auto`；如需彻底关闭桥，可加
`- WB_TLS_FINGERPRINT=python`，卷中的账号、设置和用量不会因此改变。

### 3. 启动入口：优先用 `-m`

同一份代码、同一个账号池，`python3 wb_proxy.py` 与 `python3 -m wb_proxy` 的常驻内存差 **47-54 MB**
（Windows 11 / aarch64、Python 3.12-3.14 四套环境实测一致，见 #702）。成因仍在排查，
但只要换成 `-m` 就能拿到这段收益——512 MB 的设备上约 10%。

```bash
cd /path/to/workbuddy2api-hub        # 必须先进入 wb_proxy.py 所在目录
python3 -m wb_proxy --port 8788
```

`-m` 把**当前目录**放进 `sys.path`，而脚本方式放的是脚本所在目录，所以务必先 `cd`。
仓库内的资源路径都基于 `__file__` 解析，不受影响。Docker 镜像和 OpenWrt 包已改用 `-m`；
Windows / macOS 的 `start-wb-proxy.*` 启动脚本暂未改动。

### 4. TLS 出站桥（默认 `auto`）

从本版本起，未显式配置 TLS 模式的安装默认使用 `WB_TLS_FINGERPRINT=auto`：
网关会先尝试随包 Go/uTLS 桥；桥二进制缺失、架构不支持、启动失败、桥进程运行中
退出，或当前请求使用自定义 CA / 不兼容代理时，自动回退 Python/OpenSSL。
回退只发生在当前进程内，不会反复拉起失败的桥，也不会改变原来的代理出口和证书
校验。便捷版、Docker 和 OpenWrt 的受支持架构包都自带对应桥，用户不需要安装 Go。

需要强制指定时：

```sh
WB_TLS_FINGERPRINT=python   # 强制 Python/OpenSSL
WB_TLS_FINGERPRINT=node     # 强制桥；桥不可用时报明确错误
```

`node` 模式下不要设置 `WB_TLS_BRIDGE=off`，否则会按显式关闭桥处理而走 Python。
OpenWrt 使用 `uci set workbuddy2api.main.tls_mode='auto'`、`'node'` 或 `'python'`。
实际模式、最近路线和回退原因可在 `/health`、`/settings` 及面板网络设置中查看。
降级到不识别 `auto` 的旧版本前，请临时设置 `WB_TLS_FINGERPRINT=python`。
逐路径头顺序、代理/桥头隔离和未修改项见
[`docs/OUTBOUND-HEADER-AUDIT.md`](docs/OUTBOUND-HEADER-AUDIT.md)。

### 5. CodeArts 原生第三出口

网关内置进程内直连华为云 CodeArts，支持聊天 SSE 协议转换与自动签到，无需单独运行第三方桥接服务：
1. 打开看板 →「设置 → CodeArts 接入」，勾选「启用 CodeArts 出口」并保存；
2. 切换至看板顶部「CodeArts」视图，点击「+ 添加账号 (OAuth)」完成华为云授权；
3. 在「设置 → API Key」中新建 Key 并绑定出口为 `CodeArts`（或全局通用）即可调用。

CodeArts 的模型 ID 按上游目录**精确匹配**：`deepseek-v4.1-flash` 与
`deepseek-v4.1-flash-1017` 是两个独立模型，不会互相别名或静默回退。
`/v1/models?realm=codearts` 返回的是账号当前可用的真实目录 ID；调用时请直接使用
返回的完整 ID。

---

## 二、账号接入与 API Key 权限

### 1. 账号添加与代理出口绑定
- 打开看板 `http://127.0.0.1:8788/`，点击「+ 添加账号 (OAuth)」，在浏览器中完成官方登录授权即可自动入库。
- **独立代理出口槽（Proxy Slot）**：在看板中可按需配置并命名 HTTP/SOCKS5 出口代理（支持账号密码认证），支持将账号与特定代理槽位绑定，账号身份请求与出站调用均自动走该代理。

### 2. 多 API Key 权限管理
- 「设置」页支持创建多个独立 API Key：
  - **出口绑定**：可固定走国际版、国内版或 CodeArts；
  - **模型限制**：支持通配符白名单（如 `deepseek*`, `gpt-6-astra`），违规请求本机直接返回 400；
  - **账号白名单**：可精确限定该 Key 仅允许调度的账号范围；
  - **用量透视**：数据看板按 Key 独立统计调用次数、Token 消耗、缓存命中与积分。

---

## 三、客户端接入配置

- **Base URL**：`http://127.0.0.1:8788/v1`（局域网为 `http://<局域网IP>:8788/v1`）
- **API Key**：看板「设置」中添加并绑定的 Key
- **模型名称**：调用 `/v1/models` 中列出的任意官方对齐模型 ID（如 `deepseek-v4.1-flash`, `gpt-6-astra`, `hy3`）

**Codex CLI / Responses API**

```bash
export OPENAI_BASE_URL="http://127.0.0.1:8788/v1"
export OPENAI_API_KEY="你在看板设置中添加并绑定的API_Key"
```

**Claude Code / Anthropic Messages（实验性）**

网关支持实验性 Messages 协议适配，因长会话缓存命中率差异，默认关闭：
```bash
# 网关端设置 WB_ENABLE_ANTHROPIC_MESSAGES=1 开启后生效：
export ANTHROPIC_BASE_URL="http://127.0.0.1:8788"
export ANTHROPIC_API_KEY="你在看板设置中添加并绑定的API_Key"
```

---

## 四、常用环境变量

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `PORT` | `8788` | 网关监听端口 |
| `API_KEY` | 自动生成 | 初始 API Key（看板配置多 Key 后优先由看板管理） |
| `WB_DEPLOY_MODE` | `lan` | 部署模式：`lan`（0.0.0.0）、`local`（127.0.0.1）、`public` |
| `WB_MAX_PAYLOAD_BYTES` | `16777216` | 单请求体上限（字节，默认 16MB，支持 1–256 MB） |
| `WB_CHAT_SLOT_WAIT` | `30` | 并发槽位的等待秒数：全局对话槽位与 Key 级 `concurrency_limit` 共用这个预算，等到才有名额，超时仍按 429 拒绝 |
| `WB_ENABLE_ANTHROPIC_MESSAGES` | `0` | 是否开启实验性 Anthropic Messages 协议转换 |
| `WB_BACKGROUND_MODEL_TARGET` | 留空 | 后台模型别名改写目标（如 DSH 客户端自动映射） |
| `WB_CA_BUNDLE` | 留空 | 自签根证书路径（供抓包调试或中间代理使用） |
| `WB_CN_CHAT_UPSTREAM` | 官方默认 | 国内版出站代理地址 |
| `WB_IDENTITY_OS` | 宿主系统 | 仅 CLI 身份：覆盖 `x-stainless-os`（如 `Linux` / `Windows`） |
| `WB_IDENTITY_ARCH` | 宿主架构 | 仅 CLI 身份：覆盖 `x-stainless-arch`（如 `x64` / `arm64`） |
| `WB_IDENTITY_NODE_VERSION` | 官方默认 | 仅 CLI 身份：覆盖 `x-stainless-runtime-version` |
| `WB_SANITIZE_LOOSE_BILLING` | `0` | 计费头的宽松兜底：严格解析认不出时，按「像计费头」（含 ≥2 个 `cc_*=` / `cch=` 键值、且不超过 400 字符）整段删除。默认关闭，保持 #853 之后的严格语义；客户端改字段名导致每轮前缀命中率归零时才需要打开 |
| `WB_MSGSTAT_SHARDS` | `0` | 单发 `/v1/messages` 请求收敛到几个账号上（0 = 关闭）。打开后同一 *(key, 模型, system, tools)* 组合的一次性调用固定复用 ≤N 个账号，避免被首条 user 文本打散到整池；上游 prompt 缓存按账号存放，换号即整段重付 |
| `WB_MSGSTAT_DAILY_SALT` | `1` | 上一条的亲和键带当天日期盐，每天各桶重新开一次；`0` 关闭（键跨天不变） |

遇到上游 `400 / 11-128` 时，先按 [`docs/TROUBLESHOOTING-11-128.md`](docs/TROUBLESHOOTING-11-128.md) 收集同一请求的
身份、最小请求和提示词对照结果；不要先轮换账号。

---

## 五、主要 API 端点

| 接口 | 方法 | 端点 | 说明 |
|---|---|---|---|
| 聊天补全 | `POST` | `/v1/chat/completions` | 标准 OpenAI 聊天接口（支持流式 SSE 与思维链回填） |
| 交互式响应 | `POST` | `/v1/responses` | OpenAI Responses 协议接口（Codex 专用） |
| 模型目录 | `GET` | `/v1/models` | 获取当前出口对齐的官方可用模型列表 |
| 生图 | `POST` | `/v1/images/generations` | 文生图 / 图生图（始终可用，按媒体号池自动选出口） |
| 生视频 | `POST` | `/v1/videos` | 异步生视频任务提交（本地并发排队与空闲调度） |
| 视频状态 | `GET` | `/v1/videos/<id>` | 轮询视频生成进度与结果 |
| 产物下载 | `GET` | `/v1/videos/<id>/content` | 下载视频 MP4 产物直链 |
| 健康检查 | `GET` | `/health` | 网关运行状态、可用账号数与就绪模型分布 |

---

## 六、测试验证

```bash
python tests/run_all.py            # 全部套件
python tests/run_all.py realm      # 只跑名字里含 realm 的
```

- 314 个套件：234 个 Python + 80 个 JS；JS 需要 PATH 上有 `node`，缺失时会跳过并提示。
- `tests/_mobile_check.py` 是独立的 Playwright 手机/桌面布局检查器（需自行安装 Playwright），按需手动运行，不在上面的套件集里。
- `tests/_visual_recent.py` 是同一类手动检查器：用合成 fixture 起一份 1480 宽的「请求列表」，验证失败徽章点开的详情弹窗、四个过滤下拉真的把参数发到 `/usage/recent`，并把列表 / 弹窗 / 筛选条截图写到系统临时目录的 `wb-visual-recent/`。
- CI（`.github/workflows/tests.yml`）跑同一条命令：Ubuntu 上 python 3.9 与 3.12（3.9 是本项目声称的最低版本），Windows 上 python 3.12；推送 `v*` tag 时额外断言 **tag == 源码版本**（`-ci` 演练 tag 豁免）。

---

## 七、版本更新记录 (Changelog)

本版更新与完整历史版本请查阅 **[docs/CHANGELOG.md](docs/CHANGELOG.md)**。
### v2.2.0

- **合并上游 v2.0.4 – v2.1.3**：Key 级日 token 限量与并发有界排队、请求列表服务端筛选与失败详情、CodeArts 积分差值结算与并发占位排队、工具 Schema 关键字类型纠偏、运营活动任务自动化（星巴克 / 记者节）、真实技能分享与模板真实场景、WB_MSGSTAT_SHARDS 单发亲和键等。
- **本分支增强全部保留**：来源 IP 全链路与面板「来源 IP」聚合视图、来源 IP 归属地（v2.1.1 的 wb_client_geo.py）、账号池排队等待、池子超半数熔断自动探活、上游超时 45 / 90 秒、listen backlog 1024。
- 全量测试：**314 个套件：234 个 Python + 80 个 JS，`311 passed, 3 failed, 0 skipped`**（3 项均为 v2.1.1 基线已有的历史失败：`_test_breaker_fairness`、`_test_egress_backoff`、`_test_pool_backoff`，与本次合并无关）。

### v2.1.3

- **运营活动与成长任务补全**：新增星巴克协作、记者节福利活动，接入任务读取、`viewed`、事件上报、`claim` 与 `claimed_at` 回读；技能分享改为创建真实分享渠道并确认进度后领奖；模板任务按服务端场景逐组上报四事件。手机 App 对话任务只提示、不伪造。
- **CodeArts 并发占满改为有界排队**（#886 / #887）：单账号并发槽被占满时最多等待 `busy_wait_seconds`（默认 10 秒），名额释放立即唤醒；超时返回可重试的 429，不再误报 502「没有可用的账号」。真正空池 / 全停用 / 全冷却仍提示添加账号。
- **工具 Schema 关键字类型纠偏**（#885）：数字、布尔、字符串约束字段统一纠偏，并拒绝 `NaN / Infinity`，修复上游 code 11129。
- **清理合并遗留的重复顶层定义**（#888），避免后续维护误改到不生效的旧定义。
- **统计时区开关（北京时间）**：设置 →「日志与系统」新增「统计时区」卡片（`settings.json` 键 `stats_tz_beijing`，`/settings/save` 只收 JSON 布尔，默认关闭）。关闭时全部时间按服务器所在时区显示与分桶，与上游一致；勾选后统一按北京时间（固定 UTC+8）计算日志时间戳、请求记录、撞线 / 重置时刻、今日活动、用量日 / 小时分桶、签到日期、额度重置日与导出文件名。落盘仍存 epoch，切换只影响展示与日历日计算，保存后立即生效。实现用固定偏移而不是 `TZ=Asia/Shanghai` + `tzset()`：中国自 1991 年起无夏令时，固定偏移不需要 tzdata，Windows 没有 `tzset`、musl / OpenWrt 镜像常缺 zoneinfo 也能正确工作。 / A statistics-timezone switch (Settings → Logs & system) now offers Beijing time: `stats_tz_beijing` in `settings.json`, a strict JSON boolean on `/settings/save`, off by default. With it off every time is shown and bucketed in the host timezone exactly as before; switched on, log timestamps, request rows, limit-hit and reset moments, today's activity, usage day/hour buckets, check-in dates, quota reset days and export filenames all use a fixed UTC+8. Epochs are still what gets stored, so the switch only changes display and calendar-day maths, and it takes effect on save. The implementation uses a fixed offset rather than `TZ=Asia/Shanghai` + `tzset()`: China has had no DST since 1991, so no tz database is needed, which keeps it correct on Windows (no `tzset`) and on musl / OpenWrt images that ship without zoneinfo.
#### 合并上游 v2.0.1 – v2.0.3

- **可选 Go/uTLS 传输桥**：新增本地 Go/uTLS CONNECT 桥接器，可按目标平台启用 Node/OpenSSL 兼容的 ClientHello（18 个 Cipher、10 个 Extension、无 ALPN），Python 仍负责 HTTP 构造、连接复用与 SSE 读取。默认继续使用 Python/OpenSSL，只有设置 `WB_TLS_FINGERPRINT=node` 才启用；支持自动发现便携包内的 Windows / macOS / Linux amd64、arm64 桥接器，OpenWrt 额外支持 armv7。桥接器仅监听回环地址，使用启动时随机认证密钥，并继续验证上游证书。
- **设备 Token 与桌面 chat 兼容**：账号支持独立 `deviceToken`，也可从设置页配置 `device_token_file` 并在不暴露 token 本体的前提下热重载；优先级为账号 token > settings 字面值 > 文件。新增可选桌面 chat 兼容头（`X-Agent-Runtime`、`baggage` 与会话字段），默认关闭。
- **请求体兼容性增强**：国内版 Kimi 工具 schema 自动内联 `$ref/$defs`；可选最小输出预算（`WB_MIN_OUTPUT_BUDGET=1`）与无可见输出的 length 终止重试；面板与日志继续对设备 token 脱敏。
- **文本号池 / 媒体号池分区**（#841）：账号新增 `poolScope`（`text` / `media`），文本对话只派文本号，图片 / 视频只派媒体号，空媒体池不回落到文本池。老账号默认 `text`，升级后行为不变；面板可按号池筛选、单号切换或勾选批量挪池，`/accounts/set` 与 `/accounts/set-all` 同步支持 `poolScope`。单实例靠字段过滤，双实例可分别设 `WB_POOL_SCOPE=text|media` 做进程级硬隔离；`WB_POOL_SEPARATION=0` 可回退旧的单池行为。文本任务（签到、成长、猫猫、国际每日活跃）只处理文本号，Token 保活仍覆盖全部账号。
- **历史思考镜像 / Upstream reasoning mirror**：模型名以 `kimi`、`glm`、`minimax`、`mimo`、`step` 或 `space-bunny` 开头时，在工具消息合并完成之后，把非空 `reasoning_content` 原样镜像到上游读取的 `reasoning`；不写空白占位，也不注入 DeepSeek 的 `thinking`。`deepseek` 与 `hy` 不在本镜像范围内。Preserve 只保证发往 WorkBuddy 的字段，不宣称模型长期质量。 / For models whose names start with `kimi`, `glm`, `minimax`, `mimo`, `step`, or `space-bunny`, non-empty `reasoning_content` is mirrored verbatim to the upstream-read `reasoning` after tool-message merging; no blank placeholder is written and DeepSeek `thinking` is not injected. `deepseek` and `hy` are outside this mirror. Preservation guarantees only the fields sent to WorkBuddy, not long-term model quality.
- **空文本段先补位再出站 / Fill empty text parts before they leave（code 11151）**：上游对 content 里每个 `type:"text"` 段做长度校验，`text` 为 `""`、`null` 或缺失时回 `400` / `11151`「a message has empty content」，而这条历史每一轮都会重放，会话就此退役。触发点不只是客户端真的发了 parts 数组：上游会把**字符串** content 里以 `[` 开头的 JSON 数组当 parts 解析，于是工具结果里常见的表单 / 按钮抓取（`[{"type":"text","text":""}]`）被当成一个空文本段。现在 `build_upstream_body()` 在工具调用配对修复之后、发出之前多一道 `guard_empty_text_parts()`：真实 parts 列表与被嗅探的字符串数组里的空 text 段填成一个空格（上游只校验长度非零，模型看不到任何内容），未知 type、非数组 JSON、纯文本与 `text` 非空的部分逐字节不变，两次执行结果相同。影响面仅限「上游本来会 400」的请求形状。 / The upstream validates every `type:"text"` part and answers `400` / `11151` when `text` is `""`, `null` or missing — and because the history is replayed on every turn, that retires the conversation. A captured form dump in a tool result is enough: a *string* content that starts with `[` is parsed as chat parts, so `[{"type":"text","text":""}]` becomes an empty part. `build_upstream_body()` now runs `guard_empty_text_parts()` after the tool-pairing repairs and fills those parts with a single space (the upstream only checks for non-zero length, so nothing model-visible changes). Unknown part types, non-array JSON, plain text and non-empty parts stay byte-for-byte identical, and the pass is idempotent. Only payload shapes the upstream would have rejected are affected.
- 新增可选的订阅桥接（#830）：把 Clash / Mihomo 订阅、V2Ray URI 或单个 HTTP / SOCKS 代理转换成 mihomo listener，并同步成网关代理槽。direct 代理现在会正确生成 `proxies` 条目；HTTP 订阅与 HTTP 代理可以区分；缺失 PyYAML 时会返回明确错误。Docker 与宿主 mihomo 的联动仍需按 `docs/SUBBRIDGE.md` 挂载配置。
- 新增 `start-workbuddy-all.bat`：一条命令先通过 `--probe-only` 确认端口上是健康的本项目实例，未运行时再拉起代理，随后打开 WorkBuddy 执行器工作台窗口。端口被陌生服务或卡死实例占用时会直接报错，不再误判为“已在运行”。网关目录、Node、Python 可用 `WORKBUDDY_GATEWAY_DIR` / `WORKBUDDY_NODE` / `WORKBUDDY_PYTHON` 覆盖，端口用第一个参数指定（默认 8788）；`WORKBUDDY_LAUNCH_SKIP_WINDOW=1` 只起代理不开窗口。
- **Responses 历史推理保真 / Responses reasoning replay fidelity**：修复连续 `reasoning` 项目只剩最后一段、相邻两轮助手消息被合并、Chat 形状助手历史里的 `reasoning_content` 被丢弃，以及内置 web 工具第二轮请求丢失第一轮推理的问题；推理只关联所属助手消息，不会写入 user/system/tool 普通文本，也不会猜测或改写外部提供者的加密 `encrypted_content`。保真只证明历史按原样送达 WorkBuddy Chat 上游，不额外保证模型的长期任务质量。 / Fix consecutive reasoning replay overwrites, adjacent assistant-turn collapse, Chat-shaped `reasoning_content` loss, and reasoning loss across built-in web-tool follow-ups. Reasoning stays attached to its assistant message, never enters user/system/tool text, and foreign encrypted content is never guessed or rewritten. Preservation proves delivery to the WorkBuddy Chat upstream only, not long-task model quality.
- **API Key 的出口徽章与模型准入覆盖 CodeArts 出口**（#801 / #802）：绑定固定 CodeArts 出口的 Key 在列表里被画成「跟随面板切换」（图标分支只认 `intl` / `cn`），现在出口徽章统一走 `keyRealmBadge()`，三种出口各回各的；「模型准入」的候选清单也补上 `?realm=codearts`（它的 13 个模型与 intl / cn 完全不交集，以前一个都选不到、只能手填 id），绑定了出口的 Key 只列该出口的目录并在清单上方标出出口，未绑定（跟随面板切换）的才取全量；清单按出口分别缓存，不再由先打开的 Key 决定后面所有 Key 的清单。CodeArts 未启用时不去请求该目录。
- **手机端账号卡的长昵称不再顶出卡片**：账号名那格的直接子项原来按内容宽排（`min-width:auto`），昵称一长就把整格撑到卡片外面——390px 视口实测单元格内容宽 271px、名字行 434px，右侧被硬裁且没有省略号。现在该格的直接子项钉住 `min-width:0;max-width:100%`，长昵称按格宽省略。
- **手机端账号区三处布局修正**：批量操作那组 6 个按钮一行摆不下时会被压成竖排单字，窄屏改为两列网格（3 行 2 列），文字保持横排；账号卡第一行原来塞了昵称、备注、分组、任务开关、版本、状态、账户类型，长昵称时整行顶出卡片，现在任务开关与版本 / 状态 / 类型收到第二行单独显示；操作区两层 flex 容器各自换行时「出站身份」会整块另起一行、中间空出一段，两行容器改为 `display:contents` 拆平，按钮按顺序自然流动（「导出」紧跟「同步昵称」，「删除」排在出站身份之后）。以上都只在 ≤640px 生效，桌面布局不变。
- **请求到达即记日志（`chat head`）**：聊天日志行要等请求体收完才写，上传慢的请求在那段窗口里一行痕迹都没有，看起来像「对话卡住」，也分不清「上传慢」与「请求没到本进程」。现在 `do_POST` 在模型路由的请求头到达时先记一条 `chat head`（带 `content_length` 与 key），配合 `body_wait` 能直接区分两者。只覆盖对话真正使用的路由，面板轮询不刷日志。
- **`responses:` 日志同时打客户端与实际生效的推理强度**：原来只打请求体里的 `effort`，客户端不填时恒为 `None`，读起来像「没开思考」，实际按模型默认档（如 `high`）在跑。现在同时打 `effort=`（客户端）与 `upstream_effort=`（实际写进上游请求的值），两者用与构造请求体同一份解析逻辑。
- **自绘下拉面板不再被祖先裁剪、移动端出口/权重格不再互相挤压**：`.cs-panel` 从 `position:absolute` 改为 `position:fixed`，打开 / 滚动 / 缩放时把触发器坐标与最小宽度写进内联样式，向上展开的下拉不会再被账号卡区块的 `overflow-y:auto` 裁掉首行。出口 / 权重两格在移动端改用 `flex:1 1 0` 占剩余宽度，长节点名不再溢出盖住「权重：」标签。
- **400 / 未处理 4xx 不再泄漏账号并发名额**：上游 400（如 11-128 渠道校验）原样透传时直接 `raise`，跳过了重试循环后的统一归还，账号在 `account_max_concurrent` 计数里永久 +1。上限为 1 时一个漏掉的名额就让它永远「已在服务 1 个请求」——面板健康、账号测试也绿，但派发再也不选它，只有重启进程才恢复。其它未单独处理的 4xx（如打错路径的 404）走同一个 `raise`，问题相同。现在两处 `raise` 之前都先归还名额。
- **网关重启后账号列表不再被旧筛选过滤成空**：账号筛选（搜索词 / 状态 / 分组）是内存态，而网关重启后会话失效、重新登录不会刷新页面，重启前设的条件会原样留到登录后，把账号列表过滤成空——「当前禁用」区用的是未筛选名单，反而还显示账号，看起来像账号全丢了，必须手动点「清除筛选」才恢复。现在会话丢失与每次进入面板都会重置账号筛选，以「显示全部账号」为默认。
- **账号表「权重」列不再只剩一个箭头**：64px 的列宽减去单元格内边距只剩 40px，自绘下拉的触发器要吃掉 padding 18px + gap 8px + 箭头 11px，数字被挤成 1px 宽。现在列宽放宽到 78px、该列内边距收到 8px，并给权重下拉单独的紧凑触发器，1–3 位数都留得下。
- **国际版 DeepSeek 出站别名**：客户端和 `/v1/models` 继续显示 `deepseek-v4.1-flash`（同时保留显式 `-sg`），实际发给国际版上游时使用 `deepseek-v4.1-flash-sg`；API Key 模型白名单仍按 base 校验，响应与用量记录保留 `requested_model=deepseek-v4.1-flash`，实际计费模型记为 `-sg`。面板账号测试、每日活跃与窗口探针也走真实 `-sg`。`WB_INTL_MODEL_ALIAS=0` 可关闭映射。出站桌面身份同步到 5.9.4（UA `WorkBuddy/5.9.4 workbuddy-ai/5.9.4 CLI/2.165.0`）。

#### 本分支增强（fork）

- **来源 IP 自动显示地区**：面板「请求记录」的来源 IP 列与「来源 IP」聚合视图现在显示归属地（如「江苏 苏州」），内网地址显示「内网」、本机回环显示「本机」，搜索框也能按地区筛。查询走新增的 `wb_client_geo.py`（ip-api.com 主用、whois.pconline.com.cn 兜底），只在后台线程里跑并受 40 次 / 分钟限速，结果写 `usage/client-geo.json` 缓存 7 天（失败退避 10 分钟、上限 2000 条）。面板只读缓存、查不到就空着——请求路径从不等待这次查询，外部接口挂了也不影响任何请求。开关在「设置 → 网络 → 来源 IP 归属地」（`client_geo_enabled`，默认开；关闭只停新查询，已有缓存照旧显示）。
- **池子被本地熔断关掉一半以上时自动探活**：新增设置 `auto_probe_percent`（面板「设置 → 稳定性 → 池子超半数账号熔断时自动探活」，0–100 的百分比，默认 50，0 = 关闭）。熔断 / 降权 / 软限流都是本地记账，解除它们的唯一证据是一条真实成功的请求；池子被打到半瘫之后每个请求都立刻 503，而客户端重试又会把刚恢复的名额抢空，用户几分钟里看不到一次成功响应（十天日志里 248 次 `no usable account` 就是这么来的）。现在只要「被本地临时惩罚关着的账号」超过阈值，就在后台跑一轮「一键测试」，成功的账号立刻放回池子。两轮之间至少隔 2 分钟；风控连坐暂停期间不探（那时要停手）；被上游 403 限制的账号不进探针名单（探了等于换号再打上游）。

- **高并发时不再一把打死整个账号池**：新增设置 `account_queue_seconds`（面板「设置 → 稳定性 → 池子暂时没号时排队等待」，0–120 秒，默认 0 = 保持老行为）。此前「每个账号的并发名额被占满」或「整池刚被上游按分钟限流停放」时，请求会立刻 503 `no usable account for realm 'cn': every candidate is disabled, cooling`——十天里这类错误 248 次、占全部请求错误的 29%，客户端看到的是「所有请求同时失败」，而它的重试又会在账号刚恢复的瞬间把新名额抢空，形成越忙越死。开了这个预算后，这批请求原地每 100 毫秒重挑一次账号，最多等 N 秒，等到名额才发出去；只有「挨个账号都试过且全部失败」（上游真故障）才不排队、直接报错。并发数不变，只是这一批慢几秒。
- **listen backlog 128 → 1024**：几百个客户端在同时刻重连（客户端重启、反代回源、上游掐连接后的批量重试）时，128 深的 accept 队列会溢出，内核丢 SYN、客户端按 1 秒粒度重传，表现为「一部分请求无端慢 1 秒」。队列深度只占内核条目、不占服务端线程，1024 远低于本机 `net.core.somaxconn`（4096），不会挤占内存。

- **请求来源 IP 全链路可见**：access 日志改用「来源 IP + 请求行」开头，`chat:` / `chat done:` 行与媒体完成行带 `ip=`，usage 行新增 `client_ip` 字段。反代后面按 `X-Real-IP` → `X-Forwarded-For` 首跳解析真实客户端，但仅当对端是回环地址或 `WB_TRUSTED_PROXIES` 显式列出的代理时才采信这些头，公网客户端伪造头无效；解析不出就退回 socket 对端地址，日志里不会出现空字段。usage 行只在调用方拿得到时写 `client_ip`，未传参的调用点与历史行形状完全不变，无需迁移数据。面板「请求记录」新增「来源 IP」列（没有该字段的历史行显示 —），搜索框同步支持按 IP 过滤。出处：排查「谁在刷接口」时 access 日志只有请求行，只能靠时间戳去反代日志里反查。
- **面板「来源 IP」聚合视图**：数据看板新增「来源 IP」表，按客户端地址汇总请求数、Token、用过的账号与最近活动；下面折叠一张「账号 → 来源 IP」反查表，看每个账号被哪些客户端用过——用来认出「同一个人换着号刷」或「一个号被几个人共用」。数据来自 `/usage/by-client-ip`：全量视图，不跟区间选择器联动（理由同「按账号」），聚合走增量折叠，载荷挂 15 秒 TTL + ETag，5 秒一轮的轮询多数落在 304 上。`client_ip` 字段上线前的历史行归入「(未知)」并标注「IP 上线前」，不当作真实地址统计。
- **上游超时收紧**：首字节超时 120 → **45 秒**，流中空闲 300 → **90 秒**。实测 43 万字节请求体的首字节只要 1–3 秒，旧的 120 秒让卡住的上游把请求连同它的并发槽位占满两分钟才开始重试；流中 90 秒静默已是实测思考增量间隔（约 40 毫秒）的两千倍，只在流真的死掉时才触发。两项都可在面板「设置 → 上游」改回。出处：排查「带宽没吃满却长时间不响应」时发现 `stream aborted: [Errno 110] Connection timed out` 的单条请求跑了 1401–1935 秒。
- **OpenWrt 包版本号跟随源码**：`wrt/openwrt/workbuddy2api/Makefile` 的 `PKG_VERSION` 补到当前源码版本（2.0.0 → 2.0.4），恢复 `build-apk.sh` / `build-ipk.sh` 与 release 工作流的三重比对（Makefile 版本 = `server_version` = tag）。此前 2.0.1–2.0.4 一直没同步，tag 触发的 release 工作流在 version job 就报错退出。
- **用量聚合缓存跳过写盘时不再静默停更**：checkpoint 写盘因状态锁被占、状态暂不可序列化或写入异常而跳过时，按类节流告警并登记后台异步补写（30 秒起指数退避，封顶 15 分钟）；补写成功立即取消，失败继续重试。新增 64MB checkpoint 落后告警、蓝绿双进程临时文件隔离，避免 `remaining` 一类缓存连续多日不落盘、重启后反复全量重折。
- **设置页分组在正體中文 / 英文界面不再整页空白**：分组胶囊靠各区块的 `h2` 标题文字比对归类，界面语言切到正體中文或英文后标题已被 i18n 换掉，比对全部落空、每个区块都归到「日志与系统」，于是点「基础 / 自动化 / 稳定性」时把整页 section 全部 hidden（看起来设置页清空）。现在改用 i18n 翻译前保留的原文比对，三种语言的分组结果一致；另补上漏归的「选择网页活跃提示词」（原来被归到「日志与系统」）。
- **账号分组**（#707）：账号新增可选分组，支持按组筛选、导入时指定分组、单账号编辑、分组启停，以及刷新凭证 / 测试 / 补积分等批量操作仅作用于当前分组；API Key 账号选择器也支持按组选入与移除。
- **API Key 配置示例**（#704）：设置页新增可折叠的 Base URL、cURL 与各协议端点示例，并支持一键复制。
- **检查更新支持代理槽**（#798）：可在设置页指定 GitHub 更新检查使用的代理槽；槽停用或删除后自动回退直连。
- **会话粘滞修复**（#718）：小账号池的长会话不再按页轮换账号，避免前缀缓存丢失和 Token 消耗翻倍。
- **请求体超限 413**（#799）：先返回 413，再在有限时间内排空上传，避免连接重置吞掉响应。
- **CodeArts 参数与模型 ID**（#794 / #797）：输出 token 按模型上限收敛、`stop` 字符串归一化；参数错误返回 400 且不冷却账号。`deepseek-v4.1-flash` 与 `-1017` 为独立模型，精确匹配。
- **提示词改写与模型倍率**（#796 / #774）：恢复退化为空操作的 `SANITIZE_REWRITES`；live 目录的 `x0.00` 不再覆盖已知付费倍率。
- **风控连坐暂停保护可配可立即解除**：设置页「稳定性」新增「风控连坐暂停保护」卡片。上游 403 / 11140 异常行为触发全区域暂停派发时，面板展示实时剩余倒计时，提供「立即解除暂停」一键解冻恢复请求；支持自定义暂停时长（默认 1800 秒，设为 0 可彻底关闭连坐熔断保护），且保存更短时间时即时截断现有倒计时。
- **账号多时面板更顺**：账号表改为客户端分页（每页 50 个，排序与筛选作用在全部账号上再切页；改区域 / 改筛选 / 点表头回第 1 页，账号变少时页码夹回最后一页）；15 秒账号轮询拿回的数据与视图都没变时不再整表重画，且只在显示账号数据的页签（网关、账号、任务，新导航的总览）上跑，切回这些页签时立即拉一次；自动补积分改为只点名缺积分的号（`POST /accounts/credits` 新增 `uids` 列表参数，非列表回 400），每个号每次页面加载最多补一次，不再触发全池逐个刷。手动「一键刷新积分」不变。
- 移除已废弃的 `WB_DEEPSEEK_FLASH_FORCE_SG` 文档行与两个恒返回 `False` 的存根函数（#776）。
- **CodeArts 模型倍率**：`/v1/models?realm=codearts` 的条目新增 `credits`（如 `x0.7`，与 WorkBuddy 目录同一写法），取自上游模型目录的标准档；错峰优惠档不计入，上游没有倍率的模型不带此字段。
- **改善 Claude Code 兼容性**（#733）：`sanitize` 现在把
  `You are Claude Code, Anthropic's official CLI tool for Claude.` 整句中性化；
  旧规则只把 `CLI for Claude` 改写成 `CLI tool for Claude`，反而保留了
  `You are Claude Code` 指纹。覆盖大小写与弯引号，`user` / `tool` 内容不改写。
- **添加账号时可指定登录出口代理槽**：OAuth 登录弹窗新增「登录出口代理」下拉（只在配置了启用的代理槽时出现），申请授权链接、等待回调与拉取账号资料都走选中的槽，登录成功后账号绑定到该槽，避免登录 IP 与后续调用 IP 不一致。默认「直连（不走代理槽）」，与以前完全一样；选「自动」(`proxySlot: "auto"`) 时随机挑一个没绑定账号（含 CodeArts 账号）、也没被其他进行中登录占用的槽，没有空闲槽则直连。已绑定槽的账号用「自动」重登会保留原槽；槽绑定不写进账号的旧版 `proxy` 字段。`/accounts/login/start` 的日志与响应只给代理的 host:port，不含用户名密码；不存在或已停用的槽返回 400。
- 启动检查不再把"端口能连上但一直不答"当成端口空闲。此前 `--probe-only` 用 2 秒超时探 `/health`，卡死的实例只会让它超时，于是判定端口可用、又叠了一层实例；Windows 的 `SO_REUSEADDR` 允许重复监听，内核仍把新连接分给卡死的那个，看板与日志查看器就一直是空的。现在这种情况明确报错（退出码 1）并给出占端口 PID 的查法，不再静默重复启动。
- 部署入口改用 `python3 -m wb_proxy`（OpenWrt init 与 Dockerfile）：同一份代码实测空闲内存少 47-54 MB（#702 / #777）。
- 新增 `WB_DUMP_11_128` 本地取证开关（默认关闭）：`1` 只写脱敏摘要，`full` 额外写出站
  body，文件落在 `usage/11-128-dumps/`；用于定位 Claude Code 专属 11-128 的真实请求差异
  （#733）。摘要不含提示词明文，`full` 含明文但由使用者显式开启。
- **国际版每日活跃总开关**：设置页「国际版每日活跃打卡」新增「定时自动打卡」勾选框（`settings.json` 键 `daily_activity`，`/settings/save` 只收 JSON 布尔）。缺省开启，老安装行为不变；关掉后调度器不再自动跑每日活跃（定时时段、立即巡检保活、启动补跑都跳过，启动补跑留到重新打开后再消费），账号上的手动打卡不受影响。
- **用量缓存写盘不再拖住其他视图**：checkpoint 写盘收集各类聚合状态时，状态锁改为非阻塞尝试；某一类正在锁里全量重折（GB 级 `usage.jsonl` 冷启动要几十分钟）时这一类本次跳过、下次再写，不再连带 `/usage/by-account` 等视图一起卡住（面板「账号加载失败」/ Cloudflare 524）。

- **请求列表：失败看得进去、筛得出结果**：结果列里的「失败 / 上游中断 / 客户端取消」改成可点按钮，点开是一层详情弹窗——HTTP 状态码、上游原话（落盘时已截断 200 字）、账号、API Key、模型、耗时、模式、token 与请求类型，可一键复制；行上不再为它多占一列。筛选条移到标题下方（表格之上），新增「结果（全部 / 成功 / 失败）/ 账号 / 模型 / Key」四个下拉，全部走服务端 `GET /usage/recent?account=&model=&key=&outcome=`：日志上百万行时不是只筛当前页，而是向后最多扫描 `WB_RECENT_FILTER_SCAN`（默认 20000）行；扫到上限时返回 `total_exact=false` 与 `scanned=N`，界面写明「已扫描 N 行，命中 M 条（可能还有更早的）」，不假装知道全量。「失败」是个桶：`failed` / `upstream_aborted` / `client_aborted` 都算没成功。账号 / 模型 / Key 三个下拉恒带搜索框（`data-cs-search="on"`），几十上百条也不用翻。 / **Request list: failures readable, results filterable**: the outcome cell's "failed / upstream aborted / client aborted" badges are buttons now, opening a detail dialog with the HTTP status, the upstream message as recorded (already truncated to 200 chars), account, API key, model, elapsed time, mode, token counts and request type, copyable in one click - with no extra column spent on the row. The filter bar moves above the table and gains outcome (all / succeeded / failed), account, model and key dropdowns, all served by `GET /usage/recent?account=&model=&key=&outcome=`: with millions of log lines the filter is not limited to the current page - it scans back at most `WB_RECENT_FILTER_SCAN` (default 20000) rows and reports `total_exact=false` plus `scanned=N` when it hits that cap, so the UI says "scanned N rows, M matched (older rows may exist)" instead of pretending to know the total. "Failed" is a bucket: `failed` / `upstream_aborted` / `client_aborted` all count as not-succeeded. The account / model / key dropdowns always carry a search box (`data-cs-search="on"`), so a few hundred entries do not have to be scrolled by hand.
- **账号页批量操作统一按「勾选否则当前筛选结果」定作用范围**：刷新积分 / 刷新凭证 / 测试 / 分配代理 / 切换所有出站身份 / 启用 / 停用原来各写一套口径（有的刷整池、有的只认分组），现在统一走 `acctScopeUids()`——有勾选只作用于勾选的账号，没有勾选则作用于当前筛选结果的全部账号（视图 + 号池 + 搜索 / 状态 / 分组 / 错误码，且不分页，避免「全部」只作用当前页）。批量挪号池仍要求先勾选：号池归属是一次明确的指派，没有勾选无从下手。`/accounts/refresh`、`/accounts/test`、`/accounts/product` 新增 `uids` 点名，空列表即什么都不做，不退化成全池；`/accounts/set-all` 原本就要求显式 UID 列表。按钮同时去掉「一键」前缀（刷新积分 / 刷新凭证 / 测试 / 分配代理 / 切换所有出站身份 / 启用 / 停用），「当前分组启用 / 停用」保留。 / The account page's bulk actions now share one scope rule: "Refresh credits", "Refresh tokens", "Test", "Assign proxy exits", "Switch all outbound identities", "Enable" and "Disable" each used to compute their own target set (some hit the whole pool, some only the group filter). They now all go through `acctScopeUids()`: the ticked accounts when there are any, otherwise the whole current filter result (view + pool + search / status / group / error code, and not just the current page, so "all" does not silently mean "this page"). Moving accounts between pools still requires a selection, because a pool assignment is an explicit choice. `/accounts/refresh`, `/accounts/test` and `/accounts/product` accept a `uids` list now; an empty list does nothing instead of falling back to the whole pool, and `/accounts/set-all` already required an explicit UID list. The "一键" prefix is dropped from those buttons while "Enable / Disable current group" keeps its name.
- **号池筛选常显并改为下拉框**：账号表的号池筛选不再跟随「文本 / 媒体号池隔离」开关隐藏——`poolScope` 是账号的归属标记，隔离关着时它只影响服务端派发，不影响这个字段可查可改。三个互斥按钮（全部 / 文本 / 媒体）换成一个下拉框，默认「全部号池」，选中即生效；账号行的号池徽章同样恒显示，「移入媒体池 / 移入文本池」不再要求先开隔离。移动端号池组排成一行（下拉 + 计数 + 两个按钮），不再各占一行把账号列表推下去。 / The pool filter no longer hides behind the pool-separation switch: `poolScope` is an account's ownership tag, and the switch only affects server-side dispatch, not whether the field can be seen or changed. The three mutually exclusive buttons become one dropdown (All / Text / Media, default All, applied immediately); the pool badge on each row is always shown, and "Move to media pool" / "Move to text pool" no longer require the switch. On phones the pool group sits on a single row (dropdown + counter + two buttons) instead of pushing the account list down.
- **模型别名开关**：`model_aliases` 之前只是一张无条件生效的映射表——填进去的别名立刻对所有客户端可见、所有请求都会被改写，运维想「先填好但暂不生效」没有手段。新增 `model_aliases_enabled`（缺省关闭，旧配置升级后行为不变），关闭时别名既不进 `/v1/models` 也不改写请求，原模型名照常可用；开启后别名与原名都可用，别名在模型清单里紧跟其目标模型列出。面板「设置 → 模型与定价」新增开关，「网关 → 模型清单」新增行内「对外名称」列（开关关闭时整列隐藏），支持直接编辑单个模型的对外名称。配套：别名请求的应答回显客户端发来的名字（`client_facing_model`），配了模型限制的 Key 用别名调用不再被网关自己的改写拦下，`/settings` 与 `/settings/save` 读写 `model_aliases` / `model_aliases_enabled`。 / **Model alias switch**: `model_aliases` used to be an unconditionally applied mapping table - any alias typed in was immediately visible to every client and rewritten on every request, with no way to stage a table without activating it. A new `model_aliases_enabled` key (off by default, so upgrades keep the old behaviour) gates it: while off, aliases are neither listed in `/v1/models` nor rewritten, and the original model names keep working; while on, aliases and original names both work and each alias is listed right next to its target. The panel gains a switch under Settings -> Models & pricing and an inline "External name" column in the gateway model catalog (the whole column hides while the switch is off), editable per model. Supporting changes: replies echo the name the client sent (`client_facing_model`), a key restricted to an alias is no longer rejected by the gateway's own rewrite, and `/settings` plus `/settings/save` read and write `model_aliases` / `model_aliases_enabled`.
- **账号页桌面布局重排**：账号表改为跟随容器宽度（`width:100%` + `min-width:1096px` 只作横向滚动兜底），上一版写死 `min-width` 让容器窄时右侧列被固定操作列盖住，「Token / 缓存」看着像被裁掉；各列按实测内容定宽，多余宽度全给账号列。勾选列、版本列、账号列三列常驻左侧吸附（偏移 0 / 32 / 100px），横向滚动时不会只剩一排认不出归属的数据。桌面昵称允许折行、完整显示（此前 `nowrap + ellipsis` 把长昵称裁成「changzhan…」）。任务开关 / 备注 / 分组收到账号行内同一排（`.acct-chip-row`）。 / **Desktop account table re-layout**: the table now follows its container (`width:100%` with `min-width:1096px` only as a horizontal-scroll fallback); the previous fixed `min-width` let the sticky actions column cover the right-hand columns on narrower containers, so "Token / Cache" looked cut off. Columns are sized to their measured content and the leftover width goes to the account column. The checkbox, version and account columns stay pinned to the left (offsets 0 / 32 / 100px) so a horizontally scrolled row never becomes an unidentifiable strip. Desktop nicknames wrap and show in full (they used to be clipped to "changzhan..." by `nowrap + ellipsis`). The task switch, note and group chips sit on one row inside the account cell (`.acct-chip-row`).
- **账号页移动端卡片分层**：第一行「勾选 + 昵称 + 版本 / 账户类型徽章」，第二行「号池 + 任务开关 + 备注 + 分组」chip 流；状态徽章与到期信息各归其行，长昵称按字符折行不超屏。启用 / 停用 / 删除三个按钮在手机上排成一行（各占 1/3），删除紧跟停用。批量操作组改成两列网格（6 个按钮 3 行 2 列），按钮文字不再被压成竖排。号池组（下拉 + 计数 + 两个「移入」）排成一行。 / **Mobile account card layering**: the first row is "checkbox + nickname + version / account-type badges" and the second row is a chip flow of "pool + task switch + note + group"; the state badge and expiry each get their own line, and long nicknames wrap by character instead of overflowing. Enable / Disable / Delete sit on one row on phones (one third each) with Delete right after Disable. The bulk-action group becomes a two-column grid (six buttons over three rows), so button labels are no longer squeezed into vertical text. The pool group (dropdown + counter + two "move" buttons) sits on a single row.
- **启用 / 停用 / 删除 / 导出统一作用域**：四个「xx 已选」独立按钮移除，能力并进「启用 / 停用 / 删除 / 导出」——有勾选时以勾选为准，没有勾选时以当前筛选结果为准；勾选时按钮上标出数量（如「启用 (2)」），确认框写明本次范围。表头全选框改为作用于当前筛选结果（跨页），三态也按筛选结果回填。 / **One scope for enable / disable / delete / export**: the four "xx selected" buttons are gone and their behaviour folded into Enable / Disable / Delete / Export - checked accounts when anything is selected, otherwise the current filter result; the buttons show the count when a selection exists (e.g. "Enable (2)") and the confirmation dialog names the scope. The header select-all now applies to the whole filter result (across pages) and its tri-state is filled from that same set.
- **表头文案缩短**：「今日活动」→「活动」、「总 token」→「Token」（全称保留在 `title` 里），省出的宽度给账号列。 / **Shorter header labels**: "Today's activity" -> "Activity" and "Total tokens" -> "Token" (the full wording stays in `title`), freeing width for the account column.

---

## 八、致谢与引用声明 (Credits & References)

在协议逆向、风控规避、任务链路与工程化设计过程中，本项目参考、吸纳并致谢以下优秀开源项目与技术成果（排名不分先后）：

### 核心逆向与协议参考
- **[Sliverkiss/workbuddy2api](https://github.com/Sliverkiss/workbuddy2api)**：成长任务逆向、设备指纹派生（`derive_id`）、调度器（`Scheduler`）与 `reasoning_content` 回填设计；
- **[L0NE-6/WorkBuddy-Daily](https://github.com/L0NE-6/WorkBuddy-Daily)**：国内版微信小程序专属事件指纹与动态专家深链任务模型；
- **[88lin/workbuddy-auto-signin](https://github.com/88lin/workbuddy-auto-signin)**：猫猫日常旅行与成长能量开盲盒（Buddy 盲盒）安全生命周期；
- **[linguo2625469/workbuddy2api-panel](https://github.com/linguo2625469/workbuddy2api-panel)**：国内版连登管家闭环逻辑与轻量对话活跃上报事件；
- **[misakano7545/workbuddy2api-panel](https://github.com/misakano7545/workbuddy2api-panel)**：Go/uTLS Node/OpenSSL ClientHello 指纹参数与桥接实现参考（18 Cipher、10 Extension、无 ALPN）；
- **[Zhengyuuuui/workbuddy2api](https://github.com/Zhengyuuuui/workbuddy2api)**：国际版 11140 账号封禁识别、冷却规避与故障排查清单；
- **[yuanyuanyuan430/workbuddy2api-hub](https://github.com/yuanyuanyuan430/workbuddy2api-hub)**：国际版 EdgeOne CDN 证书错配排查与活跃上报优雅降级方案；
- **[CangShui/workbuddy-cliproxy-fix](https://github.com/CangShui/workbuddy-cliproxy-fix)** & **[lovingfish/workbuddy-cliproxy](https://github.com/lovingfish/workbuddy-cliproxy)**：早期客户端代理修复与网关通信原型；
- **[mmqz/cpa-multi-plugins](https://github.com/mmqz/cpa-multi-plugins)**：多插件管理与出站调度结构参考；
- **[ardeyouxipianyi/workbuddy2api](https://github.com/ardeyouxipianyi/workbuddy2api)**：国内版早期分发包逆向分析与出站 User-Agent 规范；

### 工程化与生态基础
- **[aodianjun/workbuddy2api-hub](https://github.com/aodianjun/workbuddy2api-hub)**：OpenWrt 路由器打包配方（`.ipk` / `.apk`）与系统服务支持；
- **[YTjungle666/workbuddy2api-hub](https://github.com/YTjungle666/workbuddy2api-hub)**：社区维护的 Rust 后端与启动器重写分支，提供无 Python 运行时依赖的单文件静态二进制；
- **[astral-sh/python-build-standalone](https://github.com/astral-sh/python-build-standalone)**：Windows 便携版免安装精简独立 Python 运行时构建基石；
- **[deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness)**：DSH 客户端协议与提示词指纹清洗规避参考。

感谢所有向本项目提交 PR、反馈 Issue 与分享实测样本的社区贡献者！

---

## 九、免责声明 (Disclaimer)

本项目仅用于协议学习与个人开发测试，不提供任何商业服务或可用性担保。因使用非官方客户端产生的账号风控、限制或封禁由使用者自行承担，请优先使用官方客户端。

## ⭐ Star 趋势

<p align="center">
  <a href="https://star-history.com/#ardeyouxipianyi/workbuddy2api-hub&Date">
    <img src="https://api.star-history.com/svg?repos=ardeyouxipianyi/workbuddy2api-hub&type=Date" alt="Star History Chart" width="760">
  </a>
</p>
