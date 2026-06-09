from __future__ import annotations

from datetime import datetime

from notion_sync import _notion_request


PAGE_ID = "3737db4d-c72f-8196-831a-c46c8e4ae6c2"
DOC_TITLE = "拼多多广告同步 Agent 使用说明"


def rich_text(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text}}]


def paragraph(text: str) -> dict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": rich_text(text)}}


def heading(level: int, text: str) -> dict:
    block_type = f"heading_{level}"
    return {"object": "block", "type": block_type, block_type: {"rich_text": rich_text(text)}}


def bullet(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": rich_text(text)},
    }


def code(text: str, language: str = "plain text") -> dict:
    return {"object": "block", "type": "code", "code": {"rich_text": rich_text(text), "language": language}}


def build_blocks() -> list[dict]:
    return [
        paragraph(f"更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"),
        paragraph("这是一份给日常运营和后续 Codex Agent 使用的完整说明。目标是：每天把 ERP 里的拼多多一到七店广告数据自动同步到 Notion；如果 9 点电脑没开机，后面开机后自动补跑；如果 Notion 里昨天缺数据，也会自动补上。"),
        heading(2, "1. 先看结论"),
        bullet("平时不需要手动操作。电脑开机并登录 Windows 后，系统会通过 Windows 任务计划自动检查昨天数据。"),
        bullet("每天 9 点会自动跑；如果 9 点电脑没开机，后面开机登录后会尽快补跑。"),
        bullet("补跑不是盲目重复登记，而是先检查 Notion：哪个店昨天没有数据，才补哪个店。"),
        bullet("同步写入时仍按“日期 + plan_id + 店铺”去重，所以同一天重复运行不会重复登记。"),
        bullet("ERP 登录过期时，会先用 .env 里的 ERP 账号密码自动登录；只有账号密码失败时才需要人工扫码或短信登录。"),
        bullet("如果同步失败，脚本会在 Notion 里提醒 @金博敏，并在 debug 日志里留下错误原因。"),
        bullet("Notion 写入阶段会显示读取字段、读取已有数据、写入第几行；临时网络断开但重试成功时不再刷 WARNING，只有全部重试失败才报警。"),
        heading(2, "2. 日常怎么用"),
        paragraph("正常情况："),
        bullet("每天早上只需要打开电脑并登录 Windows。"),
        bullet("如果 9 点电脑已经开着，会在 9 点自动同步昨天数据。"),
        bullet("如果 9 点电脑没开机，后面开机登录后，任务计划会尽快补跑昨天数据。"),
        bullet("你可以打开一到七店 Notion 数据库，按昨天日期筛选，确认是否已有数据。"),
        paragraph("手动补一天数据："),
        bullet("双击桌面快捷方式“拼多多广告同步”。"),
        bullet("在“单日日期”里填日期，例如 2026-06-04。"),
        bullet("店铺选 all，表示一到七店全部处理。"),
        bullet("点“同步单日”。"),
        paragraph("只检查不写入："),
        bullet("桌面软件勾选“只检查，不写入 Notion”，再点同步按钮。"),
        bullet("这个模式适合检查 ERP 能不能抓到数据，不会改 Notion。"),
        heading(2, "3. 自动补漏逻辑"),
        bullet("自动补漏脚本是 catchup_daily.py。"),
        bullet("每天定时任务会调用 catchup_daily.py，而不是直接无条件写入。"),
        bullet("它会先逐个检查一到七店 Notion 数据库，判断昨天是否至少有一条广告数据。"),
        bullet("如果某个店昨天已经有数据，就跳过这个店。"),
        bullet("如果某个店昨天没有数据，就抓这个店昨天的 ERP 广告数据并写入对应 Notion 数据库。"),
        bullet("如果 ERP 某个店昨天本身没有广告数据，日志会显示抓取 0 行；这种情况需要结合 ERP 页面确认。"),
        bullet("如果同步过程中 Notion 网络失败，稍后再运行 catchup_daily.py 即可；已有数据会跳过，缺失数据会继续补。"),
        bullet("如果 Notion 新建页面时回包断开，脚本会先按“日期 + plan_id + 店铺”反查是否已经创建，避免重复登记。"),
        bullet("如果某个店 Notion 连续失败，脚本会保存这个店尚未写入的行到 debug\\pending_notion，并继续处理后面的店铺。"),
        paragraph("定时任务实际执行的是："),
        code("python catchup_daily.py --date 昨天 --store all", "powershell"),
        paragraph("手动检查昨天是否缺数据，缺少才补跑："),
        code("cd D:\\desktop\\codex\\guanggao\npython catchup_daily.py --store all", "powershell"),
        paragraph("手动检查指定日期是否缺数据，缺少才补跑："),
        code("python catchup_daily.py --date 2026-06-04 --store all", "powershell"),
        paragraph("只检查缺失情况，不写入 Notion："),
        code("python catchup_daily.py --date 2026-06-04 --store all --dry-run", "powershell"),
        heading(2, "4. 桌面软件"),
        bullet("桌面快捷方式名称：拼多多广告同步。"),
        bullet("软件文件：D:\\desktop\\codex\\guanggao\\desktop_app.py。"),
        bullet("启动批处理：D:\\desktop\\codex\\guanggao\\启动拼多多广告同步.bat。"),
        bullet("“同步昨天”：同步昨天一到七店，适合临时手动补昨天。"),
        bullet("“同步单日”：同步输入框里的某一天。"),
        bullet("“同步日期范围”：同步开始日期到结束日期之间的所有数据。"),
        bullet("“重新登录并同步”：强制重新走登录流程；现在会先尝试 ERP 账号密码自动登录，失败才需要扫码/短信。"),
        bullet("“只检查，不写入 Notion”：用于测试 ERP 抓取和解析，不会修改 Notion。"),
        bullet("“打开日志文件夹”：打开 debug 目录，看任务日志和解析结果。"),
        bullet("“停止当前运行”：停止桌面软件当前启动的同步进程。"),
        heading(2, "5. ERP 登录逻辑"),
        bullet("正常情况下先使用 .auth\\session.json 里的登录态。"),
        bullet("如果登录态过期，脚本读取 .env 的 ERP_USERNAME 和 ERP_PASSWORD 自动登录。"),
        bullet("自动登录成功后，会重新保存 .auth\\session.json，下次继续复用。"),
        bullet("只有 .env 没有账号密码、账号密码错误、账号权限不够，才需要手动扫码或短信登录。"),
        bullet(".env 是敏感文件，不能上传 GitHub，也不要发给别人。"),
        code("ERP_USERNAME=你的ERP账号或手机号\nERP_PASSWORD=你的ERP密码", "plain text"),
        heading(2, "6. Notion 数据库"),
        bullet("一店：拼多多一店-每日广告数据，ERP store=22"),
        bullet("二店：拼多多二店-每日广告数据，ERP store=222"),
        bullet("三店：拼多多三店-每日广告数据，ERP store=223"),
        bullet("四店：拼多多四店-每日广告数据，ERP store=224"),
        bullet("五店：拼多多五店-每日广告数据，ERP store=225"),
        bullet("六店：拼多多六店-每日广告数据，ERP store=226"),
        bullet("七店：拼多多七店-每日广告数据，ERP store=227"),
        bullet("每个店对应一个独立 Notion 数据库。"),
        bullet("Notion 去重规则：日期 + plan_id + 店铺。"),
        bullet("同一条广告数据如果已经存在，脚本会 update；不存在才 create。"),
        bullet("写入前会先按日期范围读取 Notion 已有数据用于去重；现在每页读取 100 条，避免长时间无输出。"),
        bullet("Notion API 请求会自动记住可用线路，并在 SSL/连接中断时重试。"),
        bullet("如果某一路网络临时断开但后续重试成功，日志只记录为普通进度；只有全部重试都失败时，才会显示 Notion 请求失败的 WARNING。"),
        bullet("如果 Notion 读取已有数据或写入中断，脚本会把尚未写入的行保存到 debug\\pending_notion，避免数据丢失。"),
        bullet("数据库列顺序和格式已经按之前确认的模板设置。"),
        heading(2, "7. 写入字段规则"),
        bullet("广告计划：从 ERP 表格广告计划列读取。"),
        bullet("日期：使用 ERP 数据日期，也就是 make_time。"),
        bullet("广告类型：计划名包含“全店托管”则写“全店托管”；其他带 ID 或 plan_id 的计划写“稳定成本”。"),
        bullet("商品ID：只给稳定成本广告填写，从广告计划名里的“商品ID”或“ID”后面提取数字。"),
        bullet("花费、平均点击花费、投产比、曝光量、成交笔数、每笔成交花费、每笔成交金额、广告成交金额：按 ERP 表格数值写入。"),
        bullet("点击率、转化率、推广曝光占比：写入 Notion 时存小数。"),
        paragraph("百分比示例：ERP 显示 13.66%，脚本写入 0.1366，Notion 显示 13.66%。"),
        bullet("空值会写 None，不会乱填 0。"),
        bullet("ERP 表格新增列时，脚本不会自动乱写；需要代码里明确映射后才写入 Notion。"),
        heading(2, "8. 常用手动命令"),
        paragraph("先进入项目目录："),
        code("cd D:\\desktop\\codex\\guanggao", "powershell"),
        paragraph("同步昨天一到七店："),
        code("python main.py --store all", "powershell"),
        paragraph("同步指定日期一到七店："),
        code("python main.py --date 2026-06-03 --store all", "powershell"),
        paragraph("同步日期范围："),
        code("python main.py --range 2026-05-25~2026-05-31 --store all", "powershell"),
        paragraph("只检查 ERP 抓取和解析，不写 Notion："),
        code("python main.py --date 2026-06-03 --store all --dry-run", "powershell"),
        paragraph("强制重新登录并同步指定日期："),
        code("python main.py --date 2026-06-03 --store all --relogin", "powershell"),
        paragraph("只跑一个店，例如二店："),
        code("python main.py --date 2026-06-03 --store 222", "powershell"),
        paragraph("跑多个指定店，例如二店和三店："),
        code("python main.py --date 2026-06-03 --store 222,223", "powershell"),
        heading(2, "9. 每天 9 点自动任务"),
        bullet("Windows 任务计划名称：拼多多广告数据同步到 Notion"),
        bullet("执行文件：D:\\desktop\\codex\\guanggao\\run_daily.ps1"),
        bullet("实际命令：python catchup_daily.py --date 昨天 --store all"),
        bullet("任务设置 StartWhenAvailable=True：如果 9 点电脑没开机，后面开机登录 Windows 后会尽快补跑。"),
        bullet("任务设置 WakeToRun=True：系统允许时可以唤醒电脑执行。"),
        bullet("任务允许电池运行：DisallowStartIfOnBatteries=False，StopIfGoingOnBatteries=False。"),
        bullet("如果 ERP 登录过期，会优先账号密码自动登录，不再默认要求扫码。"),
        bullet("如果账号密码自动登录失败，定时脚本会打开重新登录窗口，并在 Notion 里提醒。"),
        heading(2, "10. 如何确认今天有没有成功"),
        bullet("打开一到七店任意一个 Notion 广告数据库。"),
        bullet("筛选日期等于昨天。"),
        bullet("如果能看到广告计划行，表示这个店昨天数据已登记。"),
        bullet("也可以打开 debug 日志，看最新 task_YYYYMMDD_HHMMSS.log。"),
        bullet("日志里出现“补漏检查完成：Notion 已有 YYYY-MM-DD 的全部店铺数据，无需补跑”，表示检查通过。"),
        bullet("日志里出现“补漏完成：YYYY-MM-DD，共抓取 X 行，新增 X 行”，表示刚刚补写成功。"),
        heading(2, "11. 日志文件"),
        bullet("日志目录：D:\\desktop\\codex\\guanggao\\debug"),
        bullet("定时任务日志：task_YYYYMMDD_HHMMSS.log"),
        bullet("最近一次 ERP 解析结果：parsed_rows_current.json"),
        bullet("如果要排查某天数据，先看对应时间的 task 日志。"),
        bullet("如果日志中文乱码，run_daily.ps1 已设置 UTF-8；新日志应该正常显示中文。"),
        heading(2, "12. 常见问题"),
        paragraph("9 点电脑没开机怎么办？"),
        bullet("不用手动处理。任务计划已设置错过后尽快运行，开机登录 Windows 后会补跑。"),
        paragraph("Notion 里昨天没有数据怎么办？"),
        bullet("运行 python catchup_daily.py --store all，它会先查 Notion，缺哪个店补哪个店。"),
        paragraph("ERP 账号退出了怎么办？"),
        bullet("脚本会用 .env 的 ERP_USERNAME / ERP_PASSWORD 自动登录。自动登录失败时再人工处理。"),
        paragraph("Notion 网络失败怎么办？"),
        bullet("稍后重跑 catchup_daily.py。因为有去重和缺失检查，不会重复登记。"),
        bullet("如果日志里看到 POST /pages 的 SSL 或 EOF 错误，表示已经进入 Notion 新建页面阶段，是网络回包中断；重跑会先反查已创建页面。"),
        bullet("如果日志停在“读取 Notion 数据库字段”或“读取 Notion 已有数据用于去重”，优先检查电脑到 api.notion.com 的网络或代理。"),
        bullet("如果日志只显示某个店“缺少数据，准备补跑”，但实际同步抓取 0 行，通常表示 ERP 当天这个店没有广告行，不是 Notion 写入失败。"),
        bullet("如果日志显示“Notion 待补写数据已保存”，网络恢复后重新跑同一天同店即可；脚本会按去重规则写入或更新。"),
        paragraph("ERP 后台还没登记全店托管数据怎么办？"),
        bullet("等 ERP 补好后，重新跑对应日期即可；已存在的稳定成本会更新，缺少的全店托管会新增。"),
        paragraph("某个店以后改名怎么办？"),
        bullet("如果只是 Notion 页面名字改了，通常不影响同步；如果 ERP store ID 或 Notion database/data_source ID 变了，需要改 stores.py。"),
        paragraph("ERP 表格新增列怎么办？"),
        bullet("先不要乱填 Notion。让 Agent 查看 ERP HTML 表头、确认 Notion 列名和类型，再在 notion_sync.py 里新增映射。"),
        heading(2, "13. 本机环境和路径"),
        bullet("项目路径：D:\\desktop\\codex\\guanggao"),
        bullet("Python：C:\\Users\\lds\\AppData\\Local\\Programs\\Python\\Python312\\python.exe"),
        bullet("系统：Windows，使用 PowerShell 和 Windows 任务计划程序"),
        bullet("桌面入口：桌面快捷方式“拼多多广告同步”"),
        bullet("ERP 登录态：D:\\desktop\\codex\\guanggao\\.auth\\session.json"),
        bullet("敏感配置：D:\\desktop\\codex\\guanggao\\.env"),
        bullet("日志目录：D:\\desktop\\codex\\guanggao\\debug"),
        heading(2, "14. 主要文件"),
        bullet("main.py：主入口，负责指定日期、日期范围、店铺循环、失败通知。"),
        bullet("catchup_daily.py：自动补漏入口，先查 Notion，缺数据才同步。"),
        bullet("erp_client.py：ERP 登录、账号密码自动登录、抓取广告 HTML、解析分页和表格。"),
        bullet("notion_sync.py：Notion 字段映射、去重、新建、更新、失败提醒、网络重试、创建后反查和待补写文件保存。"),
        bullet("stores.py：一到七店 ERP store ID 与 Notion database/data_source ID 映射。"),
        bullet("run_daily.ps1：每天 9 点任务计划实际调用的脚本。"),
        bullet("desktop_app.py：桌面控制面板。"),
        bullet("README.md：GitHub 上的项目说明。"),
        heading(2, "15. GitHub 和备份"),
        bullet("GitHub 仓库：https://github.com/516262300-star/-.git"),
        bullet("代码已提交到 GitHub，但 .env、.auth、debug 不会上传。"),
        bullet("如果换电脑，需要从 GitHub 拉代码，然后重新配置 .env。"),
        bullet("如果修改了代码，确认测试通过后运行 git add、git commit、git push 保存。"),
        paragraph("常用保存命令："),
        code("cd D:\\desktop\\codex\\guanggao\ngit status --short --branch\ngit add .\ngit commit -m \"说明本次修改\"\ngit push", "powershell"),
        heading(2, "16. 给后续 Agent 的处理建议"),
        bullet("先读取这页说明、README.md、main.py、catchup_daily.py、notion_sync.py、erp_client.py、stores.py。"),
        bullet("不要打印或上传 .env 内容；只检查是否配置，不要展示 token 或密码。"),
        bullet("涉及 Notion 字段变更时，先查询数据库 schema，再改映射。"),
        bullet("涉及 ERP 页面变更时，先 dry-run 抓 HTML 和表头，再改解析逻辑。"),
        bullet("涉及定时任务时，检查 Windows 任务计划“拼多多广告数据同步到 Notion”的设置和 run_daily.ps1。"),
        bullet("每次改完脚本代码要 py_compile、dry-run 或小范围实际测试，再更新这页 Notion 使用说明，并提交 GitHub。"),
    ]


def archive_existing_children(page_id: str) -> None:
    cursor = None
    archived_count = 0
    while True:
        path = f"/blocks/{page_id}/children?page_size=100"
        if cursor:
            path += f"&start_cursor={cursor}"
        response = _notion_request("GET", path)
        for block in response.get("results", []):
            _notion_request("PATCH", f"/blocks/{block['id']}", payload={"archived": True})
            archived_count += 1
            if archived_count % 10 == 0:
                print(f"已归档旧内容 {archived_count} 个块", flush=True)
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")
    print(f"旧内容归档完成：{archived_count} 个块", flush=True)


def append_children(page_id: str, blocks: list[dict]) -> None:
    for index in range(0, len(blocks), 90):
        _notion_request(
            "PATCH",
            f"/blocks/{page_id}/children",
            payload={"children": blocks[index : index + 90]},
        )
        print(f"已写入新内容 {min(index + 90, len(blocks))}/{len(blocks)} 个块", flush=True)


def main() -> None:
    print("开始更新 Notion Agent 使用说明", flush=True)
    _notion_request(
        "PATCH",
        f"/pages/{PAGE_ID}",
        payload={
            "icon": {"type": "emoji", "emoji": "📌"},
            "properties": {"title": {"title": rich_text(DOC_TITLE)}},
        },
    )
    print("页面标题已更新", flush=True)
    archive_existing_children(PAGE_ID)
    append_children(PAGE_ID, build_blocks())
    print("已更新 Notion Agent 使用说明")


if __name__ == "__main__":
    main()
