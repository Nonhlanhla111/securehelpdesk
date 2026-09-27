import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, apiErrorMessage, setToken, setUnauthorizedHandler } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true); // true until the initial /me check resolves

  const clearSession = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(clearSession);
    // No stored token to restore (by design: memory-only), so refreshing
    // the page always lands back on the login screen.
    setLoading(false);
  }, [clearSession]);

  const login = useCallback(async (email, password) => {
    const { data } = await api.post("/api/auth/login", { email, password });
    setToken(data.access_token);
    const me = await api.get("/api/auth/me");
    setUser(me.data);
    return me.data;
  }, []);

  const register = useCallback(async (email, fullName, password) => {
    await api.post("/api/auth/register", { email, full_name: fullName, password });
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/api/auth/logout");
    } catch {
      // Already unauthenticated/expired — fine, we're clearing local state anyway.
    }
    clearSession();
  }, [clearSession]);

  const changePassword = useCallback(async (currentPassword, newPassword) => {
    await api.post("/api/auth/change-password", {
      current_password: currentPassword,
      new_password: newPassword,
    });
    clearSession(); // server revoked the token; force a fresh login
  }, [clearSession]);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, changePassword }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

export { apiErrorMessage };
