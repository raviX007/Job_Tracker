export const DECISIONS = ["All", "YES", "MAYBE", "MANUAL", "NO"] as const;

export const EMAIL_STATUSES = [
  "All", "draft", "verified", "ready", "queued", "sent", "delivered", "bounced", "failed",
] as const;

export const RESPONSE_TYPES = [
  "interview", "rejection", "offer", "ghosted", "followup_needed", "assignment",
] as const;

export const APPLICATION_METHODS = [
  "auto_apply", "cold_email", "manual_apply", "telegram_alert",
] as const;

export const CHART_COLORS = [
  "#00d4aa", "#1e3a5f", "#f5a623", "#e74c3c", "#8e44ad", "#3498db",
] as const;

export const PIPELINE_SOURCES: Record<string, string | null> = {
  "All Scrapers": "all",
  "Remote Boards": "remote_boards",
  "Aggregators": "aggregators",
  "API Boards": "api_boards",
  "ATS Direct": "ats_direct",
  "Remotive": "remotive",
  "Jobicy": "jobicy",
  "Himalayas": "himalayas",
  "Arbeitnow": "arbeitnow",
  "Jooble": "jooble",
  "Adzuna": "adzuna",
  "RemoteOK": "remoteok",
  "HiringCafe": "hiringcafe",
  "JSearch": "jsearch",
  "CareerJet": "careerjet",
  "TheMuse": "themuse",
  "FindWork": "findwork",
  "Greenhouse": "greenhouse",
  "Lever": "lever",
};

export const STARTUP_SOURCES: Record<string, string> = {
  "All Startup Sources": "startup_scout",
  "HN Who's Hiring": "hn_hiring",
  "YC Directory": "yc_directory",
  "ProductHunt": "producthunt",
};
