"use client";

import { createContext, useContext, useState, useEffect, type ReactNode } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

interface AuthContextValue {
  username: string | null;
  canEdit: boolean;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  username: null,
  canEdit: false,
  isLoading: true,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthContextValue>({
    username: null,
    canEdit: false,
    isLoading: true,
  });

  useEffect(() => {
    async function fetchAuth() {
      try {
        const h: Record<string, string> = { "X-API-Key": API_KEY };
        const token = localStorage.getItem("auth_token");
        if (token) h["Authorization"] = `Bearer ${token}`;

        const resp = await fetch(`${API_BASE}/api/auth/me`, { headers: h });
        if (!resp.ok) {
          // JWT expired or invalid — clear stale credentials and redirect to login
          if (resp.status === 401 && token) {
            localStorage.removeItem("auth_token");
            localStorage.removeItem("auth_username");
            document.cookie = "auth_token=; path=/; max-age=0";
            window.location.href = "/login";
            return;
          }
          setState({ username: null, canEdit: false, isLoading: false });
          return;
        }
        const data = await resp.json();
        setState({
          username: data.username ?? null,
          canEdit: data.can_edit ?? false,
          isLoading: false,
        });
      } catch {
        setState({ username: null, canEdit: false, isLoading: false });
      }
    }
    fetchAuth();
  }, []);

  return (
    <AuthContext.Provider value={state}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
