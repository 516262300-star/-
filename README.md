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
- `run_daily.ps1`：每天 9 点定时任务调用的脚本
- `desktop_app.py`：桌面控制面板
- `启动拼多多广告同步.bat`：双击打开桌面软件

## 2. 配置 .env

项目根目录需要有 `.env`：

```env
NOTION_TOKEN=你的 Notion integration token
NOTION_DATABASE_ID=一店 Notion 数据库 ID
ERP_USERNAME=你的 ERP 账号或手机号
ERP_PASSWORD=你的 ERP 密码
```

说明：

- `.env` 已加入 `.gitignore`，不会上传 GitHub。
- ERP 账号密码只放在 `.env`，不要写进代码。
- 如果 ERP 登录态过期，脚本会优先用 `.env` 的账号密码自动登录。
- 自动登录失败时，才会退回到手动扫码/短信登录。

## 3. 桌面软件

桌面上有快捷方式：

```text
拼多多广告同步
```

双击后可以操作：

- `同步昨天`
- `同步单日`
- `同步日期范围`
- `重新登录并同步`
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

强制重新登录并同步：

```powershell
python main.py --date 2026-06-03 --store all --relogin
```

## 5. 自动登录逻辑

脚本会按这个顺序处理 ERP 登录：

1. 先使用 `.auth/session.json` 里的已有登录态。
2. 如果登录态过期，读取 `.env` 的 `ERP_USERNAME` 和 `ERP_PASSWORD` 自动登录。
3. 自动登录成功后，重新保存 `.auth/session.json`。
4. 如果账号密码自动登录失败，才弹出浏览器让人手动扫码/短信登录。

因此，只要 `.env` 里的 ERP 账号密码有效，以后 ERP 自动退出时不需要手动扫码。

## 6. Notion 写入逻辑

每条广告数据按下面三项判重：

```text
日期 + plan_id + 店铺
```

如果 Notion 里已存在，就更新；不存在，就新建。

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

每天 9 点会自动运行：

```powershell
python main.py --store all
```

如果 9 点电脑没开机，任务已设置为开机登录后尽快补跑。

如果 ERP 登录态过期，脚本会尝试账号密码自动登录。账号密码自动登录失败时，会自动弹出一个 PowerShell/浏览器窗口，让你处理手动登录。

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

- ERP 登录态过期：脚本会自动账号密码登录。
- Notion 网络失败：通常是电脑到 `api.notion.com` 连接不稳定，稍后重跑即可。
- GitHub 推送失败：通常是电脑连不上 `github.com`，本地提交仍然保存。

## 10. 安装依赖

新电脑第一次安装：

```powershell
cd D:\desktop\codex\guanggao
pip install -r requirements.txt
python -m playwright install chromium
```

如果是从 GitHub 重新拉代码，需要重新配置 `.env`，并重新跑一次同步让脚本生成 `.auth/session.json`。
