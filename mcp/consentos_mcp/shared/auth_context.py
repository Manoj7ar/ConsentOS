from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class AgentContext:
    user_sub: str
    email: str | None
    auth0_subject_token: str | None = None
    agent_name: str = "FreelanceCOOAgent"
    workflow_id: str | None = None
    workflow_run_id: str | None = None


def default_server_context() -> AgentContext:
    return AgentContext(
        user_sub=os.getenv("CONSENTOS_DEFAULT_USER_SUB", "auth0|demo-user"),
        email=os.getenv("CONSENTOS_DEFAULT_USER_EMAIL", "demo@example.com"),
        auth0_subject_token=os.getenv("CONSENTOS_AUTH0_SUBJECT_TOKEN"),
        agent_name=os.getenv("CONSENTOS_DEFAULT_AGENT", "ExternalMCPHost"),
    )
