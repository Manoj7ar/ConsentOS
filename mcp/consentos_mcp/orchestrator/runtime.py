from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from consentos_mcp.orchestrator.agent import FreelanceCOOAgent
from consentos_mcp.orchestrator.tool_catalog import ToolCatalog
from consentos_mcp.shared.auth_context import AgentContext
from consentos_mcp.shared.settings import get_settings

app = FastAPI(title="ConsentOS Orchestrator")
catalog = ToolCatalog()
agent = FreelanceCOOAgent(catalog)


class ChatMessage(BaseModel):
    role: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    assistant_message: str
    tool_events: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def resolve_context(
    x_consentos_internal_secret: str | None = Header(default=None),
    x_consentos_user_sub: str | None = Header(default=None),
    x_consentos_user_email: str | None = Header(default=None),
    x_consentos_auth0_subject_token: str | None = Header(default=None),
) -> AgentContext:
    settings = get_settings()
    if x_consentos_internal_secret != settings.internal_api_shared_secret or not x_consentos_user_sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing trusted ConsentOS identity headers.")
    return AgentContext(
        user_sub=x_consentos_user_sub,
        email=x_consentos_user_email,
        auth0_subject_token=x_consentos_auth0_subject_token,
        agent_name="FreelanceCOOAgent",
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready() -> dict[str, Any]:
    settings = get_settings()
    checks = []
    if settings.gemini_api_key:
        checks.append({"key": "gemini", "status": "ok", "detail": "Gemini API key is configured."})
    else:
        checks.append({"key": "gemini", "status": "error", "detail": "MCP_GEMINI_API_KEY is missing."})
    if settings.internal_api_shared_secret and settings.internal_api_shared_secret != "change-me":
        checks.append({"key": "internal_api_secret", "status": "ok", "detail": "Internal API shared secret is configured."})
    else:
        checks.append(
            {
                "key": "internal_api_secret",
                "status": "error",
                "detail": "INTERNAL_API_SHARED_SECRET must be set to a non-placeholder value.",
            }
        )
    status_value = "ok" if all(check["status"] == "ok" for check in checks) else "degraded"
    return {"status": status_value, "checks": checks}


@app.get("/tools")
def list_tools() -> dict[str, Any]:
    return {
        "tools": [asdict(tool) for tool in catalog.list_tools()],
        "resources": [asdict(resource) for resource in catalog.list_resources()],
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, context: AgentContext = Depends(resolve_context)) -> ChatResponse:
    result = await agent.respond([message.model_dump() for message in payload.messages], context)
    return ChatResponse(**result)
