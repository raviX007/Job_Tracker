import { vi, describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/test-utils";
import type { ApplicationForUpdate, AnalyzedJobForUpdate } from "@/lib/types";

vi.mock("@/lib/api");
vi.mock("@/hooks/use-profile", async () => {
  const actual = await vi.importActual<typeof import("@/hooks/use-profile")>("@/hooks/use-profile");
  return {
    ...actual,
    isDemoMode: vi.fn(() => false),
  };
});

import {
  getApplicationsForUpdate,
  getAnalyzedJobsForUpdate,
} from "@/lib/api";
import { isDemoMode } from "@/hooks/use-profile";
import OutcomesPage from "../page";

const mockGetApplicationsForUpdate = vi.mocked(getApplicationsForUpdate);
const mockGetAnalyzedJobsForUpdate = vi.mocked(getAnalyzedJobsForUpdate);
const mockIsDemoMode = vi.mocked(isDemoMode);

const fakeApps: ApplicationForUpdate[] = [
  {
    app_id: 1,
    job_id: 10,
    company: "TechCo",
    title: "Backend Engineer",
    method: "manual_apply",
    platform: "LinkedIn",
    applied_at: "2025-01-15",
    response_type: null,
    response_date: null,
    notes: "",
    match_score: 88,
  },
  {
    app_id: 2,
    job_id: 20,
    company: "DesignHub",
    title: "Frontend Developer",
    method: "cold_email",
    platform: "Email",
    applied_at: "2025-01-16",
    response_type: "interview",
    response_date: "2025-01-20",
    notes: "Phone screen done",
    match_score: 72,
  },
];

const fakeJobs: AnalyzedJobForUpdate[] = [
  {
    job_id: 100,
    company: "StartupX",
    title: "Full Stack Dev",
    location: "Remote",
    job_url: "https://example.com/job/100",
    match_score: 80,
    apply_decision: "YES",
    route_action: "apply",
  },
  {
    job_id: 200,
    company: "BigCorp",
    title: "Data Engineer",
    location: null,
    job_url: null,
    match_score: 60,
    apply_decision: "MAYBE",
    route_action: "email",
  },
];

function setupMocks() {
  mockGetApplicationsForUpdate.mockResolvedValue(fakeApps);
  mockGetAnalyzedJobsForUpdate.mockResolvedValue(fakeJobs);
}

describe("OutcomesPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockIsDemoMode.mockReturnValue(false);
  });

  it("renders loading skeleton initially", () => {
    mockGetApplicationsForUpdate.mockReturnValue(new Promise(() => {}));
    mockGetAnalyzedJobsForUpdate.mockReturnValue(new Promise(() => {}));

    renderWithProviders(<OutcomesPage />);
    expect(screen.getByText("Update Outcomes")).toBeInTheDocument();
  });

  it("renders Update Existing tab with application cards", async () => {
    setupMocks();
    renderWithProviders(<OutcomesPage />);

    await waitFor(() => {
      expect(screen.getByText("TechCo")).toBeInTheDocument();
    });
    expect(screen.getByText("DesignHub")).toBeInTheDocument();
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText("Frontend Developer")).toBeInTheDocument();
  });

  it("shows empty state for update tab", async () => {
    mockGetApplicationsForUpdate.mockResolvedValue([]);
    mockGetAnalyzedJobsForUpdate.mockResolvedValue(fakeJobs);

    renderWithProviders(<OutcomesPage />);

    await waitFor(() => {
      expect(
        screen.getByText("No applications to update. Log some applications first."),
      ).toBeInTheDocument();
    });
  });

  it("renders Log New Application tab", async () => {
    setupMocks();
    const user = userEvent.setup();
    renderWithProviders(<OutcomesPage />);

    await waitFor(() => {
      expect(screen.getByText("TechCo")).toBeInTheDocument();
    });

    // Switch to Log tab
    await user.click(screen.getByRole("tab", { name: "Log New Application" }));

    await waitFor(() => {
      expect(screen.getByText("StartupX")).toBeInTheDocument();
    });
    expect(screen.getByText("BigCorp")).toBeInTheDocument();
    expect(screen.getByText("Full Stack Dev")).toBeInTheDocument();
  });

  it("shows empty state for log tab", async () => {
    mockGetApplicationsForUpdate.mockResolvedValue(fakeApps);
    mockGetAnalyzedJobsForUpdate.mockResolvedValue([]);

    const user = userEvent.setup();
    renderWithProviders(<OutcomesPage />);

    await waitFor(() => {
      expect(screen.getByText("TechCo")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("tab", { name: "Log New Application" }));

    await waitFor(() => {
      expect(
        screen.getByText("No eligible analyzed jobs to log. Run the pipeline to analyze more jobs."),
      ).toBeInTheDocument();
    });
  });

  it("shows error state with retry button", async () => {
    mockGetApplicationsForUpdate.mockRejectedValue(new Error("Update fetch failed"));
    mockGetAnalyzedJobsForUpdate.mockResolvedValue([]);

    renderWithProviders(<OutcomesPage />);

    await waitFor(() => {
      expect(screen.getByText("Update fetch failed")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("shows demo mode message", () => {
    mockIsDemoMode.mockReturnValue(true);

    renderWithProviders(<OutcomesPage />);

    expect(
      screen.getByText(/Outcome updates are disabled in demo mode/),
    ).toBeInTheDocument();
  });
});
