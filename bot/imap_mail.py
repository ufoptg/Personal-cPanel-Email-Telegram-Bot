"""IMAP helpers for listing and reading inbox messages."""

from __future__ import annotations

import email
import imaplib
import re
from dataclasses import dataclass
from email.header import decode_header, make_header
from email.message import Message
from html import unescape
from typing import Iterable

from bot.config import Config


@dataclass(frozen=True)
class MessageOverview:
    uid: str
    subject: str
    from_: str
    date: str


@dataclass(frozen=True)
class MessageBody:
    uid: str
    subject: str
    from_: str
    date: str
    body: str
    truncated: bool


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


class ImapError(Exception):
    pass


def _decode_header_value(raw: str | None) -> str:
    if not raw:
        return "(none)"
    try:
        return str(make_header(decode_header(raw)))
    except Exception:  # noqa: BLE001
        return raw


def _html_to_text(html: str) -> str:
    text = _TAG_RE.sub(" ", html)
    text = unescape(text)
    return _WS_RE.sub(" ", text).strip()


def _extract_body(msg: Message) -> str:
    if msg.is_multipart():
        plain_parts: list[str] = []
        html_parts: list[str] = []
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get("Content-Disposition", "").lower().startswith("attachment"):
                continue
            ctype = part.get_content_type()
            try:
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
            except Exception:  # noqa: BLE001
                continue
            if ctype == "text/plain":
                plain_parts.append(text)
            elif ctype == "text/html":
                html_parts.append(_html_to_text(text))
        if plain_parts:
            joined = "\n".join(plain_parts).strip()
            if joined:
                return joined
        if html_parts:
            joined = "\n".join(html_parts).strip()
            if joined:
                return joined
        return "(no readable body)"

    try:
        payload = msg.get_payload(decode=True) or b""
        charset = msg.get_content_charset() or "utf-8"
        text = payload.decode(charset, errors="replace")
    except Exception:  # noqa: BLE001
        return "(unable to decode body)"
    if msg.get_content_type() == "text/html":
        return _html_to_text(text) or "(empty body)"
    return text.strip() or "(empty body)"


def _raw_from_fetch(data: list) -> bytes | None:
    """Pick the largest literal payload from an IMAP FETCH response."""
    best: bytes | None = None
    for item in data:
        if not isinstance(item, tuple) or len(item) < 2:
            continue
        payload = item[1]
        if isinstance(payload, memoryview):
            payload = payload.tobytes()
        if not isinstance(payload, (bytes, bytearray)):
            continue
        raw = bytes(payload)
        if best is None or len(raw) > len(best):
            best = raw
    return best


class ImapClient:
    def __init__(self, config: Config) -> None:
        self._config = config

    def _connect(self, address: str, password: str) -> imaplib.IMAP4_SSL:
        try:
            client = imaplib.IMAP4_SSL(self._config.imap_host, self._config.imap_port)
            client.login(address, password)
            typ, _ = client.select("INBOX", readonly=True)
            if typ != "OK":
                client.logout()
                raise ImapError("Failed to select INBOX")
            return client
        except imaplib.IMAP4.error as exc:
            raise ImapError(f"IMAP login failed: {exc}") from exc
        except OSError as exc:
            raise ImapError(f"IMAP connection failed: {exc}") from exc

    def list_recent(self, address: str, password: str, limit: int = 10) -> list[MessageOverview]:
        limit = max(1, min(limit, 50))
        client = self._connect(address, password)
        try:
            typ, data = client.uid("search", None, "ALL")
            if typ != "OK" or not data or not data[0]:
                return []
            uids = data[0].split()
            recent = uids[-limit:]
            recent.reverse()  # newest first
            return list(self._fetch_overviews(client, recent))
        finally:
            try:
                client.logout()
            except Exception:  # noqa: BLE001
                pass

    def fetch_message(self, address: str, password: str, uid: str, max_chars: int = 3500) -> MessageBody:
        client = self._connect(address, password)
        try:
            # BODY.PEEK[] returns the full RFC822 message without setting \Seen.
            # Do not combine with RFC822.HEADER — that returns header-only bytes first
            # and we used to parse that as the whole message (empty body).
            raw: bytes | None = None
            for spec in ("(BODY.PEEK[])", "(RFC822)"):
                typ, data = client.uid("fetch", uid, spec)
                if typ != "OK" or not data:
                    continue
                raw = _raw_from_fetch(data)
                if raw:
                    break
            if not raw:
                raise ImapError(f"Message UID {uid} not found")

            msg = email.message_from_bytes(raw)
            subject = _decode_header_value(msg.get("Subject"))
            from_ = _decode_header_value(msg.get("From"))
            date = msg.get("Date") or "(unknown date)"
            body = _extract_body(msg)
            truncated = False
            if len(body) > max_chars:
                body = body[:max_chars].rstrip() + "\n\n…(truncated)"
                truncated = True
            return MessageBody(
                uid=uid,
                subject=subject,
                from_=from_,
                date=date,
                body=body,
                truncated=truncated,
            )
        finally:
            try:
                client.logout()
            except Exception:  # noqa: BLE001
                pass

    def _fetch_overviews(self, client: imaplib.IMAP4_SSL, uids: Iterable[bytes]) -> Iterable[MessageOverview]:
        for uid_b in uids:
            uid = uid_b.decode("ascii", errors="replace")
            typ, data = client.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if typ != "OK" or not data or not isinstance(data[0], tuple):
                continue
            header_bytes = data[0][1]
            msg = email.message_from_bytes(header_bytes)
            yield MessageOverview(
                uid=uid,
                subject=_decode_header_value(msg.get("Subject")),
                from_=_decode_header_value(msg.get("From")),
                date=msg.get("Date") or "(unknown date)",
            )
