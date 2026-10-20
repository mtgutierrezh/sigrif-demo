import { useMemo, type ReactNode } from "react";
import { AuthProvider, useAuth } from "react-oidc-context";

import { authConfig, isAuthEnabled } from "../lib/auth";
import { SessionContext, type Session } from "./session";

function LocalSession({ children }: { children: ReactNode }) {
  const value = useMemo<Session>(
    () => ({
      status: "authenticated",
      name: "Demo local",
      canSimulate: true,
      signIn: () => undefined,
      signOut: () => undefined,
    }),
    [],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

function OidcSession({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const groups = useMemo(
    () => (auth.user?.profile["cognito:groups"] as string[] | undefined) ?? [],
    [auth.user],
  );
  const value = useMemo<Session>(
    () => ({
      status: auth.isLoading ? "loading" : auth.isAuthenticated ? "authenticated" : "anonymous",
      name: auth.user?.profile.name ?? auth.user?.profile.email,
      token: auth.user?.access_token,
      canSimulate: groups.includes("operadores"),
      signIn: () => void auth.signinRedirect(),
      signOut: () => void auth.removeUser(),
    }),
    [auth, groups],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function SessionProvider({ children }: { children: ReactNode }) {
  if (!isAuthEnabled) {
    return <LocalSession>{children}</LocalSession>;
  }
  return (
    <AuthProvider {...authConfig}>
      <OidcSession>{children}</OidcSession>
    </AuthProvider>
  );
}
