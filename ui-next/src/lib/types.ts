// ─── Pagination ──────────────────────────────────────

export interface PaginatedResult<T> {
  data: T;
  totalCount: number;
}

// ─── Overview ────────────────────────────────────────

export interface OverviewStats {
  today_jobs: number;
  today_analyzed: number;
  today_emails: number;
  today_applied: number;
  total_jobs: number;
  total_analyzed: number;
  total_yes: number;
  total_emails: number;
  jobs_with_emails: number;
  avg_score: number;
  week_jobs: number;
}

// ─── Applications ────────────────────────────────────

export interface Application {
  job_id: number;
  title: string;
  company: string;
  location: string | null;
  source: string;
  is_remote: boolean;
  job_url: string;
  date_posted: string | null;
  date_scraped: string | null;
  match_score: number;
  embedding_score: number | null;
  apply_decision: string;
  skills_matched: string[];
  skills_missing: string[];
  ats_keywords: string[];
  gap_tolerant: boolean | null;
  company_type: string | null;
  route_action: string | null;
  cold_email_angle: string | null;
  cover_letter: string | null;
  experience_required: string | null;
  red_flags: string[];
}

export interface ApplicationFilters {
  min_score: number;
  max_score: number;
  decision: string;
  source: string;
  search: string;
  limit: number;
  offset: number;
}

// ─── Email Queue ─────────────────────────────────────

export interface EmailQueueItem {
  id: number;
  recipient_email: string;
  recipient_name: string;
  recipient_role: string;
  recipient_source: string;
  subject: string;
  body_plain: string;
  email_verified: boolean;
  email_verification_result: string | null;
  status: string;
  sent_at: string | null;
  created_at: string;
  job_title: string;
  job_company: string;
  job_url: string;
  job_source: string;
  match_score: number;
  route_action: string | null;
}

export interface EmailStatusCounts {
  [status: string]: number;
}

// ─── Analytics ───────────────────────────────────────

export interface DailyTrend {
  date: string;
  jobs_scraped: number;
  jobs_analyzed: number;
  emails_queued: number;
}

export interface ScoreDistribution {
  bracket: string;
  count: number;
}

export interface SourceBreakdown {
  source: string;
  count: number;
  avg_score: number;
  yes_count: number;
}

export interface CompanyType {
  company_type: string;
  count: number;
  avg_score: number;
  gap_tolerant_count: number;
}

export interface ResponseRate {
  method: string;
  total: number;
  responded: number;
  interviews: number;
  offers: number;
  rejections: number;
}

export interface RouteBreakdown {
  [route: string]: number;
}

// ─── Tracker ─────────────────────────────────────────

export interface TrackerRow {
  job_id: number;
  app_id: number | null;
  company: string;
  title: string;
  source: string;
  job_url: string;
  match_score: number;
  apply_decision: string;
  route_action: string | null;
  skills_matched: string[];
  skills_missing: string[];
  embedding_score: number | null;
  is_remote: boolean;
  location: string | null;
  is_obsolete: boolean;
  app_method: string | null;
  app_platform: string | null;
  applied_at: string | null;
  response_type: string | null;
  app_notes: string | null;
}

// ─── Update Outcomes ─────────────────────────────────

export interface ApplicationForUpdate {
  app_id: number;
  job_id: number;
  company: string;
  title: string;
  method: string;
  platform: string;
  applied_at: string;
  response_type: string | null;
  response_date: string | null;
  notes: string;
  match_score: number;
}

export interface AnalyzedJobForUpdate {
  job_id: number;
  company: string;
  title: string;
  location: string | null;
  job_url: string | null;
  match_score: number;
  apply_decision: string;
  route_action: string | null;
}

// ─── Startup Profiles ────────────────────────────────

export interface StartupProfile {
  id: number;
  job_id: number;
  startup_name: string;
  website_url: string | null;
  yc_url: string | null;
  ph_url: string | null;
  founding_date: string | null;
  founding_date_source: string | null;
  age_months: number | null;
  founder_names: string[];
  founder_emails: string[];
  founder_roles: string[];
  employee_count: number | null;
  employee_count_source: string | null;
  one_liner: string | null;
  product_description: string | null;
  tech_stack: string[];
  topics: string[];
  has_customers: boolean | null;
  has_customers_evidence: string | null;
  funding_amount: string | null;
  funding_round: string | null;
  funding_date: string | null;
  funding_source: string | null;
  source: string;
  yc_batch: string | null;
  ph_launch_date: string | null;
  ph_votes_count: number | null;
  data_completeness: number | null;
  created_at: string;
  match_score: number | null;
  company: string | null;
  title: string | null;
  job_url: string | null;
  cold_email_id: number | null;
  cold_email_subject: string | null;
  cold_email_body: string | null;
  cold_email_status: string | null;
}

export interface StartupProfileStats {
  total: number;
  avg_score: number;
  with_emails: number;
  avg_completeness: number;
  by_source: Record<string, number>;
  by_funding: Record<string, number>;
}

export interface StartupProfileFilters {
  source: string;
  funding_round: string;
  min_age: number;
  max_age: number;
  has_funding: string;
  search: string;
  sort_by: string;
  limit: number;
  offset: number;
}

// ─── Pipeline ────────────────────────────────────────

export interface PipelineRunResponse {
  run_id: string;
  pipeline: string;
  source: string;
  limit: number;
  status: string;
}

export interface PipelineStatusResponse {
  run_id: string;
  pipeline: string;
  source: string;
  job_limit: number;
  status: string;
  pid: number | null;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  return_code: number | null;
  output: string;
  error: string | null;
  created_at: string;
}
