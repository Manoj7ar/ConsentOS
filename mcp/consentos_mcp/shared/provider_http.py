from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

import httpx

from consentos_mcp.shared.auth_context import AgentContext
from consentos_mcp.shared.backend_client import BackendClient


@dataclass(slots=True)
class ProviderApiError(Exception):
    provider: str
    detail: str
    status_code: int | None = None

    def __str__(self) -> str:
        return self.detail


async def exchange_provider_access_token(
    *,
    backend: BackendClient,
    context: AgentContext,
    provider: str,
) -> str:
    payload = await backend.exchange_token(context, provider)
    token = payload.get("external_access_token")
    if not token:
        raise ProviderApiError(provider=provider, detail="Token Vault exchange did not return an access token.")
    return token


async def request_json(
    *,
    provider: str,
    method: str,
    url: str,
    access_token: str,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    form_body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    response = await request(
        provider=provider,
        method=method,
        url=url,
        access_token=access_token,
        params=params,
        json_body=json_body,
        form_body=form_body,
        headers=headers,
        timeout=timeout,
    )
    payload = _parse_json(provider, response)
    return _raise_if_embedded_error(provider, payload)


async def request(
    *,
    provider: str,
    method: str,
    url: str,
    access_token: str,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    form_body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> httpx.Response:
    request_headers = {"authorization": f"Bearer {access_token}"}
    if headers:
        request_headers.update(headers)

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.request(
            method,
            url,
            params=params,
            json=json_body,
            data=form_body,
            headers=request_headers,
        )

    if response.status_code >= 400:
        detail = _extract_error_detail(response)
        raise ProviderApiError(provider=provider, detail=detail, status_code=response.status_code)
    return response


async def create_failed_activity(
    *,
    backend: BackendClient,
    context: AgentContext,
    provider: str,
    tool_name: str,
    action: str,
    input_payload: dict[str, Any],
    detail: str,
) -> dict[str, Any]:
    return await backend.create_activity(
        context,
        provider=provider,
        tool_name=tool_name,
        action=action,
        input={**input_payload, "error_detail": detail},
        status="failed",
    )


def failed_result(
    *,
    provider: str,
    tool_name: str,
    activity_log_id: int | None,
    detail: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "failed",
        "provider": provider,
        "tool_name": tool_name,
        "detail": detail,
    }
    if activity_log_id is not None:
        payload["activity_log_id"] = activity_log_id
    return payload


def cents_from_amount(amount: str) -> int:
    normalized = amount.strip().replace("$", "").replace(",", "")
    try:
        decimal_value = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"Unsupported amount format: {amount}") from exc
    return int((decimal_value * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_currency_amount(amount_minor: int | None, currency: str | None = None) -> str:
    if amount_minor is None:
        return "unknown"
    normalized_currency = (currency or "usd").upper()
    amount_major = Decimal(amount_minor) / Decimal("100")
    symbol = "$" if normalized_currency == "USD" else f"{normalized_currency} "
    return f"{symbol}{amount_major:,.2f}"


def _parse_json(provider: str, response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderApiError(provider=provider, detail="Provider returned a non-JSON response.") from exc
    if not isinstance(payload, dict):
        raise ProviderApiError(provider=provider, detail="Provider returned an unexpected JSON payload.")
    return payload


def _raise_if_embedded_error(provider: str, payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("ok") is False:
        error = payload.get("error", "unknown_error")
        raise ProviderApiError(provider=provider, detail=f"{provider} API error: {error}")
    if "error" in payload and isinstance(payload["error"], dict):
        message = payload["error"].get("message") or payload["error"].get("type") or "Provider returned an error."
        raise ProviderApiError(provider=provider, detail=message)
    return payload


def _extract_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        return text or f"Provider request failed with status {response.status_code}."

    if isinstance(payload, dict):
        if isinstance(payload.get("error"), dict):
            message = payload["error"].get("message") or payload["error"].get("type")
            if message:
                return str(message)
        if payload.get("error_description"):
            return str(payload["error_description"])
        if payload.get("error"):
            return str(payload["error"])
        if payload.get("message"):
            return str(payload["message"])
    return f"Provider request failed with status {response.status_code}."
