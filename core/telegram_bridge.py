"""
Owner-only Telegram bridge for Mark-LII.

Lets one specific Telegram user send text commands to JARVIS and receive the
reply in the same chat. It uses plain HTTPS long polling (no webhook, no open
port on this PC) through `requests`, which the project already depends on.

Configuration comes from the process environment only; nothing is read from
or written to disk:
    TELEGRAM_BOT_TOKEN   token from @BotFather
    TELEGRAM_OWNER_ID    numeric Telegram user id allowed to command JARVIS

Security rules enforced here:
  * Only a private chat with the owner is accepted. Every other sender is
    dropped silently (logged by count, never by content).
  * Messages already waiting when the bridge starts are discarded, so a command
    sent while the PC was off cannot run later.
  * The token is never logged. Exceptions are logged by type only, because
    requests embeds the full URL (token included) in its error text.
Tool permissions are not decided here: whatever the command triggers still
passes through core.safe_mode at JarvisLive._execute_tool.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Callable

import requests

_API = "https://api.telegram.org/bot{token}/{method}"
_POLL_TIMEOUT = 30          # seconds the server holds a getUpdates call open
_MAX_LEN = 4000             # Telegram caps a message at 4096 characters


def is_authorized(update: dict, owner_id: int) -> bool:
    """True only for a message from the owner in their private chat."""
    msg = update.get("message")
    if not isinstance(msg, dict):
        return False
    sender = msg.get("from") or {}
    chat = msg.get("chat") or {}
    return (
        sender.get("id") == owner_id
        and chat.get("id") == owner_id
        and chat.get("type") == "private"
        and not sender.get("is_bot", False)
    )


def _chunks(text: str, size: int = _MAX_LEN):
    for i in range(0, len(text), size):
        yield text[i:i + size]


class TelegramBridge:
    def __init__(
        self,
        token: str,
        owner_id: int,
        on_command: Callable[[str], bool],
        log: Callable[[str], None] = print,
    ):
        self._token = token
        self._owner_id = owner_id
        self._on_command = on_command   # returns False if JARVIS can't take it now
        self._log = log
        self._offset: int | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @classmethod
    def from_env(cls, on_command, log=print) -> "TelegramBridge | None":
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        owner = os.environ.get("TELEGRAM_OWNER_ID", "").strip()
        if not token or not owner:
            return None
        try:
            return cls(token, int(owner), on_command, log)
        except ValueError:
            log("Telegram: TELEGRAM_OWNER_ID must be a number — bridge disabled.")
            return None

    # ── lifecycle ────────────────────────────────────────────────────────
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="telegram-bridge", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    # ── outgoing ─────────────────────────────────────────────────────────
    def send(self, text: str) -> None:
        """Send text to the owner. Safe to call from any thread."""
        text = (text or "").strip()
        if not text:
            return
        for part in _chunks(text):
            try:
                self._call("sendMessage", {"chat_id": self._owner_id, "text": part}, timeout=15)
            except Exception as e:
                self._log(f"Telegram: send failed ({type(e).__name__}).")
                return

    # ── internals ────────────────────────────────────────────────────────
    def _call(self, method: str, payload: dict, timeout: int):
        url = _API.format(token=self._token, method=method)
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()

    def _skip_backlog(self) -> None:
        data = self._call("getUpdates", {"offset": -1, "timeout": 0}, timeout=15)
        results = data.get("result") or []
        if results:
            self._offset = results[-1]["update_id"] + 1

    def _run(self) -> None:
        try:
            self._skip_backlog()
        except Exception as e:
            self._log(f"Telegram: could not start ({type(e).__name__}) — check the token.")
            return
        self._log("Telegram: bridge online (owner-only).")
        failures = 0
        while not self._stop.is_set():
            try:
                payload = {"timeout": _POLL_TIMEOUT, "allowed_updates": ["message"]}
                if self._offset is not None:
                    payload["offset"] = self._offset
                data = self._call("getUpdates", payload, timeout=_POLL_TIMEOUT + 10)
                failures = 0
                for upd in data.get("result") or []:
                    self._offset = upd["update_id"] + 1
                    self._handle(upd)
            except Exception as e:
                failures += 1
                self._log(f"Telegram: poll error ({type(e).__name__}).")
                time.sleep(min(5 * failures, 60))

    def _handle(self, upd: dict) -> None:
        if not is_authorized(upd, self._owner_id):
            self._log("Telegram: ignored a message from an unauthorized sender.")
            return
        text = (upd["message"].get("text") or "").strip()
        if not text:
            self.send("I can only read text messages.")
            return
        self._log("Telegram: command received.")
        if not self._on_command(text):
            self.send("JARVIS isn't connected right now. Try again in a moment.")
