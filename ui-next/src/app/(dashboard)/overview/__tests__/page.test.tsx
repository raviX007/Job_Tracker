import { vi, describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/test-utils";
import type { OverviewStats, Application, DailyTrend, PaginatedResult } from "@/lib/types";

// Mock the entire API module
vi.mock("@/lib/api");

import { getOverviewStats, getDailyTrends, getApplications } from "@/lib/api";
import OverviewPage from "../page";

const mockGetOverviewStats = vi.mocked(getOverviewStats);
const mockGetDailyTrends = vi.mocked(getDailyTrends);
const mockGetApplications = vi.mocked(getApplications);

const fakeStats: OverviewStats = {
  today_jobs: 42,
  today_analyzed: 30,
  today_emails: 8,
  today_applied: 5,
  total_jobs: 1200,
  total_analyzed: 900,
  total_yes: 150,
  total_emails: 80,
  jobs_with_emails: 60,
  avg_score: 72.5,
  week_jobs: 95,
};

const fakeTrends: DailyTrend[] = [
  { date: "2025-01-01", jobs_scraped: 10, jobs_analyzed: 8, emails_queued: 3 },
  { date: "2025-01-02", jobs_scraped: 15, jobs_analyzed: 12, emails_queued: 5 },
];

const fakeTopMatches: PaginatedResult<Application[]> = {
  data: [
    {
      job_id: 1,
      title: "Senior Engineer",
      company: "Acme Corp",
      location: "Remote",
      source: "LinkedIn",
      is_remote: true,
      job_url: "https://example.com/job/1",
      date_posted: "2025-01-01",
      date_scraped: "2025-01-01",
      match_score: 85,
      embedding_score: null,
      apply_decision: "YES",
      skills_matched: ["React", "TypeScript"],
      skills_missing: [],
      ats_keywords: [],
      gap_tolerant: null,
      company_type: "Startup",
      route_action: "apply",
      cold_email_angle: null,
      cover_letter: null,
      experience_required: null,
      red_flags: [],
    },
    {
      job_id: 2,
      title: "Full Stack Developer",
      company: "Widget Inc",
      location: "NYC",
      source: "Indeed",
      is_remote: false,
      job_url: "https://example.com/job/2",
      date_posted: "2025-01-02",
      date_scraped: "2025-01-02",
      match_score: 78,
      embedding_score: null,
      apply_decision: "YES",
      skills_matched: ["Node.js"],
      skills_missing: ["Go"],
      ats_keywords: [],
      gap_tolerant: null,
      company_type: null,
      route_action: "email",
      cold_email_angle: null,
      cover_letter: null,
      experience_required: null,
      red_flags: [],
    },
  ],
  totalCount: 2,
};

function setupMocks() {
  mockGetOverviewStats.mockResolvedValue(fakeStats);
  mockGetDailyTrends.mockResolvedValue(fakeTrends);
  mockGetApplications.mockResolvedValue(fakeTopMatches);
}

describe("OverviewPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders loading skeleton initially", () => {
    // Never-resolving promises to keep loading state
    mockGetOverviewStats.mockReturnValue(new Promise(() => {}));
    mockGetDailyTrends.mockReturnValue(new Promise(() => {}));
    mockGetApplications.mockReturnValue(new Promise(() => {}));

    renderWithProviders(<OverviewPage />);
    expect(screen.getByText("Overview")).toBeInTheDocument();
  });

  it("renders KPI cards with correct values", async () => {
    setupMocks();
    renderWithProviders(<OverviewPage />);

    await waitFor(() => {
      expect(screen.getByText("42")).toBeInTheDocument();
    });
    expect(screen.getByText("30")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("renders all-time summary cards", async () => {
    setupMocks();
    renderWithProviders(<OverviewPage />);

    await waitFor(() => {
      expect(screen.getByText("Total Jobs")).toBeInTheDocument();
    });
    expect(screen.getByText("1,200")).toBeInTheDocument();
    expect(screen.getByText("900")).toBeInTheDocument();
    expect(screen.getByText("73")).toBeInTheDocument(); // Math.round(72.5)
    expect(screen.getByText("150")).toBeInTheDocument();
    expect(screen.getByText("95")).toBeInTheDocument();
  });

  it("shows empty state for trends", async () => {
    mockGetOverviewStats.mockResolvedValue(fakeStats);
    mockGetDailyTrends.mockResolvedValue([]);
    mockGetApplications.mockResolvedValue(fakeTopMatches);

    renderWithProviders(<OverviewPage />);

    await waitFor(() => {
      expect(screen.getByText("No trend data available yet.")).toBeInTheDocument();
    });
  });

  it("shows error state with retry button", async () => {
    mockGetOverviewStats.mockRejectedValue(new Error("Network error"));
    mockGetDailyTrends.mockRejectedValue(new Error("Network error"));
    mockGetApplications.mockRejectedValue(new Error("Network error"));

    renderWithProviders(<OverviewPage />);

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("retry button refetches data", async () => {
    mockGetOverviewStats.mockRejectedValueOnce(new Error("fail"));
    mockGetDailyTrends.mockRejectedValueOnce(new Error("fail"));
    mockGetApplications.mockRejectedValueOnce(new Error("fail"));

    renderWithProviders(<OverviewPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    });

    // Set up successful response for retry
    mockGetOverviewStats.mockResolvedValue(fakeStats);
    mockGetDailyTrends.mockResolvedValue(fakeTrends);
    mockGetApplications.mockResolvedValue(fakeTopMatches);

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => {
      expect(screen.getByText("42")).toBeInTheDocument();
    });
  });

  it("shows top matches with company names", async () => {
    setupMocks();
    renderWithProviders(<OverviewPage />);

    await waitFor(() => {
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    });
    expect(screen.getByText("Widget Inc")).toBeInTheDocument();
    expect(screen.getByText("Senior Engineer")).toBeInTheDocument();
    expect(screen.getByText("Full Stack Developer")).toBeInTheDocument();
  });
});
