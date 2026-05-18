"""Telegram notifier - thin wrapper over python-telegram-bot.

Behavior matrix
---------------

* If ``TELEGRAM_BOT_TOKEN`` and ``TELEGRAM_CHAT_ID`` are configured AND
  ``enabled=True``, messages are actually sent.
* Otherwise (default in dev / when the env blocks ``api.telegram.org``), the
  notifier becomes a no-op and just logs the would-be message. This keeps the
  pipeline runnable end-to-end without network or credentials.
"""

from __future__ import annotations

from dataclasses import dataclass

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from home_seek.config import Settings, get_settings
from home_seek.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SendResult:
    sent: bool
    message_id: int | None
    error: str | None = None


class TelegramNotifier:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._bot: Bot | None = None

    @property
    def configured(self) -> bool:
        return bool(self._settings.telegram_bot_token and self._settings.telegram_chat_id)

    def _get_bot(self) -> Bot:
        if self._bot is None:
            if not self._settings.telegram_bot_token:
                raise RuntimeError("telegram_bot_token is not set")
            self._bot = Bot(token=self._settings.telegram_bot_token)
        return self._bot

    async def send_message(self, text: str) -> SendResult:
        if not self.configured:
            logger.info("telegram.skipped", reason="not_configured", preview=text[:120])
            return SendResult(sent=False, message_id=None, error="not_configured")

        try:
            msg = await self._get_bot().send_message(
                chat_id=self._settings.telegram_chat_id,  # type: ignore[arg-type]
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )
            logger.info("telegram.sent", message_id=msg.message_id)
            return SendResult(sent=True, message_id=msg.message_id)
        except TelegramError as exc:
            logger.warning("telegram.error", error=str(exc))
            return SendResult(sent=False, message_id=None, error=str(exc))
