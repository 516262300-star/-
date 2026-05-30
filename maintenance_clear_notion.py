from __future__ import annotations

import time
from typing import Any

import requests

from config import NOTION_TOKEN
from stores import PDD_STORES


NOTION_VERSION = "2022-06-28"


def new_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update(
        {
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        }
    )
    return session


def request_with_retry(method: str, url: str, **kwargs: Any) -> dict:
    delay = 1
    last_error: Exception | None = None

    for _ in range(8):
        session = new_session()
        try:
            response = session.request(method, url, timeout=30, **kwargs)
            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", delay))
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            time.sleep(delay)
            delay = min(delay * 2, 30)
        finally:
            session.close()

    raise RuntimeError(f"Notion 请求失败：{url}") from last_error


def query_pages(data_source_id: str) -> list[dict]:
    url = f"https://api.notion.com/v1/data_sources/{data_source_id}/query"
    response = request_with_retry("POST", url, json={"page_size": 25})
    return response.get("results", [])


def archive_page(page_id: str) -> None:
    url = f"https://api.notion.com/v1/pages/{page_id}"
    request_with_retry("PATCH", url, json={"archived": True})


def clear_data_source(store) -> int:
    archived_count = 0

    while True:
        pages = query_pages(store.data_source_id)
        if not pages:
            return archived_count

        for page in pages:
            archive_page(page["id"])
            archived_count += 1
            if archived_count % 20 == 0:
                print(f"{store.name} 已归档 {archived_count} 行", flush=True)
            time.sleep(0.45)


def main() -> None:
    if not NOTION_TOKEN:
        raise RuntimeError(".env 缺少 NOTION_TOKEN")

    total = 0
    for store in PDD_STORES:
        print(f"开始清空：{store.name}", flush=True)
        count = clear_data_source(store)
        total += count
        print(f"完成清空：{store.name}，归档 {count} 行", flush=True)

    print(f"全部完成，共归档 {total} 行", flush=True)


if __name__ == "__main__":
    main()
