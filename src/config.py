import json
import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(f"Thiếu biến môi trường: {key}")
    return value


DISCORD_BOT_TOKEN = _require("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(_require("DISCORD_CHANNEL_ID"))

JIRA_BASE_URL = _require("JIRA_BASE_URL").rstrip("/")
JIRA_EMAIL = _require("JIRA_EMAIL")
JIRA_API_TOKEN = _require("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = _require("JIRA_PROJECT_KEY")

REMIND_CRON_HOUR = int(os.getenv("REMIND_CRON_HOUR", "9"))
REMIND_CRON_MINUTE = int(os.getenv("REMIND_CRON_MINUTE", "0"))

# {"jira_account_id": "discord_user_id", ...}
_raw_map = os.getenv("JIRA_DISCORD_USER_MAP", "{}")
JIRA_DISCORD_USER_MAP: dict[str, str] = json.loads(_raw_map)
