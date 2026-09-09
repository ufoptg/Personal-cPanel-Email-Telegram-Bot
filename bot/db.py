"""SQLite persistence for bot-created email accounts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite


@dataclass(frozen=True)
class Account:
    id: int
    localpart: str
    domain: str
    password_enc: str
    created_at: str
    telegram_user_id: int

    @property
    def address(self) -> str:
        return f"{self.localpart}@{self.domain}"


class AccountStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def init(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    localpart TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    password_enc TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    telegram_user_id INTEGER NOT NULL,
                    UNIQUE(localpart, domain)
                )
                """
            )
            await db.commit()

    async def add(
        self,
        *,
        localpart: str,
        domain: str,
        password_enc: str,
        telegram_user_id: int,
    ) -> Account:
        created_at = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                INSERT INTO accounts (localpart, domain, password_enc, created_at, telegram_user_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (localpart.lower(), domain.lower(), password_enc, created_at, telegram_user_id),
            )
            await db.commit()
            row_id = cursor.lastrowid
            row = await (
                await db.execute("SELECT * FROM accounts WHERE id = ?", (row_id,))
            ).fetchone()
        return self._row_to_account(row)

    async def list_all(self) -> list[Account]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (
                await db.execute(
                    "SELECT * FROM accounts ORDER BY created_at DESC, id DESC"
                )
            ).fetchall()
        return [self._row_to_account(row) for row in rows]

    async def get_by_local_or_address(self, value: str, domain: str) -> Account | None:
        value = value.strip().lower()
        if "@" in value:
            localpart, _, addr_domain = value.partition("@")
            if addr_domain != domain.lower():
                return None
        else:
            localpart = value
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT * FROM accounts WHERE localpart = ? AND domain = ?",
                    (localpart, domain.lower()),
                )
            ).fetchone()
        return self._row_to_account(row) if row else None

    async def delete(self, localpart: str, domain: str) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "DELETE FROM accounts WHERE localpart = ? AND domain = ?",
                (localpart.lower(), domain.lower()),
            )
            await db.commit()
            return cursor.rowcount > 0

    @staticmethod
    def _row_to_account(row: aiosqlite.Row) -> Account:
        return Account(
            id=row["id"],
            localpart=row["localpart"],
            domain=row["domain"],
            password_enc=row["password_enc"],
            created_at=row["created_at"],
            telegram_user_id=row["telegram_user_id"],
        )
