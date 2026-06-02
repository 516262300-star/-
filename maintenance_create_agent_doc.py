from __future__ import annotations

from datetime import datetime

from notion_sync import _notion_request


TARGET_PARENT_TITLE = "拼多多每日广告数据"
DOC_TITLE = "拼多多广告同步 Agent 使用说明"


def rich_text(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text}}]


def title_text(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text}}]


def paragraph(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": rich_text(text)},
    }


def heading(level: int, text: str) -> dict:
    block_type = f"heading_{level}"
    return {
        "object": "block",
        "type": block_type,
        block_type: {"rich_text": rich_text(text)},
    }


def bullet(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": rich_text(text)},
    }


def code(text: str, language: str = "plain text") -> dict:
    return {
        "object": "block",
        "type": "code",
        "code": {"rich_text": rich_text(text), "language": language},
    }


def extract_title(item: dict) -> str:
    properties = item.get("properties") or {}
    for prop in properties.values():
        if prop.get("type") == "title":
            return "".join(part.get("plain_text", "") for part in prop.get("title", []))
    return ""


def search_parent_page() -> dict:
    response = _notion_request(
        "POST",
        "/search",
        payload={
            "query": TARGET_PARENT_TITLE,
            "filter": {"property": "object", "value": "page"},
            "page_size": 20,
        },
    )
    pages = response.get("results", [])
    exact_matches = [page for page in pages if extract_title(page) == TARGET_PARENT_TITLE]
    if exact_matches:
        return exact_matches[0]
    if pages:
        return pages[0]
    raise RuntimeError(f"没有找到 Notion 页面：{TARGET_PARENT_TITLE}")


def build_blocks() -> list[dict]:
    return [
        paragraph(f"更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"),
        paragraph("这页用于记录当前 Codex Agent 维护的拼多多广告数据同步脚本，方便以后不用重新解释环境和逻辑。"),
        heading(2, "1. 本机环境"),
        bullet("电脑用户：lds"),
        bullet("项目路径：D:\\desktop\\codex\\guanggao"),
        bullet("Python：C:\\Users\\lds\\AppData\\Local\\Programs\\Python\\Python312\\python.exe"),
        bullet("系统：Windows，使用 PowerShell 运行脚本"),
        bullet("ERP 登录态：保存在 .auth\\session.json"),
        bullet("日志和调试文件：保存在 debug 目录"),
        bullet("敏感配置：.env，里面有 NOTION_TOKEN 和 NOTION_DATABASE_ID；不要上传或发给别人"),
        heading(2, "2. 主要文件"),
        bullet("main.py：主入口，负责命令行参数、日期范围、店铺循环、失败通知"),
        bullet("erp_client.py：负责登录 ERP、抓取广告 HTML、解析分页和表格"),
        bullet("notion_sync.py：负责字段映射、去重、写入 Notion、广告类型和商品ID识别"),
        bullet("stores.py：一到七店的 ERP 店铺 ID 和 Notion 数据库 ID 映射"),
        bullet("run_daily.ps1：Windows 定时任务每天实际执行的脚本"),
        bullet("maintenance_fill_product_id.py：维护脚本，用来回填 Notion 里空着的商品ID"),
        heading(2, "3. Notion 数据库"),
        bullet("一店：拼多多一店-每日广告数据，ERP store=22"),
        bullet("二店：拼多多二店-每日广告数据，ERP store=222"),
        bullet("三店：拼多多三店-每日广告数据，ERP store=223"),
        bullet("四店：拼多多四店-每日广告数据，ERP store=224"),
        bullet("五店：拼多多五店-每日广告数据，ERP store=225"),
        bullet("六店：拼多多六店-每日广告数据，ERP store=226"),
        bullet("七店：拼多多七店-每日广告数据，ERP store=227"),
        bullet("Notion 去重规则：日期 + plan_id + 店铺"),
        bullet("点击率、转化率按百分比小数写入，比如 0.04 在 Notion 显示为 4%"),
        heading(2, "4. 常用命令"),
        code("cd D:\\desktop\\codex\\guanggao", "powershell"),
        paragraph("手动同步昨天一到七店："),
        code("& 'C:\\Users\\lds\\AppData\\Local\\Programs\\Python\\Python312\\python.exe' main.py --store all", "powershell"),
        paragraph("同步指定日期一到七店："),
        code("& 'C:\\Users\\lds\\AppData\\Local\\Programs\\Python\\Python312\\python.exe' main.py --date 2026-05-31 --store all", "powershell"),
        paragraph("同步指定日期范围一到七店："),
        code("& 'C:\\Users\\lds\\AppData\\Local\\Programs\\Python\\Python312\\python.exe' main.py --range 2026-05-25~2026-05-31 --store all", "powershell"),
        paragraph("只检查抓取结果，不写 Notion："),
        code("& 'C:\\Users\\lds\\AppData\\Local\\Programs\\Python\\Python312\\python.exe' main.py --date 2026-05-31 --store all --dry-run", "powershell"),
        paragraph("ERP 登录掉线时，强制重新扫码/短信登录："),
        code("& 'C:\\Users\\lds\\AppData\\Local\\Programs\\Python\\Python312\\python.exe' main.py --relogin --store all", "powershell"),
        paragraph("回填商品ID："),
        code("& 'C:\\Users\\lds\\AppData\\Local\\Programs\\Python\\Python312\\python.exe' maintenance_fill_product_id.py --range 2026-05-25~2026-05-31 --store all", "powershell"),
        paragraph("保存代码到 GitHub："),
        code("git status\ngit add .\ngit commit -m \"说明这次改了什么\"\ngit push", "powershell"),
        heading(2, "5. 每天自动运行"),
        bullet("Windows 任务计划名称：拼多多广告数据同步到 Notion"),
        bullet("执行时间：每天 09:00"),
        bullet("执行文件：D:\\desktop\\codex\\guanggao\\run_daily.ps1"),
        bullet("实际命令：python main.py --store all"),
        bullet("如果早上 9 点电脑没开机，任务已配置为错过后尽快补跑，但仍建议当天打开 Notion 看一下是否有当天数据"),
        heading(2, "6. 同步逻辑"),
        bullet("默认日期：不传日期时抓昨天，按 Asia/Shanghai 时区计算"),
        bullet("抓取方式：用 ERP 登录态 cookie，通过 requests 获取广告页面 HTML"),
        bullet("ERP 页面：admanager?action=ad_pdd_data&platform=22&store=店铺ID&begin_date=日期&end_date=日期&page=页码"),
        bullet("分页：自动识别页数，逐页抓取，每个广告计划一行"),
        bullet("写入：先查询 Notion 现有记录，再按 日期 + plan_id + 店铺 判断更新还是新建"),
        bullet("广告类型：广告计划名包含“全店托管”则写全店托管；否则有 ID 或 plan_id 则写稳定成本"),
        bullet("商品ID：只给稳定成本广告填写，从广告计划名里的“商品ID/ID”后面提取数字"),
        bullet("失败通知：同步失败会尝试在 Notion 里 @金博敏；包括 ERP 登录掉线、Notion 写入失败、网络异常等"),
        heading(2, "7. 后续维护原则"),
        bullet("如果只是新增广告计划，不用改代码，脚本会自动按 plan_id 去重写入"),
        bullet("如果 ERP 或 Notion 改了字段名，需要先 dry-run，看解析行数和字段是否正常"),
        bullet("如果 Notion 商品ID为空，可以运行 maintenance_fill_product_id.py 回填"),
        bullet("如果 GitHub 推送失败，通常是网络或代理问题；本地提交不等于已经同步到 GitHub"),
    ]


def main() -> None:
    parent = search_parent_page()
    parent_id = parent["id"]
    page = _notion_request(
        "POST",
        "/pages",
        payload={
            "parent": {"page_id": parent_id},
            "icon": {"type": "emoji", "emoji": "📌"},
            "properties": {"title": {"title": title_text(DOC_TITLE)}},
            "children": build_blocks(),
        },
    )
    print(f"已创建：{page.get('url')}")


if __name__ == "__main__":
    main()
