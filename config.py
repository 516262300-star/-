from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
ERP_USERNAME = os.getenv("ERP_USERNAME") or os.getenv("ERP_PHONE")
ERP_PASSWORD = os.getenv("ERP_PASSWORD")
