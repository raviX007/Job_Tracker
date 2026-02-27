import { vi, describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import type { StartupProfile, StartupProfileStats, PaginatedResult } from "@/lib/types";

vi.mock("@/lib/api");

import {
  getStartupProfiles,
  getStartupProfileStats,
  getStartupProfileSources,
} from "@/lib/api";
import StartupsPage from "../page";

const mockGetStartupProfiles = vi.mocked(getStartupProfiles);
const mockGetStartupProfileStats = vi.mocked(getStartupProfileStats);
const mockGetStartupProfileSources = vi.mocked(getStartupProfileSources);

const fakeStats: StartupProfileStats = {
  total: 42,
  avg_score: 75,
  with_emails: 10,
  avg_completeness: 68.5,
  by_source: { "YC Directory": 25, "ProductHunt": 17 },
  by_funding: { Seed: 15, "Series A": 8 },
};

const fakeStartups: StartupProfile[] = [
  {
    id: 1,
    job_id: 100,
    startup_name: "CoolStartup",
    website_url: "https://coolstartup.com",
    yc_url: "https://yc.com/coolstartup",
    ph_url: null,
    founding_date: "2024-06-01",
    founding_date_source: "yc",
    age_months: 7,
    founder_names: ["Alice Smith"],
    founder_emails: ["alice@coolstartup.com"],
    founder_roles: ["CEO"],
    employee_count: 5,
    employee_count_source: "linkedin",
    one_liner: "AI-powered code review",
    product_description: "We help developers ship faster",
    tech_stack: ["Python", "React"],
    topics: ["AI", "DevTools"],
    has_customers: true,
    has_customers_evidence: "Website testimonials",
    funding_amount: "$2M",
    funding_round: "Seed",
    funding_date: "2024-08-01",
    funding_source: "crunchbase",
    source: "YC Directory",
    yc_batch: "W24",
    ph_launch_date: null,
    ph_votes_count: null,
    data_completeness: 85,
    created_at: "2025-01-10",
    match_score: 90,
    company: "CoolStartup",
    title: "Software Engineer",
    job_url: "https://coolstartup.com/jobs/1",
    cold_email_id: 1,
    cold_email_subject: "Interested in your AI code review tool",
    cold_email_body: "Hi Alice, I noticed your work on...",
    cold_email_status: "draft",
  },
  {
    id: 2,
    job_id: 200,
    startup_name: "DataFlow",
    website_url: null,
    yc_url: null,
    ph_url: "https://producthunt.com/posts/dataflow",
    founding_date: null,
    founding_date_source: null,
    age_months: null,
    founder_names: [],
    founder_emails: [],
    founder_roles: [],
    employee_count: null,
    employee_count_source: null,
    one_liner: "Real-time data pipelines",
    product_description: null,
    tech_stack: [],
    topics: [],
    has_customers: null,
    has_customers_evidence: null,
    funding_amount: null,
    funding_round: null,
    funding_date: null,
    funding_source: null,
    source: "ProductHunt",
    yc_batch: null,
    ph_launch_date: "2025-01-05",
    ph_votes_count: 120,
    data_completeness: 30,
    created_at: "2025-01-12",
    match_score: 55,
    company: null,
    title: null,
    job_url: null,
    cold_email_id: null,
    cold_email_subject: null,
    cold_email_body: null,
    cold_email_status: null,
  },
];

const fakeProfileResult: PaginatedResult<StartupProfile[]> = {
  data: fakeStartups,
  totalCount: 2,
};

function setupMocks() {
  mockGetStartupProfiles.mockResolvedValue(fakeProfileResult);
  mockGetStartupProfileStats.mockResolvedValue(fakeStats);
  mockGetStartupProfileSources.mockResolvedValue(["YC Directory", "ProductHunt"]);
}

function setupPendingMocks() {
  mockGetStartupProfiles.mockReturnValue(new Promise(() => {}));
  mockGetStartupProfileStats.mockReturnValue(new Promise(() => {}));
  mockGetStartupProfileSources.mockReturnValue(new Promise(() => {}));
}

describe("StartupsPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders loading skeleton initially", () => {
    setupPendingMocks();
    renderWithProviders(<StartupsPage />);
    expect(screen.getByText("Startup Scout")).toBeInTheDocument();
  });

  it("renders KPI stats cards", async () => {
    setupMocks();
    renderWithProviders(<StartupsPage />);

    await waitFor(() => {
      expect(screen.getByText("Total Startups")).toBeInTheDocument();
    });
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("Avg Completeness")).toBeInTheDocument();
    expect(screen.getByText("69%")).toBeInTheDocument(); // Math.round(68.5)
    expect(screen.getByText("Top Source Count")).toBeInTheDocument();
    expect(screen.getByText("25")).toBeInTheDocument();
    expect(screen.getByText("Funded")).toBeInTheDocument();
    expect(screen.getByText("23")).toBeInTheDocument(); // 15 + 8
  });

  it("renders startup cards with data", async () => {
    setupMocks();
    renderWithProviders(<StartupsPage />);

    await waitFor(() => {
      expect(screen.getByText("CoolStartup")).toBeInTheDocument();
    });
    expect(screen.getByText("DataFlow")).toBeInTheDocument();
    expect(screen.getByText("AI-powered code review")).toBeInTheDocument();
    expect(screen.getByText("Real-time data pipelines")).toBeInTheDocument();
  });

  it("shows filter controls", async () => {
    setupMocks();
    renderWithProviders(<StartupsPage />);

    await waitFor(() => {
      expect(screen.getByText("CoolStartup")).toBeInTheDocument();
    });

    expect(screen.getByText("Source")).toBeInTheDocument();
    expect(screen.getByText("Funding Round")).toBeInTheDocument();
    expect(screen.getByText("Min Age (mo)")).toBeInTheDocument();
    expect(screen.getByText("Max Age (mo)")).toBeInTheDocument();
    expect(screen.getByText("Search")).toBeInTheDocument();
    expect(screen.getByText("Sort By")).toBeInTheDocument();
  });

  it("shows empty state when no startups", async () => {
    mockGetStartupProfiles.mockResolvedValue({ data: [], totalCount: 0 });
    mockGetStartupProfileStats.mockResolvedValue(fakeStats);
    mockGetStartupProfileSources.mockResolvedValue([]);

    renderWithProviders(<StartupsPage />);

    await waitFor(() => {
      expect(screen.getByText("No startup profiles found")).toBeInTheDocument();
    });
  });

  it("shows error state with retry button", async () => {
    mockGetStartupProfiles.mockRejectedValue(new Error("Startup fetch failed"));
    mockGetStartupProfileStats.mockRejectedValue(new Error("Startup fetch failed"));
    mockGetStartupProfileSources.mockRejectedValue(new Error("Startup fetch failed"));

    renderWithProviders(<StartupsPage />);

    await waitFor(() => {
      expect(screen.getByText("Startup fetch failed")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
