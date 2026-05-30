from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta, timezone

from erp_client import LoginRequiredError, fetch_ad_rows
from notion_sync import notify_notion, sync_rows_to_notion


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
    parser = argparse.ArgumentParser(description="同步拼多多一店广告数据到 Notion")
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument("--date", type=parse_date, help="抓取单日数据，例如 2026-05-29")
    date_group.add_argument(
        "--range",
        dest="date_range",
        help="抓取日期范围，例如 2026-05-01~2026-05-29",
    )
    parser.add_argument("--relogin", action="store_true", help="强制重新扫码/短信登录 ERP")
    parser.add_argument("--dry-run", action="store_true", help="只抓取解析，不写入 Notion")
    return parser


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    args = build_parser().parse_args()
    begin_date, end_date = resolve_date_range(args)

    logging.info("任务开始：%s ~ %s", begin_date, end_date)
    try:
        rows = fetch_ad_rows(begin_date, end_date, force_relogin=args.relogin)

        if args.dry_run:
            logging.info("dry-run：解析到 %s 行，未写入 Notion", len(rows))
            return

        stats = sync_rows_to_notion(rows)
        logging.info("Notion 同步完成：新增 %s 行，更新 %s 行", stats["created"], stats["updated"])
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
            f"拼多多广告数据同步失败（{begin_date} ~ {end_date}）："
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
