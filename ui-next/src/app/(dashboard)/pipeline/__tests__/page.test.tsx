import { vi, describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/test-utils";

vi.mock("@/lib/api");
vi.mock("@/hooks/use-profile", async () => {
  const actual = await vi.importActual<typeof import("@/hooks/use-profile")>("@/hooks/use-profile");
  return {
    ...actual,
    isDemoMode: vi.fn(() => false),
  };
});

import { runMainPipeline, runStartupScout, getPipelineRunStatus } from "@/lib/api";
import { isDemoMode } from "@/hooks/use-profile";
import PipelinePage from "../page";

const mockRunMainPipeline = vi.mocked(runMainPipeline);
const mockRunStartupScout = vi.mocked(runStartupScout);
const mockGetPipelineRunStatus = vi.mocked(getPipelineRunStatus);
const mockIsDemoMode = vi.mocked(isDemoMode);

describe("PipelinePage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockIsDemoMode.mockReturnValue(false);
  });

  it("renders page with controls", () => {
    renderWithProviders(<PipelinePage />);

    expect(screen.getByText("Pipeline Runner")).toBeInTheDocument();
    expect(screen.getByText("Main Pipeline")).toBeInTheDocument();
    expect(screen.getByText("Startup Scout")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run Pipeline" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run Startup Scout" })).toBeInTheDocument();
  });

  it("shows info tables", () => {
    renderWithProviders(<PipelinePage />);

    expect(screen.getByText("Pipeline Steps")).toBeInTheDocument();
    expect(screen.getByText("Source Groups")).toBeInTheDocument();
    expect(screen.getByText("Startup Scout Steps")).toBeInTheDocument();
    expect(screen.getByText("Startup Sources")).toBeInTheDocument();
  });

  it("shows demo mode warning and disables buttons", () => {
    mockIsDemoMode.mockReturnValue(true);

    renderWithProviders(<PipelinePage />);

    expect(
      screen.getByText("Pipeline execution is disabled in demo mode."),
    ).toBeInTheDocument();

    const runButton = screen.getByRole("button", { name: "Run Pipeline" });
    expect(runButton).toBeDisabled();
  });

  it("Run button triggers pipeline", async () => {
    mockRunMainPipeline.mockResolvedValue({
      run_id: "run-123",
      pipeline: "main",
      source: "all",
      limit: 10,
      status: "running",
    });

    const user = userEvent.setup();
    renderWithProviders(<PipelinePage />);

    await user.click(screen.getByRole("button", { name: "Run Pipeline" }));

    expect(mockRunMainPipeline).toHaveBeenCalledWith("all", 10);
  });

  it("shows running status after pipeline starts", async () => {
    mockRunMainPipeline.mockResolvedValue({
      run_id: "run-123",
      pipeline: "main",
      source: "all",
      limit: 10,
      status: "running",
    });

    const user = userEvent.setup();
    renderWithProviders(<PipelinePage />);

    await user.click(screen.getByRole("button", { name: "Run Pipeline" }));

    await waitFor(() => {
      expect(screen.getByText("Pipeline running...")).toBeInTheDocument();
    });
  });
});
