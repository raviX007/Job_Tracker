import type {
  OverviewStats,
  Application,
  ApplicationFilters,
  EmailQueueItem,
  EmailStatusCounts,
  DailyTrend,
  ScoreDistribution,
  SourceBreakdown,
  CompanyType,
  ResponseRate,
  RouteBreakdown,
  TrackerRow,
  ApplicationForUpdate,
  AnalyzedJobForUpdate,
  StartupProfile,
  StartupProfileStats,
  StartupProfileFilters,
  PipelineRunResponse,
  PipelineStatusResponse,
  PaginatedResult,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";
const REQUEST_TIMEOUT_MS = 60_000;

function headers(): HeadersInit {
  const h: Record<string, string> = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
  };

  if (typeof window !== "undefined") {
    const token = localStorage.getItem("auth_token");
    if (token) {
      h["Authorization"] = `Bearer ${token}`;
    }
  }

  return h;
}

async function request<T>(
  method: string,
  path: string,
  options?: { params?: Record<string, string | number>; body?: unknown; signal?: AbortSignal },
): Promise<T> {
  let url = `${API_BASE}${path}`;

  if (options?.params) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(options.params)) {
      searchParams.set(key, String(value));
    }
    url += `?${searchParams.toString()}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  // Link external signal (e.g. from React Query) to internal controller
  const onExternalAbort = () => controller.abort();
  options?.signal?.addEventListener("abort", onExternalAbort);

  try {
    const response = await fetch(url, {
      method,
      headers: headers(),
      body: options?.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    });

    if (!response.ok) {
      if (response.status === 401 && typeof window !== "undefined") {
        localStorage.removeItem("auth_token");
        localStorage.removeItem("auth_username");
        document.cookie = "auth_token=; path=/; max-age=0";
        window.location.href = "/login";
        throw new Error("Session expired");
      }
      const error = await response.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(error.detail || `API error: ${response.status}`);
    }

    return response.json();
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      if (options?.signal?.aborted) throw err; // External cancellation — let React Query handle silently
      throw new Error("Request timed out");
    }
    if (err instanceof TypeError) {
      throw new Error("Cannot reach the API server — is the backend running?");
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
    options?.signal?.removeEventListener("abort", onExternalAbort);
  }
}

function get<T>(path: string, params?: Record<string, string | number>, signal?: AbortSignal): Promise<T> {
  return request<T>("GET", path, { params, signal });
}

async function getWithCount<T>(
  path: string,
  params?: Record<string, string | number>,
  signal?: AbortSignal,
): Promise<PaginatedResult<T>> {
  let url = `${API_BASE}${path}`;

  if (params) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      searchParams.set(key, String(value));
    }
    url += `?${searchParams.toString()}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  const onExternalAbort = () => controller.abort();
  signal?.addEventListener("abort", onExternalAbort);

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: headers(),
      signal: controller.signal,
    });

    if (!response.ok) {
      if (response.status === 401 && typeof window !== "undefined") {
        localStorage.removeItem("auth_token");
        localStorage.removeItem("auth_username");
        document.cookie = "auth_token=; path=/; max-age=0";
        window.location.href = "/login";
        throw new Error("Session expired");
      }
      const error = await response.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(error.detail || `API error: ${response.status}`);
    }

    const totalCount = parseInt(response.headers.get("X-Total-Count") || "0", 10);
    const data = await response.json();
    return { data, totalCount };
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      if (signal?.aborted) throw err;
      throw new Error("Request timed out");
    }
    if (err instanceof TypeError) {
      throw new Error("Cannot reach the API server — is the backend running?");
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
    signal?.removeEventListener("abort", onExternalAbort);
  }
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>("POST", path, { body });
}

function put<T>(path: string, body?: unknown): Promise<T> {
  return request<T>("PUT", path, { body });
}

function del<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  return request<T>("DELETE", path, { params });
}

// ─── Overview ────────────────────────────────────────

export function getOverviewStats(profileId: number, signal?: AbortSignal): Promise<OverviewStats> {
  return get("/api/overview/stats", { profile_id: profileId }, signal);
}

// ─── Applications ────────────────────────────────────

export function getApplications(
  profileId: number,
  filters: Partial<ApplicationFilters> = {},
  signal?: AbortSignal,
): Promise<PaginatedResult<Application[]>> {
  return getWithCount("/api/applications", {
    profile_id: profileId,
    min_score: filters.min_score ?? 0,
    max_score: filters.max_score ?? 100,
    decision: filters.decision ?? "All",
    source: filters.source ?? "All",
    search: filters.search ?? "",
    limit: filters.limit ?? 50,
    offset: filters.offset ?? 0,
  }, signal);
}

export function getSources(profileId: number, signal?: AbortSignal): Promise<string[]> {
  return get("/api/applications/sources", { profile_id: profileId }, signal);
}

// ─── Email Queue ─────────────────────────────────────

export function getEmailQueue(
  profileId: number,
  status: string = "All",
  source: string = "All",
  limit: number = 50,
  offset: number = 0,
  signal?: AbortSignal,
): Promise<PaginatedResult<EmailQueueItem[]>> {
  return getWithCount("/api/emails/queue", { profile_id: profileId, status, source, limit, offset }, signal);
}

export function getEmailById(emailId: number, signal?: AbortSignal): Promise<EmailQueueItem> {
  return get(`/api/emails/${emailId}`, undefined, signal);
}

export function getEmailStatuses(profileId: number, signal?: AbortSignal): Promise<EmailStatusCounts> {
  return get("/api/emails/statuses", { profile_id: profileId }, signal);
}

export function getEmailSources(profileId: number, signal?: AbortSignal): Promise<string[]> {
  return get("/api/emails/sources", { profile_id: profileId }, signal);
}

export function updateEmailContent(
  emailId: number,
  subject: string,
  bodyPlain: string,
): Promise<{ status: string }> {
  return put(`/api/emails/${emailId}/content`, { subject, body_plain: bodyPlain });
}

export function deleteEmail(emailId: number): Promise<{ status: string }> {
  return del(`/api/emails/${emailId}`);
}

export function deleteAllEmails(profileId: number): Promise<{ deleted: number }> {
  return del("/api/emails", { profile_id: profileId });
}

export function sendEmail(emailId: number): Promise<{ status: string; email_id: number; to: string }> {
  return post(`/api/emails/${emailId}/send`);
}

// ─── Update Outcomes ─────────────────────────────────

export function getApplicationsForUpdate(profileId: number, signal?: AbortSignal): Promise<ApplicationForUpdate[]> {
  return get("/api/applications/for-update", { profile_id: profileId }, signal);
}

export function getAnalyzedJobsForUpdate(profileId: number, signal?: AbortSignal): Promise<AnalyzedJobForUpdate[]> {
  return get("/api/applications/analyzed-for-update", { profile_id: profileId }, signal);
}

export function updateApplicationOutcome(
  appId: number,
  data: { response_type: string; response_date: string | null; notes: string },
): Promise<{ status: string }> {
  return put(`/api/applications/${appId}/outcome`, data);
}

export function createApplication(data: {
  job_id: number;
  profile_id: number;
  method: string;
  platform: string;
}): Promise<{ status: string }> {
  return post("/api/applications", data);
}

// ─── Analytics ───────────────────────────────────────

export function getDailyTrends(profileId: number, days: number = 30, signal?: AbortSignal): Promise<DailyTrend[]> {
  return get("/api/analytics/daily-trends", { profile_id: profileId, days }, signal);
}

export function getScoreDistribution(profileId: number, signal?: AbortSignal): Promise<ScoreDistribution[]> {
  return get("/api/analytics/score-distribution", { profile_id: profileId }, signal);
}

export function getSourceBreakdown(profileId: number, signal?: AbortSignal): Promise<SourceBreakdown[]> {
  return get("/api/analytics/source-breakdown", { profile_id: profileId }, signal);
}

export function getCompanyTypes(profileId: number, signal?: AbortSignal): Promise<CompanyType[]> {
  return get("/api/analytics/company-types", { profile_id: profileId }, signal);
}

export function getResponseRates(profileId: number, signal?: AbortSignal): Promise<ResponseRate[]> {
  return get("/api/analytics/response-rates", { profile_id: profileId }, signal);
}

export function getRouteBreakdown(profileId: number, signal?: AbortSignal): Promise<RouteBreakdown> {
  return get("/api/analytics/route-breakdown", { profile_id: profileId }, signal);
}

// ─── Tracker ─────────────────────────────────────────

export function getTrackerData(
  profileId: number,
  limit: number = 50,
  offset: number = 0,
  signal?: AbortSignal,
): Promise<PaginatedResult<TrackerRow[]>> {
  return getWithCount("/api/tracker", { profile_id: profileId, limit, offset }, signal);
}

export function upsertApplication(data: {
  job_id: number;
  profile_id: number;
  method: string;
  platform: string;
  response_type: string | null;
  notes: string | null;
  app_id: number | null;
}): Promise<{ status: string }> {
  return post("/api/applications/upsert", data);
}

// ─── Jobs ────────────────────────────────────────────

export function markJobObsolete(jobId: number): Promise<{ status: string; is_obsolete: boolean }> {
  return put(`/api/jobs/${jobId}/obsolete`);
}

export function checkJobLink(jobId: number, signal?: AbortSignal): Promise<{ job_id: number; url: string; is_live: boolean }> {
  return get(`/api/jobs/${jobId}/check-link`, undefined, signal);
}

// ─── Startup Profiles ────────────────────────────────

export function getStartupProfiles(
  profileId: number,
  filters: Partial<StartupProfileFilters> = {},
  signal?: AbortSignal,
): Promise<PaginatedResult<StartupProfile[]>> {
  return getWithCount("/api/startup-profiles", {
    profile_id: profileId,
    source: filters.source ?? "All",
    funding_round: filters.funding_round ?? "All",
    min_age: filters.min_age ?? 0,
    max_age: filters.max_age ?? 24,
    has_funding: filters.has_funding ?? "All",
    search: filters.search ?? "",
    sort_by: filters.sort_by ?? "match_score",
    limit: filters.limit ?? 50,
    offset: filters.offset ?? 0,
  }, signal);
}

export function getStartupProfileStats(profileId: number, signal?: AbortSignal): Promise<StartupProfileStats> {
  return get("/api/startup-profiles/stats", { profile_id: profileId }, signal);
}

export function getStartupProfileSources(profileId: number, signal?: AbortSignal): Promise<string[]> {
  return get("/api/startup-profiles/sources", { profile_id: profileId }, signal);
}

// ─── Pipeline ────────────────────────────────────────

export function runMainPipeline(source: string, limit: number): Promise<PipelineRunResponse> {
  return post("/api/pipeline/main/run", { source, limit });
}

export function runStartupScout(source: string, limit: number): Promise<PipelineRunResponse> {
  return post("/api/pipeline/startup-scout/run", { source, limit });
}

export function getPipelineRunStatus(runId: string): Promise<PipelineStatusResponse> {
  return get(`/api/pipeline/runs/${runId}`);
}

export function getRecentPipelineRuns(
  pipeline?: string,
  limit: number = 20,
  signal?: AbortSignal,
): Promise<PipelineStatusResponse[]> {
  const params: Record<string, string | number> = { limit };
  if (pipeline) params.pipeline = pipeline;
  return get("/api/pipeline/runs", params, signal);
}

// ─── Profiles ───────────────────────────────────────

export function getMyProfile(signal?: AbortSignal): Promise<{ profile: any }> {
  return get("/api/profiles/me", undefined, signal);
}

export function saveMyProfile(config: Record<string, any>): Promise<{ status: string; profile_id: number }> {
  return put("/api/profiles/me", { config });
}

export async function uploadResume(file: File): Promise<{ extracted: any; resume_text_length: number; auto_saved: boolean }> {
  const formData = new FormData();
  formData.append("file", file);

  const h: Record<string, string> = { "X-API-Key": API_KEY };
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("auth_token");
    if (token) h["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}/api/profiles/me/resume`, {
    method: "POST",
    headers: h,
    body: formData,
  });

  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("auth_token");
      localStorage.removeItem("auth_username");
      document.cookie = "auth_token=; path=/; max-age=0";
      window.location.href = "/login";
      throw new Error("Session expired");
    }
    const error = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `Upload failed: ${response.status}`);
  }

  return response.json();
}
