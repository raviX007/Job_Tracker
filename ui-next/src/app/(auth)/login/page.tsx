"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Briefcase } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<"login" | "register">("login");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const endpoint =
        mode === "login" ? "/api/auth/login" : "/api/auth/register";
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      if (!res.ok) {
        const data = await res
          .json()
          .catch(() => ({ detail: "Request failed" }));
        throw new Error(data.detail || `Error: ${res.status}`);
      }

      const { token, username: user } = await res.json();

      // Store JWT in cookie (for middleware) and localStorage (for API calls)
      document.cookie = `auth_token=${token}; path=/; max-age=${60 * 60 * 24}; SameSite=Lax`;
      localStorage.setItem("auth_token", token);
      localStorage.setItem("auth_username", user);

      // Fetch profile to sync profile_id in localStorage
      try {
        const profileRes = await fetch(`${API_BASE}/api/profiles/me`, {
          headers: { "X-API-Key": API_KEY, Authorization: `Bearer ${token}` },
        });
        if (profileRes.ok) {
          const profileData = await profileRes.json();
          if (profileData.profile?.id) {
            localStorage.setItem("job-tracker-profile-id", String(profileData.profile.id));
          }
        }
      } catch {
        // Non-critical — profile_id will sync when user visits Settings
      }

      router.push("/overview");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[#0f1b2d] to-[#1e3a5f] px-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-accent/20">
            <Briefcase className="h-6 w-6 text-accent" />
          </div>
          <CardTitle className="text-2xl">Job Tracker</CardTitle>
          <CardDescription>
            {mode === "login"
              ? "Sign in to your account"
              : "Create a new account"}
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {error}
              </div>
            )}
            <div className="space-y-2">
              <label
                htmlFor="username"
                className="text-sm font-medium text-gray-700"
              >
                Username
              </label>
              <Input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your username"
                required
                minLength={mode === "register" ? 3 : 1}
                autoComplete="username"
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <label
                htmlFor="password"
                className="text-sm font-medium text-gray-700"
              >
                Password
              </label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                required
                minLength={mode === "register" ? 8 : 1}
                autoComplete={
                  mode === "login" ? "current-password" : "new-password"
                }
              />
            </div>
          </CardContent>
          <CardFooter className="flex flex-col gap-3">
            <Button
              type="submit"
              variant="accent"
              className="w-full"
              disabled={loading}
            >
              {loading
                ? mode === "login"
                  ? "Signing in..."
                  : "Creating account..."
                : mode === "login"
                  ? "Sign In"
                  : "Create Account"}
            </Button>
            <button
              type="button"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError("");
              }}
              className="text-sm text-muted-foreground transition-colors hover:text-primary"
            >
              {mode === "login"
                ? "Don't have an account? Register"
                : "Already have an account? Sign in"}
            </button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
