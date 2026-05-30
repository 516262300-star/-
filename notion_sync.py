from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from notion_client import Client
from notion_client.errors import APIResponseError

from config import NOTION_DATABASE_ID, NOTION_TOKEN


STORE_ID = "22"
STORE_NAME = "1店：利德仕官方旗舰店"
NOTION_NOTIFY_USER_ID = "356d872b-594c-8146-b021-0002d1442e4e"

PERCENT_FIELDS = {"click_rate", "convert_rate"}

FIELD_CANDIDATES = {
    "make_time": ["日期", "make_time", "数据日期"],
    "plan_id": ["plan_id", "计划ID", "广告计划ID"],
    "store": ["店铺", "store", "店铺ID"],
    "plan_name": ["广告计划", "plan_name", "广告计划名称"],
    "spend": ["花费", "spend"],
    "spend_average": ["平均点击花费", "spend_average"],
    "click_rate": ["点击率", "click_rate"],
    "convert_rate": ["转化率", "convert_rate"],
    "collect_shop_count": ["收藏店铺数", "collect_shop_count"],
    "collect_goods_count": ["收藏商品数", "collect_goods_count"],
    "amount_ad": ["广告成交金额", "amount_ad"],
    "record_id": ["ERP记录ID", "record_id"],
}

WRITE_FIELD_ORDER = [
    "make_time",
    "plan_id",
    "store",
    "plan_name",
    "spend",
    "spend_average",
    "click_rate",
    "convert_rate",
    "collect_shop_count",
    "collect_goods_count",
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
    missing = []
    if not NOTION_TOKEN:
        missing.append("NOTION_TOKEN")
    if not NOTION_DATABASE_ID:
        missing.append("NOTION_DATABASE_ID")
    if missing:
        raise NotionSyncError(f".env 缺少配置：{', '.join(missing)}")


def get_notion_client() -> Client:
    _require_config()
    http_client = httpx.Client(trust_env=False)
    return Client(auth=NOTION_TOKEN, client=http_client)


def get_database_schema(client: Client) -> dict[str, PropertyInfo]:
    database = _with_retry(
        lambda: client.databases.retrieve(database_id=NOTION_DATABASE_ID)
    )
    if "properties" in database:
        properties = database["properties"]
    else:
        data_source_id = get_data_source_id(client)
        data_source = _with_retry(
            lambda: client.data_sources.retrieve(data_source_id=data_source_id)
        )
        properties = data_source["properties"]

    return {
        name: PropertyInfo(name=name, type=value["type"])
        for name, value in properties.items()
    }


def get_data_source_id(client: Client) -> str:
    database = _with_retry(
        lambda: client.databases.retrieve(database_id=NOTION_DATABASE_ID)
    )
    data_sources = database.get("data_sources") or []
    if data_sources:
        return data_sources[0]["id"]
    return NOTION_DATABASE_ID


def get_notification_page_id(client: Client) -> str:
    database = _with_retry(
        lambda: client.databases.retrieve(database_id=NOTION_DATABASE_ID)
    )
    parent = database.get("parent", {})
    if parent.get("type") == "page_id":
        return parent["page_id"]
    return NOTION_DATABASE_ID


def notify_notion(message: str) -> None:
    client = get_notion_client()
    page_id = get_notification_page_id(client)
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
        _with_retry(
            lambda: client.comments.create(
                parent={"page_id": page_id},
                rich_text=rich_text,
            )
        )
        return
    except APIResponseError:
        # Some integrations can write pages but cannot use the Comments API.
        pass

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _with_retry(
        lambda: client.pages.create(
            parent={"page_id": page_id},
            properties={
                "title": {
                    "title": [
                        {
                            "type": "text",
                            "text": {"content": f"拼多多广告数据同步提醒 {timestamp}"},
                        }
                    ]
                }
            },
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": rich_text},
                }
            ],
        )
    )


def print_database_schema() -> None:
    client = get_notion_client()
    schema = get_database_schema(client)
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
        readable = {
            key: " / ".join(FIELD_CANDIDATES[key])
            for key in missing
        }
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
        if field_key in {"collect_shop_count", "collect_goods_count"}:
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


def build_page_properties(row: dict, mapping: dict[str, PropertyInfo]) -> dict:
    properties = {}
    values = dict(row)
    values["store"] = STORE_NAME

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
    filters = [
        _filter_equals(mapping["make_time"], str(row["make_time"])),
        _filter_equals(mapping["plan_id"], str(row["plan_id"])),
        _filter_equals(mapping["store"], STORE_NAME),
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


def sync_rows_to_notion(rows: list[dict]) -> dict[str, int]:
    client = get_notion_client()
    schema = get_database_schema(client)
    mapping = build_field_mapping(schema)
    data_source_id = get_data_source_id(client)

    stats = {"created": 0, "updated": 0}
    for index, row in enumerate(rows, start=1):
        action = upsert_row(client, data_source_id, row, mapping)
        stats[action] += 1
        if index % 20 == 0:
            print(f"已同步 {index}/{len(rows)} 行")

    return stats


def load_step_b_rows(path: Path = Path("debug/parsed_rows_step_b.json")) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_step_c(dry_run: bool = False) -> None:
    rows = load_step_b_rows()
    print(f"准备同步 {len(rows)} 行到 Notion")

    client = get_notion_client()
    schema = get_database_schema(client)
    mapping = build_field_mapping(schema)
    data_source_id = get_data_source_id(client)

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
