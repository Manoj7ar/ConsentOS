from __future__ import annotations

import argparse
import secrets
from pathlib import Path


PLACEHOLDER_VALUES = {
    "change-me",
    "replace-me",
    "replace-with-32-byte-random",
    "example.us.auth0.com",
    "your-tenant.us.auth0.com",
}
REQUIRED_MANUAL_KEYS = [
    "AUTH0_DOMAIN",
    "AUTH0_CLIENT_ID",
    "AUTH0_CLIENT_SECRET",
    "BACKEND_AUTH0_CLIENT_ID",
    "BACKEND_AUTH0_CLIENT_SECRET",
    "BACKEND_AUTH0_CIBA_CLIENT_ID",
    "BACKEND_AUTH0_CIBA_CLIENT_SECRET",
    "MCP_GEMINI_API_KEY",
]
SUGGESTED_KEYS = [
    "MCP_SLACK_MENTION_CHANNEL_IDS",
]


def parse_env(path: Path) -> tuple[list[str], dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return lines, values


def render_env(lines: list[str], values: dict[str, str]) -> str:
    rendered: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            rendered.append(line)
            continue
        key, _ = stripped.split("=", 1)
        rendered.append(f"{key}={values.get(key, '')}")
    return "\n".join(rendered) + "\n"


def is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    stripped = value.strip()
    if stripped == "":
        return True
    if stripped in PLACEHOLDER_VALUES:
        return True
    return stripped.startswith("your-tenant.")


def apply_overrides(values: dict[str, str], overrides: dict[str, str]) -> None:
    for key, value in overrides.items():
        values[key] = value


def ensure_generated_secrets(values: dict[str, str]) -> None:
    if is_placeholder(values.get("INTERNAL_API_SHARED_SECRET")):
        values["INTERNAL_API_SHARED_SECRET"] = secrets.token_urlsafe(48)
    if is_placeholder(values.get("AUTH0_SECRET")):
        values["AUTH0_SECRET"] = secrets.token_urlsafe(48)


def mirror_related_values(values: dict[str, str]) -> None:
    auth0_domain = values.get("AUTH0_DOMAIN", "").strip()
    if auth0_domain and is_placeholder(values.get("BACKEND_AUTH0_DOMAIN")):
        values["BACKEND_AUTH0_DOMAIN"] = auth0_domain

    backend_domain = values.get("BACKEND_AUTH0_DOMAIN", "").strip()
    if backend_domain and (not values.get("BACKEND_AUTH0_ISSUER", "").strip() or "your-tenant" in values["BACKEND_AUTH0_ISSUER"]):
        values["BACKEND_AUTH0_ISSUER"] = f"https://{backend_domain.rstrip('/')}/"

    auth0_audience = values.get("AUTH0_AUDIENCE", "").strip()
    if auth0_audience and not values.get("BACKEND_AUTH0_AUDIENCE", "").strip():
        values["BACKEND_AUTH0_AUDIENCE"] = auth0_audience

    if not values.get("BACKEND_PROXY_URL", "").strip():
        values["BACKEND_PROXY_URL"] = "http://localhost:8000"
    if not values.get("ORCHESTRATOR_BASE_URL", "").strip():
        values["ORCHESTRATOR_BASE_URL"] = "http://localhost:8100"
    if not values.get("APP_BASE_URL", "").strip():
        values["APP_BASE_URL"] = "http://localhost:3000"


def unresolved_keys(values: dict[str, str], keys: list[str]) -> list[str]:
    return [key for key in keys if is_placeholder(values.get(key))]


def parse_override_args(raw_pairs: list[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for pair in raw_pairs:
        if "=" not in pair:
            raise SystemExit(f"Invalid --set value '{pair}'. Use KEY=VALUE.")
        key, value = pair.split("=", 1)
        overrides[key] = value
    return overrides


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap ConsentOS .env from .env.example, generate secrets, and highlight missing manual values."
    )
    parser.add_argument("--example", default=".env.example", help="Path to the example env file.")
    parser.add_argument("--output", default=".env", help="Path to write the generated env file.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write files; print the missing-value report only.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file instead of merging into it.")
    parser.add_argument("--set", action="append", default=[], help="Override env values with KEY=VALUE.")
    args = parser.parse_args()

    example_path = Path(args.example)
    output_path = Path(args.output)
    template_lines, template_values = parse_env(example_path)

    if output_path.exists() and not args.force:
        _, existing_values = parse_env(output_path)
        template_values.update(existing_values)

    apply_overrides(template_values, parse_override_args(args.set))
    ensure_generated_secrets(template_values)
    mirror_related_values(template_values)

    missing_required = unresolved_keys(template_values, REQUIRED_MANUAL_KEYS)
    missing_suggested = unresolved_keys(template_values, SUGGESTED_KEYS)

    if not args.dry_run:
        output_path.write_text(render_env(template_lines, template_values), encoding="utf-8")
        print(f"Wrote {output_path}")
    else:
        print("Dry run only; no files written.")

    print()
    print("Generated automatically:")
    print("- INTERNAL_API_SHARED_SECRET")
    print("- AUTH0_SECRET")
    print("- mirrored BACKEND_AUTH0_DOMAIN / BACKEND_AUTH0_ISSUER when AUTH0_DOMAIN is set")
    print()
    if missing_required:
        print("Still required from real integrations:")
        for key in missing_required:
            print(f"- {key}")
    else:
        print("All required strict-live keys are populated.")
    if missing_suggested:
        print()
        print("Recommended to review:")
        for key in missing_suggested:
            print(f"- {key}")

    print()
    print("Next steps:")
    print("- Fill the remaining required values in .env")
    print("- Start the stack with docker-compose up --build")
    print("- Check http://localhost:8000/health/ready and http://localhost:8100/health/ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
