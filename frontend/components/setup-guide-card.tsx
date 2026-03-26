"use client";

type SetupLink = {
  href: string;
  label: string;
};

type SetupItem = {
  title: string;
  envs?: string[];
  location: string;
  detail: string;
  links: SetupLink[];
};

const LOCAL_SECRETS: SetupItem[] = [
  {
    title: "Auth0 browser app",
    envs: ["AUTH0_DOMAIN", "AUTH0_CLIENT_ID", "AUTH0_CLIENT_SECRET", "AUTH0_SECRET", "APP_BASE_URL"],
    location: "ConsentOS .env plus your Auth0 Regular Web App settings",
    detail:
      "These power Next.js login, logout, callback, and browser session handling. AUTH0_SECRET is generated locally by you, not issued by Auth0.",
    links: [
      {
        href: "https://auth0.com/docs/quickstart/webapp/nextjs",
        label: "Auth0 Next.js quickstart"
      },
      {
        href: "https://auth0.com/docs/get-started/applications/application-settings",
        label: "Auth0 application settings"
      }
    ]
  },
  {
    title: "Auth0 backend Token Vault exchange app",
    envs: ["BACKEND_AUTH0_DOMAIN", "BACKEND_AUTH0_CLIENT_ID", "BACKEND_AUTH0_CLIENT_SECRET"],
    location: "ConsentOS .env from an Auth0 machine-to-machine application",
    detail:
      "The backend uses these credentials to exchange Auth0 user tokens for provider access tokens from Token Vault.",
    links: [
      {
        href: "https://auth0.com/docs/get-started/auth0-overview/create-applications/machine-to-machine-apps",
        label: "Register an Auth0 M2M application"
      },
      {
        href: "https://auth0.com/docs/secure/tokens/token-vault/connected-accounts-for-token-vault",
        label: "Connected Accounts for Token Vault"
      }
    ]
  },
  {
    title: "Auth0 CIBA approval app",
    envs: ["BACKEND_AUTH0_CIBA_CLIENT_ID", "BACKEND_AUTH0_CIBA_CLIENT_SECRET"],
    location: "ConsentOS .env from an Auth0 application authorized for CIBA",
    detail:
      "These are used for step-up approvals when risky tools need phone-based authorization. The repo expects explicit CIBA env vars even if your tenant reuses another Auth0 app.",
    links: [
      {
        href: "https://auth0.com/docs/get-started/authentication-and-authorization-flow/client-initiated-backchannel-authentication-flow/user-authorization-with-ciba",
        label: "Auth0 CIBA user authorization"
      },
      {
        href: "https://auth0.com/ai/docs/async-authorization",
        label: "Auth0 async authorization for agents"
      }
    ]
  },
  {
    title: "Gemini model access for the orchestrator",
    envs: ["MCP_GEMINI_API_KEY"],
    location: "ConsentOS .env from your Google AI Studio or Gemini API project",
    detail:
      "The built-in orchestrator uses this server-side key to call the model. Do not put it in frontend code.",
    links: [
      {
        href: "https://ai.google.dev/gemini-api/docs/api-key",
        label: "Gemini API key setup"
      },
      {
        href: "https://ai.google.dev/gemini-api/docs/models",
        label: "Gemini model reference"
      }
    ]
  },
  {
    title: "Locally generated shared secrets",
    envs: ["AUTH0_SECRET", "INTERNAL_API_SHARED_SECRET"],
    location: "Generated locally and stored in ConsentOS .env",
    detail:
      "Generate strong random values yourself. For example: py -c \"import secrets; print(secrets.token_urlsafe(48))\" and run it once per secret.",
    links: []
  }
];

const AUTH0_CONNECTIONS: SetupItem[] = [
  {
    title: "Google connection in Auth0",
    location: "Auth0 Dashboard > Authentication > Social Connections > Google",
    detail:
      "Create a Google OAuth web-server client, then paste its client ID and client secret into the Auth0 Google connection and enable Connected Accounts for Token Vault.",
    links: [
      {
        href: "https://developers.google.com/identity/protocols/oauth2/web-server",
        label: "Google OAuth 2.0 for web server apps"
      },
      {
        href: "https://auth0.com/docs/secure/tokens/token-vault/connected-accounts-for-token-vault",
        label: "Auth0 Connected Accounts setup"
      }
    ]
  },
  {
    title: "GitHub connection in Auth0",
    location: "Auth0 Dashboard > Authentication > Social Connections > GitHub",
    detail:
      "Create a GitHub OAuth app and paste the resulting client ID and client secret into the Auth0 GitHub connection.",
    links: [
      {
        href: "https://docs.github.com/en/developers/apps/creating-an-oauth-app",
        label: "Create a GitHub OAuth app"
      }
    ]
  },
  {
    title: "Slack connection in Auth0",
    location: "Auth0 Dashboard > Authentication > Social Connections > Slack",
    detail:
      "Create a Slack app, configure OAuth scopes, then copy its client ID and client secret into the Auth0 Slack connection.",
    links: [
      {
        href: "https://api.slack.com/authentication/quickstart",
        label: "Slack app OAuth quickstart"
      },
      {
        href: "https://api.slack.com/docs/oauth-safety",
        label: "Slack OAuth security guidance"
      }
    ]
  },
  {
    title: "Stripe Connect connection in Auth0",
    location: "Auth0 Dashboard > Authentication > Social Connections > Stripe Connect",
    detail:
      "Create a Stripe Connect OAuth app, then use that client ID and client secret in the Auth0 Stripe Connect social connection.",
    links: [
      {
        href: "https://docs.stripe.com/connect/oauth-reference",
        label: "Stripe Connect OAuth reference"
      },
      {
        href: "https://auth0.com/ai/docs/integrations/stripe-connect",
        label: "Auth0 Stripe Connect integration"
      }
    ]
  }
];

export function SetupGuideCard() {
  return (
    <section className="setup-guide-card">
      <div className="setup-guide-card__header">
        <div>
          <p className="eyebrow">Setup Guide</p>
          <h3>Where to get the keys and credentials this repo expects</h3>
        </div>
      </div>

      <p className="muted setup-guide-summary">
        Strict live mode expects real Auth0 Connected Accounts, Token Vault exchange, and CIBA approval. You do not
        paste Gmail, GitHub, Slack, or Stripe user access tokens into ConsentOS; Auth0 stores those provider tokens and
        ConsentOS exchanges them only when the agent is authorized to act.
      </p>

      <div className="setup-guide-section">
        <h4>Put These In ConsentOS .env</h4>
        <div className="setup-guide-list">
          {LOCAL_SECRETS.map((item) => (
            <article className="setup-guide-item" key={item.title}>
              <div className="setup-guide-item__body">
                <strong>{item.title}</strong>
                {item.envs?.length ? <p className="setup-guide-envs">{item.envs.join(", ")}</p> : null}
                <p>{item.detail}</p>
                <p className="muted">Where it lives: {item.location}</p>
              </div>
              {item.links.length ? (
                <div className="setup-guide-links">
                  {item.links.map((link) => (
                    <a key={link.href} href={link.href} target="_blank" rel="noreferrer">
                      {link.label}
                    </a>
                  ))}
                </div>
              ) : null}
            </article>
          ))}
        </div>
      </div>

      <div className="setup-guide-section">
        <h4>Create These In Provider Dashboards, Then Paste Them Into Auth0</h4>
        <div className="setup-guide-list">
          {AUTH0_CONNECTIONS.map((item) => (
            <article className="setup-guide-item" key={item.title}>
              <div className="setup-guide-item__body">
                <strong>{item.title}</strong>
                <p>{item.detail}</p>
                <p className="muted">Where it lives: {item.location}</p>
              </div>
              <div className="setup-guide-links">
                {item.links.map((link) => (
                  <a key={link.href} href={link.href} target="_blank" rel="noreferrer">
                    {link.label}
                  </a>
                ))}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
