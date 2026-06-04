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
        paragraph("这页记录当前 Codex Agent 维护的拼多多广告数据同步脚本，方便换账号或换电脑后继续维护。"),
        heading(2, "1. 本机环境"),
        bullet("项目路径：D:\\desktop\\codex\\guanggao"),
        bullet("Python：C:\\Users\\lds\\AppData\\Local\\Programs\\Python\\Python312\\python.exe"),
        bullet("系统：Windows，使用 PowerShell 和 Windows 任务计划程序"),
        bullet("桌面入口：桌面快捷方式“拼多多广告同步”"),
        bullet("日志目录：D:\\desktop\\codex\\guanggao\\debug"),
        bullet("ERP 登录态：.auth\\session.json"),
        bullet("敏感配置：.env，里面有 Notion token 和 ERP 账号密码；不要上传或发给别人"),
        heading(2, "2. 主要文件"),
        bullet("main.py：主入口，负责日期、店铺循环、失败通知"),
        bullet("erp_client.py：负责 ERP 自动登录、抓取广告 HTML、解析分页和表格"),
        bullet("notion_sync.py：负责 Notion 字段映射、去重、新建和更新"),
        bullet("stores.py：一到七店 ERP store ID 和 Notion 数据库 ID 映射"),
        bullet("run_daily.ps1：每天 9 点定时任务实际调用的脚本"),
        bullet("desktop_app.py：桌面控制面板"),
        heading(2, "3. ERP 登录逻辑"),
        bullet("正常情况下先使用 .auth\\session.json 里的登录态。"),
        bullet("如果 ERP 登录态过期，脚本会读取 .env 的 ERP_USERNAME 和 ERP_PASSWORD 自动登录。"),
        bullet("自动登录成功后，会重新保存 .auth\\session.json，下次继续复用。"),
        bullet("只有账号密码缺失或自动登录失败时，才需要手动扫码/短信登录。"),
        code("ERP_USERNAME=你的ERP账号或手机号\nERP_PASSWORD=你的ERP密码", "plain text"),
        heading(2, "4. Notion 数据库"),
        bullet("一店：拼多多一店-每日广告数据，ERP store=22"),
        bullet("二店：拼多多二店-每日广告数据，ERP store=222"),
        bullet("三店：拼多多三店-每日广告数据，ERP store=223"),
        bullet("四店：拼多多四店-每日广告数据，ERP store=224"),
        bullet("五店：拼多多五店-每日广告数据，ERP store=225"),
        bullet("六店：拼多多六店-每日广告数据，ERP store=226"),
        bullet("七店：拼多多七店-每日广告数据，ERP store=227"),
        bullet("Notion 去重规则：日期 + plan_id + 店铺"),
        heading(2, "5. 常用命令"),
        paragraph("同步昨天一到七店："),
        code("cd D:\\desktop\\codex\\guanggao\npython main.py --store all", "powershell"),
        paragraph("同步指定日期一到七店："),
        code("python main.py --date 2026-06-03 --store all", "powershell"),
        paragraph("同步日期范围："),
        code("python main.py --range 2026-05-25~2026-05-31 --store all", "powershell"),
        paragraph("只检查 ERP 抓取和解析，不写 Notion："),
        code("python main.py --date 2026-06-03 --store all --dry-run", "powershell"),
        paragraph("强制重新登录并同步："),
        code("python main.py --date 2026-06-03 --store all --relogin", "powershell"),
        heading(2, "6. 每天 9 点自动运行"),
        bullet("Windows 任务计划名称：拼多多广告数据同步到 Notion"),
        bullet("执行文件：D:\\desktop\\codex\\guanggao\\run_daily.ps1"),
        bullet("实际命令：python main.py --store all"),
        bullet("如果 9 点电脑没开机，登录 Windows 后会尽快补跑。"),
        bullet("如果 ERP 登录过期，会优先账号密码自动登录，不再默认要求扫码。"),
        bullet("如果自动登录失败，才会弹出窗口让人处理。"),
        heading(2, "7. 同步和字段逻辑"),
        bullet("默认日期：昨天，按 Asia/Shanghai 时区计算。"),
        bullet("分页：自动识别页数并逐页抓取，每个广告计划一行。"),
        bullet("写入：已存在则 update，不存在则 create。"),
        bullet("广告类型：计划名包含“全店托管”写全店托管；否则有 ID 或 plan_id 写稳定成本。"),
        bullet("商品ID：只给稳定成本广告填写，从计划名里的“商品ID/ID”后面提取数字。"),
        bullet("百分比字段写小数：点击率、转化率、推广曝光占比。"),
        paragraph("例如 ERP 是 13.66%，脚本写入 0.1366，Notion 显示为 13.66%。"),
        heading(2, "8. 日常处理"),
        bullet("日常建议直接双击桌面“拼多多广告同步”操作。"),
        bullet("如果 Notion 网络失败，稍后重跑同一天即可，脚本会去重。"),
        bullet("如果 GitHub 推送失败，通常是电脑连不上 github.com；本地提交仍然保存。"),
        bullet("如果换 Codex 账号，脚本仍在本机和 GitHub；让新 Agent 先看这页说明。"),
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
