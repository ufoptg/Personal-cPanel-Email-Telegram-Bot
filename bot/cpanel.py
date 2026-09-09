"""cPanel UAPI client for email account management."""

from __future__ import annotations

from typing import Any

import httpx

from bot.config import Config


class CpanelError(Exception):
    def __init__(self, message: str, *, details: Any = None) -> None:
        super().__init__(message)
        self.details = details


class CpanelClient:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._auth_header = f"cpanel {config.cpanel_user}:{config.cpanel_api_token}"

    async def _execute(self, module: str, function: str, params: dict[str, Any]) -> Any:
        url = f"{self._config.cpanel_base_url}/execute/{module}/{function}"
        async with httpx.AsyncClient(
            verify=self._config.cpanel_verify_ssl,
            timeout=60.0,
        ) as client:
            response = await client.get(
                url,
                params=params,
                headers={"Authorization": self._auth_header},
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise CpanelError(
                f"cPanel returned non-JSON (HTTP {response.status_code})",
                details=response.text[:500],
            ) from exc

        if response.status_code >= 400:
            raise CpanelError(
                f"cPanel HTTP {response.status_code}",
                details=payload,
            )

        # UAPI shape: {"status": 1|0, "errors": [...], "data": ...} or nested under result
        result = payload.get("result", payload)
        status = result.get("status", payload.get("status"))
        if status not in (1, True, "1"):
            errors = result.get("errors") or payload.get("errors") or ["Unknown cPanel error"]
            if isinstance(errors, list):
                message = "; ".join(str(e) for e in errors)
            else:
                message = str(errors)
            raise CpanelError(message, details=payload)
        return result.get("data", payload.get("data"))

    async def add_pop(
        self,
        *,
        localpart: str,
        password: str,
        domain: str,
        quota: int = 0,
    ) -> Any:
        return await self._execute(
            "Email",
            "add_pop",
            {
                "email": localpart,
                "password": password,
                "domain": domain,
                "quota": quota,
            },
        )

    async def del_pop(self, *, localpart: str, domain: str) -> Any:
        # email param is typically the full address or localpart depending on cPanel version;
        # full address is widely accepted.
        return await self._execute(
            "Email",
            "del_pop",
            {
                "email": f"{localpart}@{domain}",
            },
        )
