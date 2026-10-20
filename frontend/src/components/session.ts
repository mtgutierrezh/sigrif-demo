import { createContext, useContext } from "react";

export interface Session {
  status: "loading" | "authenticated" | "anonymous";
  name?: string;
  token?: string;
  canSimulate: boolean;
  signIn: () => void;
  signOut: () => void;
}

export const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) {
    throw new Error("useSession must be used within SessionProvider");
  }
  return session;
}
