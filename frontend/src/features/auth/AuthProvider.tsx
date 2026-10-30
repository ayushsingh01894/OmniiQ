import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import * as api from "../../lib/api";
import { clearToken, getToken, storeToken } from "../../lib/session";

type Status = "loading" | "anonymous" | "authenticated" | "error";

type AuthValue = {
  status: Status;
  user: api.User | null;
  login: (email: string, password: string) => Promise<void>;
  register: (input: { email: string; password: string; display_name: string }) => Promise<void>;
  logout: () => void;
  retry: () => void;
};

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [token, setToken] = useState<string | null>(getToken);

  const logout = useCallback(() => {
    clearToken();
    setToken(null);
    queryClient.clear(); // never keep one user's data around for the next sign-in
  }, [queryClient]);

  useEffect(() => {
    api.setUnauthorizedHandler(logout);
    return () => api.setUnauthorizedHandler(null);
  }, [logout]);

  const me = useQuery({
    queryKey: ["me", token],
    queryFn: api.getMe,
    enabled: token !== null,
    retry: false,
  });

  const login = useCallback(async (email: string, password: string) => {
    const result = await api.login({ email, password });
    storeToken(result.access_token);
    setToken(result.access_token);
  }, []);

  const register = useCallback(
    async (input: { email: string; password: string; display_name: string }) => {
      await api.register(input);
      await login(input.email, input.password);
    },
    [login],
  );

  const status: Status =
    token === null ? "anonymous" : me.isPending ? "loading" : me.isError ? "error" : "authenticated";

  const value = useMemo<AuthValue>(
    () => ({
      status,
      user: status === "authenticated" ? (me.data ?? null) : null,
      login,
      register,
      logout,
      retry: () => void me.refetch(),
    }),
    [status, me, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
