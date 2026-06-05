from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone

from erp_client import LoginRequiredError
from main import parse_date, sync_one_store
from notion_sync import has_rows_for_date, notify_notion
from stores import get_store, get_store_ids


SHANGHAI_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


def default_yesterday() -> str:
    return (datetime.now(SHANGHAI_TZ).date() - timedelta(days=1)).isoformat()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检查并补跑缺失的拼多多广告数据")
    parser.add_argument("--date", type=parse_date, default=default_yesterday(), help="检查日期，默认昨天")
    parser.add_argument(
        "--store",
        default="all",
        help="店铺 ID，多个用逗号分隔，例如 222,223；也可填 all。默认一到七店。",
    )
    parser.add_argument("--dry-run", action="store_true", help="只检查缺失情况，不写入 Notion")
    return parser


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

    args = build_parser().parse_args()
    store_ids = get_store_ids(args.store)
    logging.info("开始补漏检查：%s，店铺：%s", args.date, ", ".join(store_ids))

    missing_store_ids: list[str] = []
    for store_id in store_ids:
        store = get_store(store_id)
        if has_rows_for_date(date=args.date, data_source_id=store.data_source_id):
            logging.info("Notion 已有数据，跳过：%s，日期 %s", store.name, args.date)
            continue
        logging.warning("Notion 缺少数据，准备补跑：%s，日期 %s", store.name, args.date)
        missing_store_ids.append(store_id)

    if not missing_store_ids:
        logging.info("补漏检查完成：Notion 已有 %s 的全部店铺数据，无需补跑", args.date)
        return

    if args.dry_run:
        missing_names = "，".join(get_store(store_id).name for store_id in missing_store_ids)
        logging.info("dry-run：缺少数据的店铺：%s", missing_names)
        return

    totals = {"created": 0, "updated": 0, "rows": 0}
    try:
        for store_id in missing_store_ids:
            stats = sync_one_store(
                store_id=store_id,
                begin_date=args.date,
                end_date=args.date,
                relogin=False,
                dry_run=False,
            )
            totals["created"] += stats["created"]
            totals["updated"] += stats["updated"]
            totals["rows"] += stats["rows"]
    except LoginRequiredError as exc:
        message = (
            f"ERP 拼多多广告数据补漏失败（{args.date}）：{exc} "
            "脚本已配置账号密码自动登录；如果仍失败，请检查 .env 的 ERP_USERNAME / ERP_PASSWORD。"
        )
        logging.error(message)
        try:
            notify_notion(message)
        except Exception:
            logging.exception("Notion 提醒发送失败")
        raise SystemExit(1) from exc
    except Exception as exc:
        message = f"拼多多广告数据补漏失败（{args.date}）：{type(exc).__name__}: {exc}"
        logging.exception(message)
        try:
            notify_notion(message)
        except Exception:
            logging.exception("Notion 提醒发送失败")
        raise SystemExit(1) from exc

    logging.info(
        "补漏完成：%s，共抓取 %s 行，新增 %s 行，更新 %s 行",
        args.date,
        totals["rows"],
        totals["created"],
        totals["updated"],
    )


if __name__ == "__main__":
    main()
