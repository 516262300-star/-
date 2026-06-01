from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta

from notion_sync import (
    _get_database_schema_rest,
    _notion_request,
    _notion_value,
    _plain_property_value,
    build_field_mapping,
    infer_product_id,
)
from stores import PDD_STORES, get_store_ids


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def iter_dates(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def parse_range(value: str) -> tuple[date, date]:
    if "~" not in value:
        single_date = parse_date(value)
        return single_date, single_date
    start_text, end_text = value.split("~", 1)
    return parse_date(start_text.strip()), parse_date(end_text.strip())


def query_pages_for_date(data_source_id: str, date_prop_name: str, day: date) -> list[dict]:
    payload = {
        "page_size": 10,
        "filter": {
            "property": date_prop_name,
            "date": {"equals": day.isoformat()},
        },
    }
    pages: list[dict] = []

    while True:
        response = _notion_request(
            "POST",
            f"/data_sources/{data_source_id}/query",
            payload=payload,
        )
        pages.extend(response.get("results", []))
        if not response.get("has_more"):
            return pages
        payload["start_cursor"] = response.get("next_cursor")


def fill_store_product_ids(store, start: date, end: date) -> dict[str, int]:
    schema = _get_database_schema_rest(store.data_source_id)
    mapping = build_field_mapping(schema)

    required_keys = ["make_time", "plan_id", "plan_name", "product_id"]
    missing = [key for key in required_keys if key not in mapping]
    if missing:
        print(f"{store.name}：缺少字段，跳过：{', '.join(missing)}")
        return {"checked": 0, "updated": 0, "skipped": 0}

    stats = {"checked": 0, "updated": 0, "skipped": 0}
    date_prop = mapping["make_time"]
    plan_id_prop = mapping["plan_id"]
    plan_name_prop = mapping["plan_name"]
    product_id_prop = mapping["product_id"]

    for day in iter_dates(start, end):
        pages = query_pages_for_date(store.data_source_id, date_prop.name, day)
        for page in pages:
            stats["checked"] += 1
            properties = page.get("properties", {})
            current_product_id = _plain_property_value(
                properties.get(product_id_prop.name, {}),
                product_id_prop.type,
            ).strip()
            if current_product_id:
                stats["skipped"] += 1
                continue

            plan_name = _plain_property_value(
                properties.get(plan_name_prop.name, {}),
                plan_name_prop.type,
            )
            plan_id = _plain_property_value(
                properties.get(plan_id_prop.name, {}),
                plan_id_prop.type,
            )
            product_id = infer_product_id({"plan_name": plan_name, "plan_id": plan_id})
            if not product_id:
                stats["skipped"] += 1
                continue

            notion_value = _notion_value(product_id_prop.type, "product_id", product_id)
            if notion_value is None:
                stats["skipped"] += 1
                continue

            _notion_request(
                "PATCH",
                f"/pages/{page['id']}",
                payload={"properties": {product_id_prop.name: notion_value}},
            )
            stats["updated"] += 1

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="回填 Notion 拼多多广告数据的商品ID")
    parser.add_argument("--range", default="2026-05-25~2026-05-31")
    parser.add_argument("--store", default="all")
    args = parser.parse_args()

    start, end = parse_range(args.range)
    store_ids = set(get_store_ids(args.store))
    total = {"checked": 0, "updated": 0, "skipped": 0}

    for store in PDD_STORES:
        if store.id not in store_ids:
            continue
        stats = fill_store_product_ids(store, start, end)
        for key, value in stats.items():
            total[key] += value
        print(
            f"{store.name}：检查 {stats['checked']} 条，"
            f"回填 {stats['updated']} 条，跳过 {stats['skipped']} 条"
        )

    print(
        f"完成：检查 {total['checked']} 条，"
        f"回填 {total['updated']} 条，跳过 {total['skipped']} 条"
    )


if __name__ == "__main__":
    main()
