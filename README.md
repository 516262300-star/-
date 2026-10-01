# 拼多多广告数据同步到 Notion

这个项目用于从公司 ERP 抓取拼多多一到七店的广告数据，并同步到对应的 Notion 数据库。

- ERP 数据页：`ldswj.net`
- 默认店铺：一到七店，`--store all`
- 默认日期：昨天，按 `Asia/Shanghai` 计算
- 判重规则：`日期 + plan_id + 店铺`
- 敏感信息：`.env` 和 `.auth/session.json` 不会提交到 GitHub

## 1. 项目位置

本机路径：

```text
D:\desktop\codex\guanggao
```

主要文件：

- `main.py`：同步主程序
- `erp_client.py`：ERP 登录、抓取、解析
- `notion_sync.py`：Notion 写入、字段映射、去重
- `stores.py`：一到七店 ERP 和 Notion 映射
- `catchup_daily.py`：自动检查 Notion 是否缺昨天数据，缺哪个店补哪个店
- `run_daily.ps1`：每天 9 点定时任务调用的脚本
- `desktop_app.py`：桌面控制面板
- `启动拼多多广告同步.bat`：双击打开桌面软件

## 2. 配置 .env

项目根目录需要有 `.env`：

```env
NOTION_TOKEN=你的 Notion integration token
NOTION_DATABASE_ID=一店 Notion 数据库 ID
# ERP 登录使用 Leedis 客户端，无需账号密码
```

说明：

- `.env` 已加入 `.gitignore`，不会上传 GitHub。
- ERP 登录统一使用 Leedis 桌面客户端。
- ERP 网页登录态过期时，通过客户端重新打开系统。
- 客户端未登录时停止任务；请先在客户端登录，再重试。

## 3. 桌面软件

桌面上有快捷方式：

```text
拼多多广告同步
```

双击后可以操作：

- `同步昨天`
- `同步单日`
- `同步日期范围`
- `刷新客户端登录并同步`
- `打开日志文件夹`
- `停止当前运行`

日常推荐直接用这个桌面软件，不需要记命令。

## 4. 手动命令

先进入项目目录：

```powershell
cd D:\desktop\codex\guanggao
```

同步昨天一到七店：

```powershell
python main.py --store all
```

同步指定日期一到七店：

```powershell
python main.py --date 2026-06-03 --store all
```

同步日期范围：

```powershell
python main.py --range 2026-05-25~2026-05-31 --store all
```

只检查 ERP 抓取和解析，不写入 Notion：

```powershell
python main.py --date 2026-06-03 --store all --dry-run
```

强制刷新客户端登录并同步：

```powershell
python main.py --date 2026-06-03 --store all --relogin
```

检查 Notion 是否缺昨天数据，缺少才自动补跑：

```powershell
python catchup_daily.py --store all
```

检查指定日期是否缺数据，缺少才自动补跑：

```powershell
python catchup_daily.py --date 2026-06-04 --store all
```

## ERP 客户端登录（2026-09-30）

ERP 统一复用 **Leedis 桌面客户端**。先在客户端完成登录，任务通过客户端“打开系统”取得专用 ERP Chrome 的网页登录态；不再读取 ERP_USERNAME、ERP_PHONE、ERP_PASSWORD，也不回退账号密码或脚本扫码登录。客户端凭据仍由客户端和 Windows 凭据管理器保管。任务只在内存使用 ldswj.net 的网站 Cookie，不再读取旧 `.auth/session.json`、`.erp_session.bin` 或 `states/erp.json`。

本机已配置客户端。换电脑时安装 LeedisClient.exe、Google Chrome 和项目 requirements.txt，然后运行工作台仓库的安装命令（替换成实际客户端路径）：

```powershell
powershell -ExecutionPolicy Bypass -File tools/setup_erp_client.ps1 -ClientExe "D:\desktop\客户端登录\Leedis-Windows\LeedisClient.exe"
```

配置保存在 `%LOCALAPPDATA%/LeedisDesktop/workbench-config.json`，只记录客户端路径；也可用 `ERP_CLIENT_EXE` 覆盖路径。安装脚本生成客户端需要的 `%USERPROFILE%/Desktop/ERP Chrome.lnk`，使用独立浏览器目录 `%LOCALAPPDATA%/LeedisDesktop/erp-chrome` 和本机 9222 端口。已有配置和快捷方式先备份再更新。网站登录态属于敏感本机数据，不提交到 GitHub。

客户端尚未运行时自动启动并尝试恢复已有登录；未登录、客户端忙、9222 不可用或登录过期无法恢复时，任务失败并显示提示。请在客户端登录后重试原任务；不会自动尝试账号密码，不会关闭客户端或 ERP Chrome。自动任务仍需在已登录 Windows 的同一用户会话下执行。切换客户端账号后，应结束当前任务并显式刷新网站登录，再重新运行。

```powershell
python erp_desktop_auth.py login  # 客户端登录，需要授权时由本人完成
python erp_desktop_auth.py check  # 后台只读检查网页会话，不打开可见网页
```

公共接入代码维护源为工作台 `tools/erp_desktop_auth.py`；各业务仓库包含同版副本，可独立运行。更新公共模块时同步四个业务副本。升级无需移植旧网页 Cookie，旧密码配置可自行删除，程序已不再使用。

### 客户端接入重试（2026-10-01）

客户端“打开系统”成功后，脚本会最多尝试 3 次连接 ERP Chrome（每次最多 10 秒）；连接后在 45 秒等待期内检查网站会话，单次验证请求最多 10 秒。浏览器启动延迟、验证请求短暂超时或连接重置会自动重试，不重复调用客户端登录。最后一次在途验证可能使总等待略超过 45 秒。

最终失败会区分“9222 端口连接失败”和“网页会话验证失败”，并记录异常类型或 HTTP 状态，不输出 Cookie 或客户端凭据。网页会话验证失败时，先确认 ERP 网页能正常打开；显示登录页才需在客户端重新登录。可用 `python erp_desktop_auth.py check` 只读验证，再用 `python main.py --date YYYY-MM-DD --store all` 重跑，按原判重规则更新或新建。

2026-10-01 09:00 的失败发生在客户端返回成功后的网页接入阶段，尚未写入广告数据。旧日志未保留底层异常，无法确认当时属于端口、超时还是连接重置；本次补足重试和分阶段诊断。

## 6. Notion 写入逻辑

每条广告数据按下面三项判重：

```text
日期 + plan_id + 店铺
```

如果 Notion 里已存在，就更新；不存在，就新建。

写入前会先按日期范围读取 Notion 已有数据用于去重。日志里会显示：

- `准备写入 Notion`
- `读取 Notion 数据库字段`
- `读取 Notion 已有数据用于去重`
- `写入 Notion：1/4`

Windows 上的 Notion API 请求会优先使用系统自带的 `curl.exe`/Schannel 直连，以避开 Python/OpenSSL 偶发的 `10054` 连接重置；失败后再自动尝试 Python 直连和系统代理。代理开关不再决定首选路线。如果新建页面 `POST /pages` 时回包断开，脚本会先按 `日期 + plan_id + 店铺` 反查是否已经创建，避免重复登记。

如果某一路网络临时断开但后续重试成功，日志只记录为普通进度，不再刷 `WARNING`。只有全部重试都失败时，才会显示 Notion 请求失败的 `WARNING`。

如果某个店 Notion 读取或写入连续失败，脚本会把这家店尚未写入的行保存到 `debug/pending_notion/`，继续处理后面的店铺，最后汇总失败店铺。

脚本会写入这些主要字段：

- 广告计划
- 日期
- 广告类型
- 商品ID
- 花费
- 平均点击花费
- 点击率
- 转化率
- 投产比
- 曝光量
- 推广曝光占比
- 成交笔数
- 每笔成交花费
- 每笔成交金额
- 广告成交金额
- plan_id
- 店铺

百分比字段写入小数：

- `点击率`
- `转化率`
- `推广曝光占比`

例如 ERP 是 `13.66%`，脚本写入 `0.1366`，Notion 显示为 `13.66%`。

## 7. 广告类型和商品ID

广告类型自动判断：

- 广告计划名包含 `全店托管`：写入 `全店托管`
- 其他带 ID 或 plan_id 的计划：写入 `稳定成本`

商品ID自动判断：

- 只给 `稳定成本` 广告填写
- 从广告计划名里的 `商品ID` 或 `ID` 后面提取数字
- `全店托管` 不填商品ID

## 8. 每天 9 点定时任务

Windows 任务计划名称：

```text
拼多多广告数据同步到 Notion
```

执行脚本：

```text
D:\desktop\codex\guanggao\run_daily.ps1
```

每天 9 点会自动运行补漏检查：

```powershell
python catchup_daily.py --date 昨天 --store all
```

运行逻辑：

1. 先检查一到七店的 Notion 数据库里，昨天是否已经有广告数据。
2. 已经有数据的店铺直接跳过。
3. 没有数据的店铺才抓 ERP 并写入 Notion。
4. 写入时仍按 `日期 + plan_id + 店铺` 去重，所以重复运行不会重复登记。

如果 9 点电脑没开机，任务已设置为开机登录后尽快补跑；补跑时也会先查 Notion，发现昨天缺数据才自动补。

如果 ERP 登录态过期，脚本通过客户端刷新网站会话；客户端未登录时记录失败，登录客户端后手动重跑补漏。定时脚本不再弹出旧的重新登录同步窗口。

## 9. 日志和排错

日志目录：

```text
D:\desktop\codex\guanggao\debug
```

定时任务日志文件格式：

```text
task_YYYYMMDD_HHMMSS.log
```

常见情况：

- ERP 登录态过期：请先在 Leedis 客户端登录后重试。
- Notion 网络失败：脚本会依次尝试 Windows TLS、Python 直连和系统代理；三条路线都失败时才会结束本轮请求。可先确认 Windows 自带的 `curl.exe` 存在，再检查 `api.notion.com` 和代理节点。
- 如果日志里看到 `POST /pages` 的 SSL 或 EOF 错误，表示已经进入 Notion 新建页面阶段，是网络回包中断；重跑会先反查已创建页面，减少重复写入风险。
- 如果日志停在 `读取 Notion 数据库字段` 或 `读取 Notion 已有数据用于去重`，等待 5 次重试完成，不要提前停止任务；最终 `WARNING` 会分别列出 Windows TLS、Python 直连和系统代理的错误。
- 如果日志只显示某个店“缺少数据，准备补跑”，但实际同步抓取 0 行，通常表示 ERP 当天这个店没有广告行，不是 Notion 写入失败。
- 如果日志显示 `Notion 待补写数据已保存`，说明这家店当时没写入成功；网络恢复后重新跑同一天同店即可，脚本会按去重规则写入或更新。
- GitHub 推送失败：通常是电脑连不上 `github.com`，本地提交仍然保存。

## 10. 代码修改收尾规则

每次修改脚本代码后，都要做下面几件事：

1. 运行 `py_compile` 或小范围实际同步测试。
2. 如果行为、日志、排错方式、定时任务或字段规则有变化，同步更新 Notion 里的“拼多多广告同步 Agent 使用说明”。
3. 提交并推送到 GitHub。

## 11. 安装依赖

新电脑第一次安装：

```powershell
cd D:\desktop\codex\guanggao
pip install -r requirements.txt
python -m playwright install chromium
```

如果是从 GitHub 重新拉代码，需要重新配置 `.env`、安装并配置 Leedis 客户端与 ERP Chrome；先运行 `python erp_desktop_auth.py check` 检查登录，再执行同步。程序不再生成或读取旧 `.auth/session.json`。

### 广告同步不再重复弹网页（2026-10-01）

普通任务优先复用已验证的 ERP 网页登录态，不再每次调用客户端“打开系统”。ERP Chrome 开着时直接读取会话，不增加或关闭用户标签页；浏览器已关闭时，使用同一个专用 ERP 浏览器目录启动无窗口 Chrome，读取并验证登录态后关闭本次后台实例。不会读取普通 Chrome 的浏览数据，也不会把 Cookie 保存到业务项目文件中。

只有首次尚未建立网站会话、网站明确显示登录过期，或手动指定 `--relogin` / 登录模块 `open` 时，才通过客户端打开一次网页建立会话。网络超时、HTTP 错误或浏览器目录占用不会通过弹网页来重试，仍保留具体错误。登录模块 `check` 始终只验证，不打开可见网页、不调用客户端刷新；失败后根据提示处理。切换客户端账号后请显式刷新登录（广告同步用 `--relogin`），以更新专用浏览器会话。
