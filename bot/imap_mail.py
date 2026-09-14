"""IMAP helpers for listing and reading mailbox messages."""

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
_LIST_QUOTED_RE = re.compile(rb'"((?:\\.|[^"\\])*)"\s*$')
_LIST_ATOM_RE = re.compile(rb"(\S+)\s*$")

# Common Spam/Junk folder names across cPanel, Dovecot, Gmail-style hosts.
_SPAM_CANDIDATES = (
    "Spam",
    "spam",
    "Junk",
    "junk",
    "INBOX.Spam",
    "INBOX.spam",
    "INBOX.Junk",
    "INBOX.junk",
    "Junk E-mail",
    "Bulk Mail",
    "[Gmail]/Spam",
)


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


def _mailbox_basename(name: str) -> str:
    for sep in ("/", "."):
        if sep in name:
            return name.rsplit(sep, 1)[-1]
    return name


def _parse_list_mailbox(line: bytes) -> str | None:
    """Extract mailbox name from an IMAP LIST response line."""
    match = _LIST_QUOTED_RE.search(line)
    if match:
        raw = match.group(1).replace(rb"\"", b'"').replace(rb"\\", b"\\")
        return raw.decode("utf-8", errors="replace")
    match = _LIST_ATOM_RE.search(line)
    if match:
        return match.group(1).decode("utf-8", errors="replace")
    return None


def _is_spam_mailbox(name: str) -> bool:
    base = _mailbox_basename(name).lower().replace("_", " ").replace("-", " ")
    if base in {"spam", "junk", "bulk mail", "junk e mail", "junk email"}:
        return True
    return "spam" in base or "junk" in base


class ImapClient:
    def __init__(self, config: Config) -> None:
        self._config = config

    def _login(self, address: str, password: str) -> imaplib.IMAP4_SSL:
        try:
            client = imaplib.IMAP4_SSL(self._config.imap_host, self._config.imap_port)
            client.login(address, password)
            return client
        except imaplib.IMAP4.error as exc:
            raise ImapError(f"IMAP login failed: {exc}") from exc
        except OSError as exc:
            raise ImapError(f"IMAP connection failed: {exc}") from exc

    def _select(self, client: imaplib.IMAP4_SSL, mailbox: str) -> None:
        typ, _ = client.select(mailbox, readonly=True)
        if typ != "OK":
            raise ImapError(f"Failed to select mailbox {mailbox!r}")

    def _connect(self, address: str, password: str, mailbox: str = "INBOX") -> imaplib.IMAP4_SSL:
        client = self._login(address, password)
        try:
            self._select(client, mailbox)
        except ImapError:
            try:
                client.logout()
            except Exception:  # noqa: BLE001
                pass
            raise
        return client

    def _list_mailboxes(self, client: imaplib.IMAP4_SSL) -> list[str]:
        typ, data = client.list()
        if typ != "OK" or not data:
            return []
        names: list[str] = []
        for item in data:
            if not isinstance(item, (bytes, bytearray)):
                continue
            name = _parse_list_mailbox(bytes(item))
            if name:
                names.append(name)
        return names

    def resolve_spam_mailbox(self, address: str, password: str) -> str:
        """Find the account's Spam/Junk folder name."""
        client = self._login(address, password)
        try:
            listed = self._list_mailboxes(client)
            for name in listed:
                if _is_spam_mailbox(name):
                    return name
            # Fall back to trying common names even if LIST omitted them.
            for name in _SPAM_CANDIDATES:
                try:
                    self._select(client, name)
                    return name
                except ImapError:
                    continue
            raise ImapError(
                "No Spam/Junk folder found. "
                "Create one in webmail, or ask the host which IMAP folder name they use."
            )
        finally:
            try:
                client.logout()
            except Exception:  # noqa: BLE001
                pass

    def list_recent(
        self,
        address: str,
        password: str,
        limit: int = 10,
        mailbox: str = "INBOX",
    ) -> list[MessageOverview]:
        limit = max(1, min(limit, 50))
        client = self._connect(address, password, mailbox=mailbox)
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

    def fetch_message(
        self,
        address: str,
        password: str,
        uid: str,
        max_chars: int = 3500,
        mailbox: str = "INBOX",
    ) -> MessageBody:
        client = self._connect(address, password, mailbox=mailbox)
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
