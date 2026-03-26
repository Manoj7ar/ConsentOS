import { ApiError } from "@/lib/api";

export function getDisplayErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    switch (error.code) {
      case "auth0_config_missing":
        return "Auth0 is not configured for this environment. Set the required frontend AUTH0_* variables.";
      case "auth_session_missing":
        return "Your browser session is missing or expired. Log in with Auth0 again.";
      case "auth_access_token_unavailable":
        return "Your Auth0 session could not refresh. Log in again before running agent actions.";
      case "auth_my_account_token_unavailable":
        return "Connected-account sync needs an Auth0 My Account token. Reauthenticate and confirm the required scopes are enabled.";
      case "auth_my_account_sync_failed":
        return "Auth0 rejected the connected-account sync request. Check Connected Accounts setup and granted scopes.";
      default:
        return error.message;
    }
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Request failed.";
}
