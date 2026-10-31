import { createContext, useContext } from "react";
import type { Me } from "./api/client";

/**
 * Who is using the planner (design_auth.md).
 *
 * `undefined` while the server is being asked, `null` when nobody is logged
 * in. The cookie itself is HttpOnly, so this is the browser's only picture of
 * the session - kept current by `/auth/me` at start, by the login and logout
 * calls, and by any 401 on the way.
 */
export interface SessionState {
  user: Me | null | undefined;
  /** False on a server without a login (`AUTH=off`): there is no one to log out. */
  canLogOut: boolean;
  loginAs: (email: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const SessionContext = createContext<SessionState | null>(null);

export function useSession(): SessionState {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside a SessionProvider");
  return value;
}
