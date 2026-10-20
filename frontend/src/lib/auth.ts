import { WebStorageStateStore } from "oidc-client-ts";

const authority = import.meta.env.VITE_COGNITO_AUTHORITY?.trim();
const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID?.trim();
const origin = typeof window === "undefined" ? "http://localhost:5173" : window.location.origin;

export const isAuthEnabled = Boolean(authority && clientId);

export const authConfig = {
  authority: authority ?? "",
  client_id: clientId ?? "",
  redirect_uri: import.meta.env.VITE_COGNITO_REDIRECT_URI ?? `${origin}/auth/callback`,
  post_logout_redirect_uri: `${origin}/`,
  response_type: "code",
  scope: "openid email profile",
  automaticSilentRenew: true,
  userStore: new WebStorageStateStore({ store: window.sessionStorage }),
};
