from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import requests
from notion_client import Client
from notion_client.errors import APIResponseError

from config import NOTION_DATABASE_ID, NOTION_TOKEN
from stores import PDD_STORES


DEFAULT_STORE_NAME = "1店：利德仕官方旗舰店"
NOTION_NOTIFY_USER_ID = "356d872b-594c-8146-b021-0002d1442e4e"
NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2025-09-03"
NOTION_REQUEST_RETRIES = 5
NOTION_REQUEST_TIMEOUT_SECONDS = 15
NOTION_PAGE_CREATE_ATTEMPTS = 3
PENDING_NOTION_DIR = Path("debug/pending_notion")
_preferred_notion_trust_env: bool | None = None

PERCENT_FIELDS = {"click_rate", "convert_rate", "promotion_exposure_rate"}
INTEGER_FIELDS = {
    "collect_shop_count",
    "collect_goods_count",
    "impressions",
    "order_count",
}

FIELD_CANDIDATES = {
    "make_time": ["日期", "make_time", "数据日期"],
    "plan_id": ["plan_id", "计划ID", "广告计划ID"],
    "store": ["店铺", "store", "店铺ID"],
    "plan_name": ["广告计划", "plan_name", "广告计划名称"],
    "ad_type": ["广告类型", "ad_type"],
    "product_id": ["商品ID", "product_id"],
    "spend": ["花费", "spend"],
    "spend_average": ["平均点击花费", "spend_average"],
    "click_rate": ["点击率", "click_rate"],
    "convert_rate": ["转化率", "convert_rate"],
    "collect_shop_count": ["收藏店铺数", "collect_shop_count"],
    "collect_goods_count": ["收藏商品数", "collect_goods_count"],
    "roi": ["投产比", "roi"],
    "impressions": ["曝光量", "impressions"],
    "promotion_exposure_rate": ["推广曝光占比", "promotion_exposure_rate"],
    "order_count": ["成交笔数", "order_count"],
    "cost_per_order": ["每笔成交花费", "cost_per_order"],
    "amount_per_order": ["每笔成交金额", "amount_per_order"],
    "amount_ad": ["广告成交金额", "amount_ad"],
    "record_id": ["ERP记录ID", "record_id"],
}

WRITE_FIELD_ORDER = [
    "make_time",
    "plan_id",
    "store",
    "plan_name",
    "ad_type",
    "product_id",
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
    "record_id",
]


@dataclass(frozen=True)
class PropertyInfo:
    name: str
    type: str


class NotionSyncError(RuntimeError):
    pass


def _require_config() -> None:
    if not NOTION_TOKEN:
        raise NotionSyncError(".env 缺少配置：NOTION_TOKEN")


def _default_database_id() -> str:
    return NOTION_DATABASE_ID or PDD_STORES[0].database_id


def get_notion_client() -> Client:
    _require_config()
    http_client = httpx.Client()
    return Client(auth=NOTION_TOKEN, client=http_client)


def get_data_source_id(client: Client, database_id: str | None = None) -> str:
    resolved_database_id = database_id or _default_database_id()
    database = _with_retry(
        lambda: client.databases.retrieve(database_id=resolved_database_id)
    )
    data_sources = database.get("data_sources") or []
    if data_sources:
        return data_sources[0]["id"]
    return resolved_database_id


def get_database_schema(
    client: Client,
    database_id: str | None = None,
    data_source_id: str | None = None,
) -> dict[str, PropertyInfo]:
    if data_source_id is None:
        resolved_database_id = database_id or _default_database_id()
        database = _with_retry(
            lambda: client.databases.retrieve(database_id=resolved_database_id)
        )
        if "properties" in database:
            properties = database["properties"]
        else:
            data_source_id = get_data_source_id(client, resolved_database_id)
            data_source = _with_retry(
                lambda: client.data_sources.retrieve(data_source_id=data_source_id)
            )
            properties = data_source["properties"]
    else:
        data_source = _with_retry(
            lambda: client.data_sources.retrieve(data_source_id=data_source_id)
        )
        properties = data_source["properties"]

    return {
        name: PropertyInfo(name=name, type=value["type"])
        for name, value in properties.items()
    }


def get_notification_page_id(client: Client) -> str:
    database_id = _default_database_id()
    database = _with_retry(lambda: client.databases.retrieve(database_id=database_id))
    parent = database.get("parent", {})
    if parent.get("type") == "page_id":
        return parent["page_id"]
    return database_id


def notify_notion(message: str) -> None:
    database_id = _default_database_id()
    database = _notion_request("GET", f"/databases/{database_id}")
    parent = database.get("parent", {})
    page_id = parent["page_id"] if parent.get("type") == "page_id" else database_id
    rich_text = [
        {
            "type": "mention",
            "mention": {
                "type": "user",
                "user": {"id": NOTION_NOTIFY_USER_ID},
            },
        },
        {
            "type": "text",
            "text": {"content": f" {message}"},
        },
    ]

    try:
        _notion_request(
            "POST",
            "/comments",
            payload={"parent": {"page_id": page_id}, "rich_text": rich_text},
        )
        return
    except Exception:
        # 有些 integration 可以创建页面，但没有 Comments API 权限。
        pass

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _notion_request(
        "POST",
        "/pages",
        payload={
            "parent": {"page_id": page_id},
            "properties": {
                "title": {
                    "title": [
                        {
                            "type": "text",
                            "text": {"content": f"拼多多广告数据同步提醒 {timestamp}"},
                        }
                    ]
                }
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": rich_text},
                }
            ],
        },
    )


def print_database_schema(database_id: str | None = None) -> None:
    client = get_notion_client()
    schema = get_database_schema(client, database_id=database_id)
    print("Notion 数据库列：")
    for prop in schema.values():
        print(f"- {prop.name}: {prop.type}")


def build_field_mapping(schema: dict[str, PropertyInfo]) -> dict[str, PropertyInfo]:
    mapping: dict[str, PropertyInfo] = {}
    normalized_names = {name.lower(): info for name, info in schema.items()}

    for field_key, candidates in FIELD_CANDIDATES.items():
        for candidate in candidates:
            info = schema.get(candidate) or normalized_names.get(candidate.lower())
            if info is not None:
                mapping[field_key] = info
                break

    required = ["make_time", "plan_id", "store"]
    missing = [key for key in required if key not in mapping]
    if missing:
        readable = {key: " / ".join(FIELD_CANDIDATES[key]) for key in missing}
        raise NotionSyncError(f"Notion 数据库缺少三键判重列：{readable}")

    return mapping


def _to_float(value: Any, *, percent: bool = False) -> float | None:
    if value in (None, ""):
        return None

    text = str(value).strip().replace(",", "")
    if not text:
        return None

    has_percent_sign = text.endswith("%")
    text = text.rstrip("%")
    number = float(text)

    if percent or has_percent_sign:
        return number / 100

    return number


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None

    return int(float(str(value).strip().replace(",", "")))


def _to_title(value: Any) -> dict:
    return {"title": [{"text": {"content": "" if value is None else str(value)}}]}


def _to_rich_text(value: Any) -> dict:
    return {"rich_text": [{"text": {"content": "" if value is None else str(value)}}]}


def _notion_value(prop_type: str, field_key: str, value: Any) -> dict | None:
    if prop_type == "title":
        return _to_title(value)
    if prop_type == "rich_text":
        return _to_rich_text(value)
    if prop_type == "number":
        if field_key in INTEGER_FIELDS:
            return {"number": _to_int(value)}
        return {"number": _to_float(value, percent=field_key in PERCENT_FIELDS)}
    if prop_type == "date":
        if value in (None, ""):
            return {"date": None}
        return {"date": {"start": str(value)}}
    if prop_type == "select":
        if value in (None, ""):
            return {"select": None}
        return {"select": {"name": str(value)}}

    return None


def infer_ad_type(row: dict) -> str | None:
    plan_name = str(row.get("plan_name") or row.get("广告计划") or "").strip()
    plan_id = str(row.get("plan_id") or "").strip()

    if "全店托管" in plan_name:
        return "全店托管"
    if "ID" in plan_name.upper() or plan_id:
        return "稳定成本"
    return None


def infer_product_id(row: dict) -> str | None:
    if infer_ad_type(row) != "稳定成本":
        return None

    plan_name = str(row.get("plan_name") or row.get("广告计划") or "").strip()
    match = re.search(r"商品\s*ID\s*[：:]\s*(\d+)", plan_name, flags=re.IGNORECASE)
    if match:
        return match.group(1)

    match = re.search(r"\bID\s*[：:]\s*(\d+)", plan_name, flags=re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def build_page_properties(row: dict, mapping: dict[str, PropertyInfo]) -> dict:
    properties = {}
    values = dict(row)
    values["store"] = row.get("store_name") or DEFAULT_STORE_NAME
    values["ad_type"] = infer_ad_type(row)
    values["product_id"] = infer_product_id(row)

    for field_key in WRITE_FIELD_ORDER:
        prop = mapping.get(field_key)
        if prop is None:
            continue

        value = values.get(field_key)
        notion_value = _notion_value(prop.type, field_key, value)
        if notion_value is not None:
            properties[prop.name] = notion_value

    return properties


def _filter_equals(prop: PropertyInfo, value: str) -> dict:
    if prop.type == "date":
        return {"property": prop.name, "date": {"equals": value}}
    if prop.type == "number":
        return {"property": prop.name, "number": {"equals": _to_float(value)}}
    if prop.type == "select":
        return {"property": prop.name, "select": {"equals": value}}
    if prop.type == "title":
        return {"property": prop.name, "title": {"equals": value}}
    return {"property": prop.name, "rich_text": {"equals": value}}


def find_existing_page(
    client: Client,
    data_source_id: str,
    row: dict,
    mapping: dict[str, PropertyInfo],
) -> str | None:
    store_name = row.get("store_name") or DEFAULT_STORE_NAME
    filters = [
        _filter_equals(mapping["make_time"], str(row["make_time"])),
        _filter_equals(mapping["plan_id"], str(row["plan_id"])),
        _filter_equals(mapping["store"], store_name),
    ]

    response = _with_retry(
        lambda: client.data_sources.query(
            data_source_id=data_source_id,
            filter={"and": filters},
            page_size=1,
        )
    )
    results = response.get("results", [])
    return results[0]["id"] if results else None


def _with_retry(operation, *, retries: int = 3):
    delay = 1
    for attempt in range(1, retries + 1):
        try:
            return operation()
        except Exception:
            if attempt >= retries:
                raise
            time.sleep(delay)
            delay *= 2


def upsert_row(
    client: Client,
    data_source_id: str,
    row: dict,
    mapping: dict[str, PropertyInfo],
) -> str:
    properties = build_page_properties(row, mapping)
    page_id = find_existing_page(client, data_source_id, row, mapping)

    if page_id:
        _with_retry(lambda: client.pages.update(page_id=page_id, properties=properties))
        return "updated"

    _with_retry(
        lambda: client.pages.create(
            parent={"data_source_id": data_source_id},
            properties=properties,
        )
    )
    return "created"


def sync_rows_to_notion(
    rows: list[dict],
    *,
    database_id: str | None = None,
    data_source_id: str | None = None,
) -> dict[str, int]:
    logging.info("准备写入 Notion：%s 行", len(rows))
    if not rows:
        return {"created": 0, "updated": 0}

    resolved_data_source_id = data_source_id or _get_data_source_id_rest(database_id)
    logging.info("读取 Notion 数据库字段")
    try:
        schema = _get_database_schema_rest(resolved_data_source_id)
    except Exception as exc:
        logging.warning(
            "读取 Notion 字段失败，改用本地已知字段映射：%s: %s",
            type(exc).__name__,
            exc,
        )
        schema = _known_database_schema()
    mapping = build_field_mapping(schema)
    logging.info("读取 Notion 已有数据用于去重")
    try:
        existing_pages = _load_existing_page_index(resolved_data_source_id, rows, mapping)
    except Exception as exc:
        pending_path = _save_pending_notion_rows(
            rows,
            data_source_id=resolved_data_source_id,
            reason=f"读取已有数据失败：{type(exc).__name__}: {exc}",
        )
        raise NotionSyncError(
            f"Notion 读取已有数据失败，已保存待补写文件：{pending_path}"
        ) from exc
    logging.info("Notion 已有数据读取完成：%s 行", len(existing_pages))

    stats = {"created": 0, "updated": 0}
    for index, row in enumerate(rows, start=1):
        if len(rows) <= 10 or index % 20 == 0:
            logging.info("写入 Notion：%s/%s", index, len(rows))
        try:
            action = _upsert_row_rest(resolved_data_source_id, row, mapping, existing_pages)
        except Exception as exc:
            pending_path = _save_pending_notion_rows(
                rows[index - 1 :],
                data_source_id=resolved_data_source_id,
                reason=f"写入第 {index}/{len(rows)} 行失败：{type(exc).__name__}: {exc}",
            )
            raise NotionSyncError(
                f"Notion 写入中断，剩余 {len(rows) - index + 1} 行已保存待补写文件：{pending_path}"
            ) from exc
        stats[action] += 1
        if index % 20 == 0:
            print(f"已同步 {index}/{len(rows)} 行")

    return stats


def _save_pending_notion_rows(
    rows: list[dict],
    *,
    data_source_id: str,
    reason: str,
) -> Path:
    PENDING_NOTION_DIR.mkdir(parents=True, exist_ok=True)
    if rows:
        store_id = str(rows[0].get("store_id") or "unknown")
        dates = sorted({str(row.get("make_time") or "unknown") for row in rows})
        date_part = f"{dates[0]}_{dates[-1]}" if dates else "unknown"
    else:
        store_id = "unknown"
        date_part = "unknown"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = PENDING_NOTION_DIR / f"pending_store_{store_id}_{date_part}_{timestamp}.json"
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "data_source_id": data_source_id,
        "reason": reason,
        "rows": rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.error("Notion 待补写数据已保存：%s", path)
    return path


def _notion_headers() -> dict[str, str]:
    _require_config()
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def _notion_request(
    method: str,
    path: str,
    *,
    payload: dict | None = None,
    retries: int | None = None,
) -> dict:
    global _preferred_notion_trust_env

    delay = 1
    last_error: Exception | None = None
    max_retries = retries or NOTION_REQUEST_RETRIES

    for attempt in range(1, max_retries + 1):
        route_errors: list[str] = []
        if _preferred_notion_trust_env is None:
            trust_env_options = [False, True]
        else:
            trust_env_options = [
                _preferred_notion_trust_env,
                not _preferred_notion_trust_env,
            ]

        for trust_env in trust_env_options:
            session = requests.Session()
            session.trust_env = trust_env
            try:
                headers = _notion_headers()
                headers["Connection"] = "close"
                response = session.request(
                    method,
                    f"{NOTION_API_BASE}{path}",
                    headers=headers,
                    json=payload,
                    timeout=NOTION_REQUEST_TIMEOUT_SECONDS,
                )
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", delay))
                    logging.warning(
                        "Notion 限流，等待 %s 秒后重试：%s %s",
                        retry_after,
                        method,
                        path,
                    )
                    time.sleep(retry_after)
                    continue
                if response.status_code >= 400:
                    error_text = response.text[:1000]
                    raise NotionSyncError(
                        f"Notion HTTP {response.status_code}: {error_text}"
                    )
                result = response.json()
                time.sleep(0.25)
                _preferred_notion_trust_env = trust_env
                return result
            except Exception as exc:
                last_error = exc
                route_errors.append(
                    f"代理={'开' if trust_env else '关'}，错误：{exc}"
                )
            finally:
                session.close()

        if attempt >= max_retries:
            logging.warning(
                "Notion 请求失败：%s %s，第 %s/%s 次，%s",
                method,
                path,
                attempt,
                max_retries,
                "；".join(route_errors),
            )
        else:
            logging.info(
                "Notion 请求暂时失败，准备重试：%s %s，第 %s/%s 次",
                method,
                path,
                attempt,
                max_retries,
            )
        time.sleep(delay)
        delay = min(delay * 1.5, 20)

    raise NotionSyncError(f"Notion 请求失败：{method} {path}") from last_error


def _get_data_source_id_rest(database_id: str | None = None) -> str:
    resolved_database_id = database_id or _default_database_id()
    database = _notion_request("GET", f"/databases/{resolved_database_id}")
    data_sources = database.get("data_sources") or []
    if data_sources:
        return data_sources[0]["id"]
    return resolved_database_id


def _get_database_schema_rest(data_source_id: str) -> dict[str, PropertyInfo]:
    data_source = _notion_request("GET", f"/data_sources/{data_source_id}")
    properties = data_source["properties"]
    return {
        name: PropertyInfo(name=name, type=value["type"])
        for name, value in properties.items()
    }


def _known_database_schema() -> dict[str, PropertyInfo]:
    known_types = {
        "日期": "date",
        "plan_id": "rich_text",
        "店铺": "select",
        "广告计划": "title",
        "广告类型": "select",
        "商品ID": "rich_text",
        "花费": "number",
        "平均点击花费": "number",
        "点击率": "number",
        "转化率": "number",
        "收藏店铺数": "number",
        "收藏商品数": "number",
        "投产比": "number",
        "曝光量": "number",
        "推广曝光占比": "number",
        "成交笔数": "number",
        "每笔成交花费": "number",
        "每笔成交金额": "number",
        "广告成交金额": "number",
        "ERP记录ID": "rich_text",
    }
    return {
        name: PropertyInfo(name=name, type=prop_type)
        for name, prop_type in known_types.items()
    }


def _row_key(row: dict, mapping: dict[str, PropertyInfo]) -> tuple[str, str, str]:
    return (
        str(row["make_time"]),
        str(row["plan_id"]),
        str(row.get("store_name") or DEFAULT_STORE_NAME),
    )


def _plain_property_value(prop: dict, prop_type: str) -> str:
    if prop_type == "date":
        date_value = prop.get("date") or {}
        return str(date_value.get("start") or "")
    if prop_type == "select":
        select_value = prop.get("select") or {}
        return str(select_value.get("name") or "")
    if prop_type == "title":
        return "".join(item.get("plain_text", "") for item in prop.get("title", []))
    if prop_type == "rich_text":
        return "".join(item.get("plain_text", "") for item in prop.get("rich_text", []))
    if prop_type == "number":
        return "" if prop.get("number") is None else str(prop.get("number"))
    return ""


def _page_key(
    page: dict,
    mapping: dict[str, PropertyInfo],
) -> tuple[str, str, str] | None:
    properties = page.get("properties", {})
    try:
        make_time_prop = mapping["make_time"]
        plan_id_prop = mapping["plan_id"]
        store_prop = mapping["store"]
        return (
            _plain_property_value(properties[make_time_prop.name], make_time_prop.type),
            _plain_property_value(properties[plan_id_prop.name], plan_id_prop.type),
            _plain_property_value(properties[store_prop.name], store_prop.type),
        )
    except KeyError:
        return None


def _date_range_filters(rows: list[dict], mapping: dict[str, PropertyInfo]) -> dict | None:
    dates = sorted({str(row.get("make_time") or "") for row in rows if row.get("make_time")})
    if not dates:
        return None

    make_time_prop = mapping["make_time"]
    return {
        "and": [
            {
                "property": make_time_prop.name,
                "date": {"on_or_after": dates[0]},
            },
            {
                "property": make_time_prop.name,
                "date": {"on_or_before": dates[-1]},
            },
        ]
    }


def has_rows_for_date(
    *,
    date: str,
    data_source_id: str,
) -> bool:
    """Return whether the Notion data source already has at least one row for date."""
    try:
        schema = _get_database_schema_rest(data_source_id)
    except Exception:
        schema = _known_database_schema()
    mapping = build_field_mapping(schema)
    make_time_prop = mapping["make_time"]
    response = _notion_request(
        "POST",
        f"/data_sources/{data_source_id}/query",
        payload={
            "filter": _filter_equals(make_time_prop, date),
            "page_size": 1,
        },
    )
    return bool(response.get("results"))


def _load_existing_page_index(
    data_source_id: str,
    rows: list[dict],
    mapping: dict[str, PropertyInfo],
) -> dict[tuple[str, str, str], str]:
    page_index: dict[tuple[str, str, str], str] = {}
    payload: dict[str, Any] = {"page_size": 100}
    date_filter = _date_range_filters(rows, mapping)
    if date_filter:
        payload["filter"] = date_filter

    while True:
        response = _notion_request(
            "POST",
            f"/data_sources/{data_source_id}/query",
            payload=payload,
        )
        for page in response.get("results", []):
            key = _page_key(page, mapping)
            if key is not None:
                page_index[key] = page["id"]

        if not response.get("has_more"):
            return page_index

        logging.info("继续读取 Notion 已有数据：已读取 %s 行", len(page_index))
        payload["start_cursor"] = response.get("next_cursor")


def _find_existing_page_rest(
    data_source_id: str,
    row: dict,
    mapping: dict[str, PropertyInfo],
) -> str | None:
    store_name = row.get("store_name") or DEFAULT_STORE_NAME
    filters = [
        _filter_equals(mapping["make_time"], str(row["make_time"])),
        _filter_equals(mapping["plan_id"], str(row["plan_id"])),
        _filter_equals(mapping["store"], store_name),
    ]
    response = _notion_request(
        "POST",
        f"/data_sources/{data_source_id}/query",
        payload={"filter": {"and": filters}, "page_size": 1},
    )
    results = response.get("results", [])
    return results[0]["id"] if results else None


def _create_page_rest(
    data_source_id: str,
    row: dict,
    mapping: dict[str, PropertyInfo],
    properties: dict,
) -> str:
    for attempt in range(1, NOTION_PAGE_CREATE_ATTEMPTS + 1):
        try:
            response = _notion_request(
                "POST",
                "/pages",
                payload={
                    "parent": {"data_source_id": data_source_id},
                    "properties": properties,
                },
                retries=1,
            )
            return response.get("id", "")
        except Exception as exc:
            logging.warning(
                "Notion 新建页面失败，反查是否已创建：第 %s/%s 次，错误：%s",
                attempt,
                NOTION_PAGE_CREATE_ATTEMPTS,
                exc,
            )
            page_id = _find_existing_page_rest(data_source_id, row, mapping)
            if page_id:
                logging.info("Notion 页面已创建但回包失败，已通过反查确认：%s", page_id)
                return page_id
            if attempt >= NOTION_PAGE_CREATE_ATTEMPTS:
                raise

    raise NotionSyncError("Notion 新建页面失败")


def _upsert_row_rest(
    data_source_id: str,
    row: dict,
    mapping: dict[str, PropertyInfo],
    existing_pages: dict[tuple[str, str, str], str] | None = None,
) -> str:
    properties = build_page_properties(row, mapping)
    key = _row_key(row, mapping)
    page_id = existing_pages.get(key) if existing_pages is not None else None
    if page_id is None and existing_pages is None:
        page_id = _find_existing_page_rest(data_source_id, row, mapping)

    if page_id:
        _notion_request("PATCH", f"/pages/{page_id}", payload={"properties": properties})
        return "updated"

    page_id = _create_page_rest(data_source_id, row, mapping, properties)
    if existing_pages is not None:
        existing_pages[key] = page_id
    return "created"


def load_step_b_rows(path: Path = Path("debug/parsed_rows_step_b.json")) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_step_c(dry_run: bool = False) -> None:
    rows = load_step_b_rows()
    print(f"准备同步 {len(rows)} 行到 Notion")

    client = get_notion_client()
    data_source_id = get_data_source_id(client)
    schema = get_database_schema(client, data_source_id=data_source_id)
    mapping = build_field_mapping(schema)

    print("字段映射：")
    for field_key in WRITE_FIELD_ORDER:
        prop = mapping.get(field_key)
        if prop:
            print(f"- {field_key} -> {prop.name} ({prop.type})")

    if dry_run:
        print(f"Data source ID：{data_source_id}")
        print("dry-run 模式：只检查 schema 和字段映射，不写入 Notion")
        return

    stats = sync_rows_to_notion(rows)
    print(f"Step C 完成：新增 {stats['created']} 行，更新 {stats['updated']} 行")
