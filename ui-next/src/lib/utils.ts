import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function scoreColor(score: number): string {
  if (score >= 80) return "text-emerald-600 bg-emerald-50 border-emerald-200";
  if (score >= 60) return "text-teal-600 bg-teal-50 border-teal-200";
  if (score >= 40) return "text-amber-600 bg-amber-50 border-amber-200";
  return "text-red-600 bg-red-50 border-red-200";
}

export function scoreBadgeColor(score: number): string {
  if (score >= 80) return "bg-emerald-500";
  if (score >= 60) return "bg-teal-500";
  if (score >= 40) return "bg-amber-500";
  return "bg-red-500";
}

export function decisionColor(decision: string): string {
  switch (decision) {
    case "YES": return "bg-emerald-500 text-white";
    case "MAYBE": return "bg-amber-500 text-white";
    case "MANUAL": return "bg-purple-500 text-white";
    case "NO": return "bg-red-500 text-white";
    default: return "bg-gray-400 text-white";
  }
}

export function statusColor(status: string): string {
  switch (status) {
    case "draft": return "bg-gray-400 text-white";
    case "verified": return "bg-blue-500 text-white";
    case "ready": return "bg-teal-500 text-white";
    case "queued": return "bg-amber-500 text-white";
    case "sent": case "delivered": return "bg-emerald-500 text-white";
    case "bounced": case "failed": return "bg-red-500 text-white";
    default: return "bg-gray-400 text-white";
  }
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleString("en-IN", {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

export function stripAnsi(str: string): string {
  return str.replace(/\x1B\[[0-9;]*[a-zA-Z]/g, "");
}
