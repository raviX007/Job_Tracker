import { vi, describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/test-utils";
import type { Application, PaginatedResult } from "@/lib/types";

vi.mock("@/lib/api");
vi.mock("@/lib/export", () => ({
  exportToExcel: vi.fn(),
}));

import { getApplications, getSources } from "@/lib/api";
import ApplicationsPage from "../page";

const mockGetApplications = vi.mocked(getApplications);
const mockGetSources = vi.mocked(getSources);

const fakeApps: Application[] = [
  {
    job_id: 1,
    title: "Backend Engineer",
    company: "TechCo",
    location: "San Francisco",
    source: "LinkedIn",
    is_remote: false,
    job_url: "https://example.com/job/1",
    date_posted: "2025-01-15",
    date_scraped: "2025-01-15",
    match_score: 88,
    embedding_score: null,
    apply_decision: "YES",
    skills_matched: ["Python", "FastAPI", "PostgreSQL"],
    skills_missing: ["Kubernetes"],
    ats_keywords: ["distributed systems"],
    gap_tolerant: true,
    company_type: "Series B",
    route_action: "apply",
    cold_email_angle: "Strong Python background",
    cover_letter: "Dear hiring manager...",
    experience_required: "3-5 years",
    red_flags: [],
  },
  {
    job_id: 2,
    title: "Frontend Developer",
    company: "DesignHub",
    location: null,
    source: "Indeed",
    is_remote: true,
    job_url: "https://example.com/job/2",
    date_posted: null,
    date_scraped: "2025-01-16",
    match_score: 62,
    embedding_score: null,
    apply_decision: "MAYBE",
    skills_matched: ["React"],
    skills_missing: ["Vue", "Angular"],
    ats_keywords: [],
    gap_tolerant: null,
    company_type: null,
    route_action: "email",
    cold_email_angle: null,
    cover_letter: null,
    experience_required: null,
    red_flags: [],
  },
];

const fakeResult: PaginatedResult<Application[]> = {
  data: fakeApps,
  totalCount: 2,
};

function setupMocks() {
  mockGetApplications.mockResolvedValue(fakeResult);
  mockGetSources.mockResolvedValue(["LinkedIn", "Indeed"]);
}

describe("ApplicationsPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders loading skeleton initially", () => {
    mockGetApplications.mockReturnValue(new Promise(() => {}));
    mockGetSources.mockResolvedValue([]);

    renderWithProviders(<ApplicationsPage />);
    expect(screen.getByText("Applications")).toBeInTheDocument();
  });

  it("renders application cards with data", async () => {
    setupMocks();
    renderWithProviders(<ApplicationsPage />);

    await waitFor(() => {
      expect(screen.getByText("TechCo")).toBeInTheDocument();
    });
    expect(screen.getByText("DesignHub")).toBeInTheDocument();
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText("Frontend Developer")).toBeInTheDocument();
  });

  it('shows "X applications found" count', async () => {
    setupMocks();
    renderWithProviders(<ApplicationsPage />);

    await waitFor(() => {
      expect(screen.getByText("2 applications found")).toBeInTheDocument();
    });
  });

  it("shows empty state when no applications", async () => {
    mockGetApplications.mockResolvedValue({ data: [], totalCount: 0 });
    mockGetSources.mockResolvedValue([]);

    renderWithProviders(<ApplicationsPage />);

    await waitFor(() => {
      expect(screen.getByText("No applications found.")).toBeInTheDocument();
    });
  });

  it("shows error state with retry button", async () => {
    mockGetApplications.mockRejectedValue(new Error("Server error"));
    mockGetSources.mockResolvedValue([]);

    renderWithProviders(<ApplicationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Server error")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("shows filter controls", async () => {
    setupMocks();
    renderWithProviders(<ApplicationsPage />);

    await waitFor(() => {
      expect(screen.getByText("TechCo")).toBeInTheDocument();
    });

    expect(screen.getByText("Min Score")).toBeInTheDocument();
    expect(screen.getByText("Max Score")).toBeInTheDocument();
    expect(screen.getByText("Decision")).toBeInTheDocument();
    expect(screen.getByText("Source")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Search company, title, skills...")).toBeInTheDocument();
  });

  it("expands and collapses details", async () => {
    setupMocks();
    const user = userEvent.setup();
    renderWithProviders(<ApplicationsPage />);

    await waitFor(() => {
      expect(screen.getByText("TechCo")).toBeInTheDocument();
    });

    // Find the first "Details" button and click
    const detailsButtons = screen.getAllByText("Details");
    await user.click(detailsButtons[0]);

    // Expanded content should be visible
    expect(screen.getByText("ATS Keywords")).toBeInTheDocument();
    expect(screen.getByText("distributed systems")).toBeInTheDocument();

    // Click "Hide Details" to collapse
    await user.click(screen.getByText("Hide Details"));
    expect(screen.queryByText("ATS Keywords")).not.toBeInTheDocument();
  });

  it("renders table view", async () => {
    setupMocks();
    const user = userEvent.setup();
    renderWithProviders(<ApplicationsPage />);

    await waitFor(() => {
      expect(screen.getByText("TechCo")).toBeInTheDocument();
    });

    // Switch to table view
    await user.click(screen.getByRole("tab", { name: "Table" }));

    // Table headers should be visible (use columnheader role to avoid matching filter labels)
    const headers = screen.getAllByRole("columnheader");
    const headerTexts = headers.map((h) => h.textContent);
    expect(headerTexts).toContain("Score");
    expect(headerTexts).toContain("Decision");
    expect(headerTexts).toContain("Company");
    expect(headerTexts).toContain("Title");
  });
});
