from __future__ import annotations

import secrets

from fastapi import Request


async def attach_request_context(request: Request, call_next):
    request.state.request_id = secrets.token_hex(8)
    response = await call_next(request)
    response.headers["x-request-id"] = request.state.request_id
    return response
