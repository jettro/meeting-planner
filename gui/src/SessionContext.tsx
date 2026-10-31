import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { ANONYMOUS, auth, UNAUTHORIZED, type Me } from "./api/client";
import { SessionContext, type SessionState } from "./session";

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null | undefined>(undefined);

  useEffect(() => {
    let current = true;
    auth
      .me()
      .then((me) => current && setUser(me))
      .catch(() => current && setUser(null));
    // Any 401, from any call, ends the session here too.
    const ended = () => setUser((was) => (was === ANONYMOUS ? was : null));
    window.addEventListener(UNAUTHORIZED, ended);
    return () => {
      current = false;
      window.removeEventListener(UNAUTHORIZED, ended);
    };
  }, []);

  const loginAs = useCallback(async (email: string) => {
    setUser(await auth.loginAs(email));
  }, []);

  const logout = useCallback(async () => {
    await auth.logout();
    setUser(null);
  }, []);

  const value = useMemo<SessionState>(
    () => ({ user, canLogOut: user !== ANONYMOUS, loginAs, logout }),
    [user, loginAs, logout],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
