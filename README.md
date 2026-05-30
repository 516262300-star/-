# 拼多多一店广告数据同步到 Notion

这个项目用于从公司 ERP 抓取拼多多一店广告数据，并同步到 Notion 数据库：

- Notion 数据库：`拼多多一店-每日广告数据`
- ERP 店铺：`store=22`，即 `1店：利德仕官方旗舰店`
- 判重规则：`日期 + plan_id + 店铺`

## 1. 安装依赖

在项目目录打开 PowerShell：

```powershell
cd D:\desktop\codex\guanggao
pip install -r requirements.txt
playwright install chromium
```

如果 `playwright` 命令找不到，可以用：

```powershell
python -m playwright install chromium
```

## 2. 配置 .env

项目根目录需要有 `.env` 文件，内容如下：

```env
NOTION_TOKEN=你的 Notion integration token
NOTION_DATABASE_ID=你的 Notion 数据库 ID
```

注意：

- `.env` 不要发给别人。
- `.env` 已经在 `.gitignore` 里，不会提交。
- 当前数据库已添加 `plan_id` 和 `店铺` 两列，用于防重复。

## 3. 第一次登录 ERP

第一次运行时，如果登录态失效，脚本会自动打开浏览器。

你只需要：

1. 在浏览器里扫码或短信登录 ERP。
2. 登录完成后回到 PowerShell。
3. 按一次回车。

登录态会保存到：

```text
.auth/session.json
```

后面如果 cookie 没过期，就不需要重复扫码。

## 4. 手动运行

抓昨天的数据并写入 Notion：

```powershell
python main.py
```

抓指定单日：

```powershell
python main.py --date 2026-05-29
```

抓日期范围：

```powershell
python main.py --range 2026-05-01~2026-05-29
```

强制重新登录：

```powershell
python main.py --relogin
```

只检查抓取和解析，不写入 Notion：

```powershell
python main.py --date 2026-05-29 --dry-run
```

## 5. 字段或广告计划变动时怎么办

如果只是 ERP 里新增广告计划，或者广告计划名称改了，通常不用改脚本。

原因是脚本用下面三项判重：

```text
日期 + plan_id + 店铺
```

如果 ERP 新增了列、删除了列、改了按钮逻辑，先运行：

```powershell
python main.py --date 有数据的日期 --dry-run
```

确认日志里解析行数正常，再正式运行：

```powershell
python main.py --date 有数据的日期
```

## 6. Windows 任务计划程序

目标：每天早上 9 点自动同步昨天的数据。

### 创建任务

1. 打开 Windows 搜索，输入 `任务计划程序`。
2. 点击右侧 `创建基本任务...`。
3. 名称填写：

```text
拼多多广告数据同步到 Notion
```

4. 触发器选择 `每天`。
5. 时间设置为 `09:00:00`。
6. 操作选择 `启动程序`。

### 程序配置

程序或脚本填写你的 Python 路径，例如：

```text
C:\Users\lds\AppData\Local\Programs\Python\Python312\python.exe
```

添加参数填写：

```text
main.py
```

起始于填写项目目录：

```text
D:\desktop\codex\guanggao
```

这样每天 9 点会自动运行：

```powershell
python main.py
```

也就是默认抓昨天的数据。

## 7. 日常检查

如果同步后想确认结果：

1. 打开 Notion 数据库 `拼多多一店-每日广告数据`。
2. 筛选昨天日期。
3. 看 `广告计划`、`plan_id`、`花费`、`点击率`、`转化率`、`广告成交金额` 是否正常。

如果发现 ERP 登录过期，手动运行一次：

```powershell
python main.py --relogin
```

扫码登录后，后续任务计划会继续使用新的登录态。

## 8. 登录掉线通知

每天 9 点的定时任务如果同步失败，会停止任务，并在 Notion 页面里评论提醒金博敏。

登录态失效时会提醒：

```text
@金博敏 ERP 拼多多广告数据同步失败：ERP 登录态已失效，需要重新扫码或短信登录。
```

其他失败也会提醒，例如 ERP 抓取失败、Notion 写入失败、字段解析异常等，提醒里会包含日期范围和错误原因。

收到提醒后，在电脑上手动运行：

```powershell
cd D:\desktop\codex\guanggao
python main.py --relogin
```

完成扫码或短信登录后，后续定时任务会继续自动同步。
