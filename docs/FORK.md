# 本分支与上游的关系（维护者手册）

本仓库是 [ardeyouxipianyi/workbuddy2api-hub](https://github.com/ardeyouxipianyi/workbuddy2api-hub) 的社区维护分支：
上游代码原样跟随，本分支只在自己的函数 / 区块里追加功能，尽量不改上游正在频繁改动的行。

## 版本号

- 上游用 `2.0.x`；本分支从 **2.1.0** 起独立递增，避免 tag 撞名。
- 历史遗留：本分支已发布的 v2.0.1 – v2.0.7 与上游同名 tag 指向不同提交，不再改动，只在发布说明里注明。
- 发布包名 `workbuddy2api-hub-v<version>.zip`，更新器读 `WB_UPDATE_REPO`（本分支指向 `M-strange/workbuddy2api-hub`）。

## 一次性设置

```bash
git remote add upstream https://github.com/ardeyouxipianyi/workbuddy2api-hub.git
git fetch upstream --no-tags
```

## 每次上游发版后的同步流程

```bash
git fetch origin --tags            # 先对齐自己的 main
git fetch upstream --no-tags
git checkout -B sync/upstream origin/main
git merge upstream/main            # 冲突面通常很小
# 解决冲突 -> 跑全量测试 -> 改版本号 -> 提交 -> 推 main -> 打 tag
python tests/run_all.py --jobs 4
```

2026-11-09 同步上游 v2.0.1 – v2.0.3（49 个提交，+8510/-482）时，冲突只有 5 个文件 11 处：

| 文件 | 冲突原因 | 处理 |
| --- | --- | --- |
| `wb_proxy.py` | 只有版本号两处（`runtime_settings_view["version"]`、`Handler.server_version`） | 取本分支新版本号 |
| `wrt/openwrt/workbuddy2api/Makefile` | 只有 `PKG_VERSION` | 与 `server_version` 保持一致 |
| `dashboard.html` | 上游改了同一处 CSS 与 `autoAssignSlots(this)` | 逐块取上游（本分支功能在别的区块） |
| `tests/_test_mobile_account_layout.js` | add/add | 取上游断言 |
| `README.md` | 徽章、维护状态、套件计数、changelog | 徽章与状态取新值；计数按 `ls tests/_test_*` 重算；changelog 分「合并上游」「本分支增强」两组都保留 |

## 冲突最少化的写法约定

1. 新功能尽量**新增**函数或新段落，不插入上游正在频繁改动的逻辑中间。
2. 面板改动集中在自己的区块（例如 `clientIpPanel`），不重排上层容器结构。
3. 版本号只有三处：`wb_proxy.py` 的 `runtime_settings_view["version"]`、`Handler.server_version`、OpenWrt `PKG_VERSION`。
4. 本地设置项一律新增 `wb_settings` key + 默认值，不改上游已有 key 的语义。

## 本分支增强清单

| 功能 | 入口 |
| --- | --- |
| 来源 IP 全链路（access / chat / usage 行） | `client_ip_of()`、`record_usage(client_ip=)` |
| 面板「来源 IP」聚合视图 | `/usage/by-client-ip`、`dashboard.html` 的 `clientIpPanel` |
| 账号池排队等待 | `wb_settings.account_queue_seconds`、`wait_for_pool_account()` |
| 池子超半数熔断时自动探活 | `wb_settings.auto_probe_percent`、`maybe_auto_probe()` |
| 上游超时 45 / 90 秒 | `wb_settings.upstream_config()` 默认值 |
| listen backlog 1024 | `GatewayServer.request_queue_size` |
