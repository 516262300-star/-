from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta, timezone

from erp_client import LoginRequiredError, fetch_ad_rows
from notion_sync import notify_notion, sync_rows_to_notion
from stores import get_store, get_store_ids


SHANGHAI_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


def parse_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期格式必须是 YYYY-MM-DD") from exc
    return value


def default_yesterday() -> str:
    return (datetime.now(SHANGHAI_TZ).date() - timedelta(days=1)).isoformat()


def resolve_date_range(args: argparse.Namespace) -> tuple[str, str]:
    if args.date:
        return args.date, args.date

    if args.date_range:
        parts = args.date_range.split("~", maxsplit=1)
        if len(parts) != 2:
            raise SystemExit("--range 格式必须是 YYYY-MM-DD~YYYY-MM-DD")
        begin_date = parse_date(parts[0].strip())
        end_date = parse_date(parts[1].strip())
        if begin_date > end_date:
            raise SystemExit("--range 的开始日期不能晚于结束日期")
        return begin_date, end_date

    yesterday = default_yesterday()
    return yesterday, yesterday


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="同步拼多多广告数据到 Notion")
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument("--date", type=parse_date, help="抓取单日数据，例如 2026-05-29")
    date_group.add_argument(
        "--range",
        dest="date_range",
        help="抓取日期范围，例如 2026-05-01~2026-05-29",
    )
    parser.add_argument(
        "--store",
        default="22",
        help="店铺 ID，多个用逗号分隔，例如 222,223；也可填 all。默认只跑一店 22。",
    )
    parser.add_argument("--relogin", action="store_true", help="强制重新扫码/短信登录 ERP")
    parser.add_argument("--dry-run", action="store_true", help="只抓取解析，不写入 Notion")
    return parser


def sync_one_store(
    *,
    store_id: str,
    begin_date: str,
    end_date: str,
    relogin: bool,
    dry_run: bool,
) -> dict[str, int]:
    store = get_store(store_id)
    logging.info("开始处理：%s", store.name)

    rows = fetch_ad_rows(
        begin_date,
        end_date,
        store_id=store.id,
        force_relogin=relogin,
    )

    if dry_run:
        logging.info("dry-run：%s 解析到 %s 行，未写入 Notion", store.name, len(rows))
        return {"created": 0, "updated": 0, "rows": len(rows)}

    stats = sync_rows_to_notion(
        rows,
        database_id=store.database_id,
        data_source_id=store.data_source_id,
    )
    stats["rows"] = len(rows)
    logging.info(
        "Notion 同步完成：%s，抓取 %s 行，新增 %s 行，更新 %s 行",
        store.name,
        len(rows),
        stats["created"],
        stats["updated"],
    )
    return stats


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    args = build_parser().parse_args()
    begin_date, end_date = resolve_date_range(args)
    store_ids = get_store_ids(args.store)

    logging.info("任务开始：%s ~ %s，店铺：%s", begin_date, end_date, ", ".join(store_ids))

    totals = {"created": 0, "updated": 0, "rows": 0}
    try:
        for index, store_id in enumerate(store_ids):
            stats = sync_one_store(
                store_id=store_id,
                begin_date=begin_date,
                end_date=end_date,
                relogin=args.relogin and index == 0,
                dry_run=args.dry_run,
            )
            totals["created"] += stats["created"]
            totals["updated"] += stats["updated"]
            totals["rows"] += stats["rows"]

        if args.dry_run:
            logging.info("dry-run 完成：共解析 %s 行，未写入 Notion", totals["rows"])
            return

        logging.info(
            "全部完成：共抓取 %s 行，新增 %s 行，更新 %s 行",
            totals["rows"],
            totals["created"],
            totals["updated"],
        )
    except LoginRequiredError as exc:
        message = (
            f"ERP 拼多多广告数据同步失败（{begin_date} ~ {end_date}）：{exc} "
            f"请在电脑上运行 python main.py --relogin，完成扫码/短信登录。"
        )
        logging.error(message)
        try:
            notify_notion(message)
            logging.info("已在 Notion 里 @ 金博敏提醒重新登录")
        except Exception:
            logging.exception("Notion 提醒发送失败")
        raise SystemExit(1) from exc
    except Exception as exc:
        message = (
            f"拼多多广告数据同步失败（{begin_date} ~ {end_date}，店铺 {args.store}）："
            f"{type(exc).__name__}: {exc}"
        )
        logging.exception(message)
        try:
            notify_notion(message)
            logging.info("已在 Notion 里 @ 金博敏提醒同步失败")
        except Exception:
            logging.exception("Notion 提醒发送失败")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
