import { vi, describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";

vi.mock("@/lib/api");

import {
  getDailyTrends,
  getScoreDistribution,
  getSourceBreakdown,
  getCompanyTypes,
  getResponseRates,
  getRouteBreakdown,
} from "@/lib/api";
import AnalyticsPage from "../page";

const mockGetDailyTrends = vi.mocked(getDailyTrends);
const mockGetScoreDistribution = vi.mocked(getScoreDistribution);
const mockGetSourceBreakdown = vi.mocked(getSourceBreakdown);
const mockGetCompanyTypes = vi.mocked(getCompanyTypes);
const mockGetResponseRates = vi.mocked(getResponseRates);
const mockGetRouteBreakdown = vi.mocked(getRouteBreakdown);

function setupMocks() {
  mockGetDailyTrends.mockResolvedValue([
    { date: "2025-01-15", jobs_scraped: 10, jobs_analyzed: 5, emails_queued: 2 },
  ]);
  mockGetScoreDistribution.mockResolvedValue([
    { bracket: "80-100", count: 12 },
  ]);
  mockGetSourceBreakdown.mockResolvedValue([
    { source: "LinkedIn", count: 25, avg_score: 72, yes_count: 10 },
  ]);
  mockGetCompanyTypes.mockResolvedValue([
    { company_type: "Series B", count: 8, avg_score: 75, gap_tolerant_count: 3 },
  ]);
  mockGetResponseRates.mockResolvedValue([
    { method: "cold_email", total: 20, responded: 5, interviews: 2, offers: 1, rejections: 2 },
  ]);
  mockGetRouteBreakdown.mockResolvedValue({ apply: 30, email: 15 });
}

function setupPendingMocks() {
  mockGetDailyTrends.mockReturnValue(new Promise(() => {}));
  mockGetScoreDistribution.mockReturnValue(new Promise(() => {}));
  mockGetSourceBreakdown.mockReturnValue(new Promise(() => {}));
  mockGetCompanyTypes.mockReturnValue(new Promise(() => {}));
  mockGetResponseRates.mockReturnValue(new Promise(() => {}));
  mockGetRouteBreakdown.mockReturnValue(new Promise(() => {}));
}

describe("AnalyticsPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders loading skeleton initially", () => {
    setupPendingMocks();
    renderWithProviders(<AnalyticsPage />);
    expect(screen.getByText("Analytics")).toBeInTheDocument();
  });

  it("renders all 6 chart cards", async () => {
    setupMocks();
    renderWithProviders(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText("Daily Activity Trend")).toBeInTheDocument();
    });
    expect(screen.getByText("Score Distribution")).toBeInTheDocument();
    expect(screen.getByText("Source Breakdown")).toBeInTheDocument();
    expect(screen.getByText("Company Types")).toBeInTheDocument();
    expect(screen.getByText("Response Rates")).toBeInTheDocument();
    expect(screen.getByText("Route Breakdown")).toBeInTheDocument();
  });

  it("shows error state", async () => {
    mockGetDailyTrends.mockRejectedValue(new Error("Analytics fetch failed"));
    mockGetScoreDistribution.mockRejectedValue(new Error("Analytics fetch failed"));
    mockGetSourceBreakdown.mockRejectedValue(new Error("Analytics fetch failed"));
    mockGetCompanyTypes.mockRejectedValue(new Error("Analytics fetch failed"));
    mockGetResponseRates.mockRejectedValue(new Error("Analytics fetch failed"));
    mockGetRouteBreakdown.mockRejectedValue(new Error("Analytics fetch failed"));

    renderWithProviders(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText("Analytics fetch failed")).toBeInTheDocument();
    });
  });

  it("handles empty data without crashing", async () => {
    mockGetDailyTrends.mockResolvedValue([]);
    mockGetScoreDistribution.mockResolvedValue([]);
    mockGetSourceBreakdown.mockResolvedValue([]);
    mockGetCompanyTypes.mockResolvedValue([]);
    mockGetResponseRates.mockResolvedValue([]);
    mockGetRouteBreakdown.mockResolvedValue({});

    renderWithProviders(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText("Daily Activity Trend")).toBeInTheDocument();
    });
  });
});
