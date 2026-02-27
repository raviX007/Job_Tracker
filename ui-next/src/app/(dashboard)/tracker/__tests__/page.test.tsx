import { vi, describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import type { TrackerRow, PaginatedResult } from "@/lib/types";

vi.mock("@/lib/api");
vi.mock("@/lib/export", () => ({
  exportToExcel: vi.fn(),
}));

import { getTrackerData } from "@/lib/api";
import TrackerPage from "../page";

const mockGetTrackerData = vi.mocked(getTrackerData);

const fakeRows: TrackerRow[] = [
  {
    job_id: 1,
    app_id: 10,
    company: "TechCo",
    title: "Backend Engineer",
    source: "LinkedIn",
    job_url: "https://example.com/job/1",
    match_score: 88,
    apply_decision: "YES",
    route_action: "apply",
    skills_matched: ["Python"],
    skills_missing: ["Go"],
    embedding_score: null,
    is_remote: true,
    location: "San Francisco",
    is_obsolete: false,
    app_method: "manual_apply",
    app_platform: "LinkedIn",
    applied_at: "2025-01-15",
    response_type: "interview",
    app_notes: "Phone screen scheduled",
  },
  {
    job_id: 2,
    app_id: null,
    company: "StartupX",
    title: "Full Stack Dev",
    source: "Indeed",
    job_url: "https://example.com/job/2",
    match_score: 65,
    apply_decision: "MAYBE",
    route_action: "email",
    skills_matched: ["React"],
    skills_missing: ["Vue"],
    embedding_score: null,
    is_remote: false,
    location: null,
    is_obsolete: false,
    app_method: null,
    app_platform: null,
    applied_at: null,
    response_type: null,
    app_notes: null,
  },
];

const fakeResult: PaginatedResult<TrackerRow[]> = {
  data: fakeRows,
  totalCount: 2,
};

describe("TrackerPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders loading skeleton initially", () => {
    mockGetTrackerData.mockReturnValue(new Promise(() => {}));
    renderWithProviders(<TrackerPage />);
    expect(screen.getByText("Application Tracker")).toBeInTheDocument();
  });

  it("renders tracker table with data", async () => {
    mockGetTrackerData.mockResolvedValue(fakeResult);
    renderWithProviders(<TrackerPage />);

    await waitFor(() => {
      expect(screen.getByText("TechCo")).toBeInTheDocument();
    });
    expect(screen.getByText("StartupX")).toBeInTheDocument();
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText("Full Stack Dev")).toBeInTheDocument();
  });

  it("shows empty state when no data", async () => {
    mockGetTrackerData.mockResolvedValue({ data: [], totalCount: 0 });
    renderWithProviders(<TrackerPage />);

    await waitFor(() => {
      expect(screen.getByText("No actionable jobs found")).toBeInTheDocument();
    });
  });

  it("shows error state with retry button", async () => {
    mockGetTrackerData.mockRejectedValue(new Error("Server error"));
    renderWithProviders(<TrackerPage />);

    await waitFor(() => {
      expect(screen.getByText("Server error")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("shows Export Excel button", async () => {
    mockGetTrackerData.mockResolvedValue(fakeResult);
    renderWithProviders(<TrackerPage />);

    await waitFor(() => {
      expect(screen.getByText("TechCo")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Export Excel" })).toBeInTheDocument();
  });

  it("shows table column headers", async () => {
    mockGetTrackerData.mockResolvedValue(fakeResult);
    renderWithProviders(<TrackerPage />);

    await waitFor(() => {
      expect(screen.getByText("TechCo")).toBeInTheDocument();
    });

    const headers = screen.getAllByRole("columnheader");
    const headerTexts = headers.map((h) => h.textContent);
    expect(headerTexts).toContain("Score");
    expect(headerTexts).toContain("Decision");
    expect(headerTexts).toContain("Company");
    expect(headerTexts).toContain("Method");
    expect(headerTexts).toContain("Notes");
    expect(headerTexts).toContain("Actions");
  });
});
