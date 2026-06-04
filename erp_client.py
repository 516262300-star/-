from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
import requests

from config import ERP_PASSWORD, ERP_USERNAME
from stores import get_store


ERP_HOME_URL = "https://ldswj.net/leedis2/public/"
ERP_LOGIN_PAGE_URL = "https://ldswj.net/leedis/index.php/welcome/loginpage"
ERP_LOGIN_ACTION_URL = "https://ldswj.net/leedis/index.php/welcome/loginact"
ERP_PDD_AD_URL = (
    "https://ldswj.net/leedis2/public/admanager"
    "?action=ad_pdd_data&platform=22&store=22"
)
AD_DATA_URL_TEMPLATE = (
    "https://ldswj.net/leedis2/public/admanager"
    "?action=ad_pdd_data&platform=22&store=22"
    "&begin_date={date}&end_date={date}&page={page}"
)

AUTH_DIR = Path(".auth")
DEBUG_DIR = Path("debug")
SESSION_PATH = AUTH_DIR / "session.json"
CURRENT_URL_PATH = DEBUG_DIR / "current_url.txt"
ERP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0 Safari/537.36"
)

AD_FIELD_KEYS = [
    "record_id",
    "plan_id",
    "spend",
    "spend_average",
    "click_rate",
    "convert_rate",
    "collect_shop_count",
    "collect_goods_count",
    "roi",
    "impressions",
    "promotion_exposure_rate",
    "order_count",
    "cost_per_order",
    "amount_per_order",
    "amount_ad",
    "make_time",
]


class LoginRequiredError(RuntimeError):
    pass


def build_ad_data_url(date: str, page: int = 1) -> str:
    return AD_DATA_URL_TEMPLATE.format(date=date, page=page)


def build_pdd_ad_url(
    begin_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
    store: str = "22",
) -> str:
    params = {
        "action": "ad_pdd_data",
        "platform": "22",
        "store": store,
        "page": str(page),
    }
    if begin_date:
        params["begin_date"] = begin_date
    if end_date:
        params["end_date"] = end_date

    return f"https://ldswj.net/leedis2/public/admanager?{urlencode(params)}"


def capture_first_page_html(date: str = "2026-05-27") -> Path:
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    output_path = DEBUG_DIR / f"page_{date}_p1.html"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto(ERP_PDD_AD_URL, wait_until="domcontentloaded")
        print("请在浏览器里扫码或短信登录。")
        print("登录完成后回到终端按回车，脚本会自动打开拼多多广告数据页面。")
        input()

        page.goto(ERP_PDD_AD_URL, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            pass

        html = page.content()
        output_path.write_text(html, encoding="utf-8")
        CURRENT_URL_PATH.write_text(page.url, encoding="utf-8")
        context.storage_state(path=str(SESSION_PATH))

        browser.close()

    return output_path


def _clean_cell_text(value: str) -> str:
    return " ".join(value.split())


def _extract_row_texts(cells: Iterable) -> list[str]:
    return [_clean_cell_text(cell.get_text(" ", strip=True)) for cell in cells]


def _extract_page_message(soup: BeautifulSoup) -> str | None:
    text_box = soup.find(id="text")
    if text_box is None:
        return None

    message = _clean_cell_text(text_box.get_text(" ", strip=True))
    return message or None


def _get_data_table(soup: BeautifulSoup):
    return soup.find("table", id="tabSpec")


def _extract_on_edit_args(row) -> list[str]:
    button = row.find("button", onclick=re.compile(r"onEditData\("))
    if button is None:
        return []

    onclick = button.get("onclick", "")
    match = re.search(r"onEditData\((.*?)\)", onclick)
    if match is None:
        return []

    return re.findall(r"'([^']*)'", match.group(1))


def _normalize_row(headers: list[str], values: list[str], edit_args: list[str]) -> dict:
    row = {header: value for header, value in zip(headers, values)}

    for key, value in zip(AD_FIELD_KEYS, edit_args):
        row[key] = value

    if "广告计划" in row and "plan_name" not in row:
        row["plan_name"] = row["广告计划"]

    if "日期" in row and "make_time" not in row:
        row["make_time"] = row["日期"]

    return row


def parse_ad_table(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    table = _get_data_table(soup)
    if table is None:
        return []

    headers = _extract_row_texts(table.select("thead th"))
    rows: list[dict] = []

    for tr in table.select("tbody tr"):
        values = _extract_row_texts(tr.find_all("td"))
        if not any(values):
            continue

        # 最后一列是“操作”，里面是按钮，不作为可见字段保存。
        visible_values = values[: len(headers)]
        edit_args = _extract_on_edit_args(tr)
        rows.append(_normalize_row(headers, visible_values, edit_args))

    return rows


def is_login_page(html: str, url: str = "") -> bool:
    lowered_url = url.lower()
    if "login" in lowered_url or "welcome/loginpage" in lowered_url:
        return True

    soup = BeautifulSoup(html, "lxml")
    title = _clean_cell_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    text = _clean_cell_text(soup.get_text(" ", strip=True))

    return (
        "登录" in title
        or "扫码" in text
        or "短信登录" in text
        or "wxLogin" in html
    )


def get_next_page_url(html: str, current_url: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    next_link = soup.select_one('ul.pagination a[rel="next"]')
    if next_link and next_link.get("href"):
        return urljoin(current_url, next_link["href"])

    for link in soup.select("ul.pagination a.page-link"):
        label = _clean_cell_text(link.get_text(" ", strip=True))
        if label in {"下一页", "Next", ">"} and link.get("href"):
            return urljoin(current_url, link["href"])

    return None


def get_total_pages(html: str) -> int:
    soup = BeautifulSoup(html, "lxml")
    text = _clean_cell_text(soup.get_text(" ", strip=True))
    match = re.search(r"(\d+)\s*/\s*(\d+)", text)
    if match:
        return int(match.group(2))

    pages = []
    for link in soup.select("ul.pagination a.page-link"):
        label = _clean_cell_text(link.get_text(" ", strip=True))
        if label.isdigit():
            pages.append(int(label))

    return max(pages, default=1)


def _set_query_param(url: str, key: str, value: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    query[key] = [value]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def _load_storage_state_cookies() -> list[dict]:
    if not SESSION_PATH.exists():
        return []

    data = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
    return data.get("cookies", [])


def build_requests_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": ERP_USER_AGENT})

    for cookie in _load_storage_state_cookies():
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain"),
            path=cookie.get("path", "/"),
        )

    return session


def has_password_login_config() -> bool:
    return bool(ERP_USERNAME and ERP_PASSWORD)


def _save_session_cookies(session: requests.Session) -> None:
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    cookies = []
    for cookie in session.cookies:
        cookies.append(
            {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain or "ldswj.net",
                "path": cookie.path or "/",
                "expires": cookie.expires or -1,
                "httpOnly": bool(cookie.has_nonstandard_attr("HttpOnly")),
                "secure": bool(cookie.secure),
                "sameSite": "Lax",
            }
        )

    SESSION_PATH.write_text(json.dumps({"cookies": cookies}, indent=2), encoding="utf-8")


def password_login() -> None:
    if not has_password_login_config():
        raise LoginRequiredError("ERP 登录态已失效，且 .env 未配置 ERP_USERNAME / ERP_PASSWORD。")

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": ERP_USER_AGENT,
            "Referer": ERP_LOGIN_PAGE_URL,
            "X-Requested-With": "XMLHttpRequest",
        }
    )

    session.get(ERP_LOGIN_PAGE_URL, timeout=30)
    response = session.post(
        ERP_LOGIN_ACTION_URL,
        data={"phone": ERP_USERNAME, "password": ERP_PASSWORD},
        timeout=30,
    )
    response.raise_for_status()

    result = response.text.strip()
    if result != "1":
        raise LoginRequiredError(f"ERP 账号密码自动登录失败，接口返回：{result[:80]}")

    html, final_url = _request_html(session, ERP_PDD_AD_URL)
    if is_login_page(html, final_url):
        raise LoginRequiredError("ERP 账号密码自动登录后仍然停留在登录页，请检查账号密码或账号权限。")

    _save_session_cookies(session)
    CURRENT_URL_PATH.write_text(final_url, encoding="utf-8")
    logging.info("ERP 账号密码自动登录成功，登录态已保存到 %s", SESSION_PATH)


def relogin() -> None:
    if has_password_login_config():
        try:
            password_login()
            return
        except LoginRequiredError as exc:
            logging.warning("ERP 账号密码自动登录失败，改用手动登录：%s", exc)

    AUTH_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(ERP_PDD_AD_URL, wait_until="domcontentloaded")
        print("登录态失效，请在浏览器里扫码或短信登录，登录完成后回到终端按回车")
        input()
        page.goto(ERP_PDD_AD_URL, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            pass
        context.storage_state(path=str(SESSION_PATH))
        CURRENT_URL_PATH.write_text(page.url, encoding="utf-8")
        browser.close()


def _request_html(session: requests.Session, url: str) -> tuple[str, str]:
    response = session.get(url, timeout=30, allow_redirects=True)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def fetch_html_with_login(url: str, *, allow_relogin: bool = False) -> tuple[str, str]:
    session = build_requests_session()
    html, final_url = _request_html(session, url)
    if not is_login_page(html, final_url):
        return html, final_url

    if has_password_login_config():
        password_login()
        session = build_requests_session()
        html, final_url = _request_html(session, url)
        if not is_login_page(html, final_url):
            return html, final_url

    if not allow_relogin:
        raise LoginRequiredError("ERP 登录态已失效，账号密码自动登录也没有成功。")

    relogin()
    session = build_requests_session()
    html, final_url = _request_html(session, url)
    if is_login_page(html, final_url):
        raise LoginRequiredError("重新登录后仍然没有进入广告数据页，请检查账号权限或登录状态。")

    return html, final_url


def fetch_all_ad_pages(start_url: str) -> list[dict]:
    all_rows: list[dict] = []
    current_url = start_url
    page_index = 1

    while current_url:
        html, final_url = fetch_html_with_login(current_url, allow_relogin=True)
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        (DEBUG_DIR / f"page_step_b_p{page_index}.html").write_text(html, encoding="utf-8")

        rows = parse_ad_table(html)
        print(f"第 {page_index} 页：解析到 {len(rows)} 行")
        all_rows.extend(rows)

        next_url = get_next_page_url(html, final_url)
        if not next_url:
            break

        page_index += 1
        current_url = next_url

    return all_rows


def fetch_ad_rows(
    begin_date: str,
    end_date: str,
    *,
    store_id: str = "22",
    force_relogin: bool = False,
) -> list[dict]:
    if force_relogin:
        relogin()

    store = get_store(store_id)
    start_url = build_pdd_ad_url(
        begin_date=begin_date,
        end_date=end_date,
        page=1,
        store=store.id,
    )
    logging.info("开始抓取 ERP：%s ~ %s，%s", begin_date, end_date, store.name)

    first_html, final_url = fetch_html_with_login(start_url, allow_relogin=force_relogin)
    total_pages = get_total_pages(first_html)
    logging.info("检测到总页数：%s", total_pages)

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    (DEBUG_DIR / "page_current_p1.html").write_text(first_html, encoding="utf-8")
    rows = parse_ad_table(first_html)
    for row in rows:
        row["store_id"] = store.id
        row["store_name"] = store.name
    logging.info("第 1 页解析到 %s 行", len(rows))

    all_rows = list(rows)
    next_url = get_next_page_url(first_html, final_url)
    page_index = 2

    while next_url:
        html, final_url = fetch_html_with_login(next_url, allow_relogin=force_relogin)
        (DEBUG_DIR / f"page_current_p{page_index}.html").write_text(html, encoding="utf-8")
        rows = parse_ad_table(html)
        for row in rows:
            row["store_id"] = store.id
            row["store_name"] = store.name
        logging.info("第 %s 页解析到 %s 行", page_index, len(rows))
        all_rows.extend(rows)
        next_url = get_next_page_url(html, final_url)
        page_index += 1

    output_path = DEBUG_DIR / "parsed_rows_current.json"
    output_path.write_text(
        json.dumps(all_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logging.info("ERP 解析完成：共 %s 行，已保存 %s", len(all_rows), output_path)

    return all_rows


def get_step_b_start_url() -> str:
    if CURRENT_URL_PATH.exists():
        saved_url = CURRENT_URL_PATH.read_text(encoding="utf-8").strip()
        if saved_url and "ad_pdd_data" in saved_url:
            return _set_query_param(saved_url, "page", "1")

    return build_pdd_ad_url(page=1)


def print_first_table_preview(html_path: Path, row_limit: int = 3) -> bool:
    html = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id="tabSpec")
    if table is None:
        table = soup.find("table")

    if table is None:
        title = _clean_cell_text(soup.title.get_text()) if soup.title else "无标题"
        print(f"未找到 <table>。当前页面标题：{title}")
        print("这通常表示还停留在登录页，或登录态没有生效。请重新运行并确认登录成功后再按回车。")
        return False

    header_row = table.find("thead")
    if header_row is not None:
        header_cells = header_row.find_all(["th", "td"])
    else:
        first_tr = table.find("tr")
        header_cells = first_tr.find_all(["th", "td"]) if first_tr else []

    headers = _extract_row_texts(header_cells)
    body_rows = table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")[1:]
    data_rows = []
    for row in body_rows[:row_limit]:
        values = _extract_row_texts(row.find_all(["td", "th"]))
        if any(values):
            data_rows.append(values)

    if not headers and not data_rows:
        page_message = _extract_page_message(soup)
        if page_message:
            print(f"页面提示：{page_message}")
        print("已进入广告数据页，但当前日期没有可预览的表头和数据。")
        return False

    print("\n表头：")
    print(" | ".join(headers) if headers else "未识别到表头")

    print(f"\n前 {row_limit} 行：")
    for index, values in enumerate(data_rows, start=1):
        print(f"{index}. " + " | ".join(values))

    return True


def run_step_a() -> None:
    html_path = capture_first_page_html()
    print(f"\nHTML 已保存：{html_path}")
    has_table = print_first_table_preview(html_path)
    if has_table:
        print("\nStep A 完成，请确认表头字段是否正确")
    else:
        print("\nStep A 未完成：没有抓到广告数据表格")


def run_step_b() -> None:
    start_url = get_step_b_start_url()
    print(f"开始抓取：{start_url}")

    first_html, final_url = fetch_html_with_login(start_url, allow_relogin=True)
    total_pages = get_total_pages(first_html)
    print(f"检测到总页数：{total_pages}")

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    (DEBUG_DIR / "page_step_b_p1.html").write_text(first_html, encoding="utf-8")
    first_rows = parse_ad_table(first_html)
    print(f"第 1 页：解析到 {len(first_rows)} 行")

    all_rows = list(first_rows)
    next_url = get_next_page_url(first_html, final_url)
    page_index = 2

    while next_url:
        html, final_url = fetch_html_with_login(next_url, allow_relogin=True)
        (DEBUG_DIR / f"page_step_b_p{page_index}.html").write_text(html, encoding="utf-8")
        rows = parse_ad_table(html)
        print(f"第 {page_index} 页：解析到 {len(rows)} 行")
        all_rows.extend(rows)
        next_url = get_next_page_url(html, final_url)
        page_index += 1

    output_path = DEBUG_DIR / "parsed_rows_step_b.json"
    output_path.write_text(
        json.dumps(all_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n共解析 {len(all_rows)} 行")
    print(f"解析结果已保存：{output_path}")

    print("\n前 3 行：")
    for row in all_rows[:3]:
        print(
            " | ".join(
                [
                    row.get("plan_id", ""),
                    row.get("plan_name", ""),
                    row.get("spend", ""),
                    row.get("spend_average", ""),
                    row.get("click_rate", ""),
                    row.get("convert_rate", ""),
                    row.get("amount_ad", ""),
                    row.get("make_time", ""),
                ]
            )
        )

    print("\nStep B 完成，请确认解析结果是否正确")
