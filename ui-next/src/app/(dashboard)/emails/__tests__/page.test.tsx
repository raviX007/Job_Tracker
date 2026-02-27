import { vi, describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import type { EmailQueueItem, EmailStatusCounts, PaginatedResult } from "@/lib/types";

vi.mock("@/lib/api");

import { getEmailQueue, getEmailStatuses, getEmailSources } from "@/lib/api";
import EmailsPage from "../page";

const mockGetEmailQueue = vi.mocked(getEmailQueue);
const mockGetEmailStatuses = vi.mocked(getEmailStatuses);
const mockGetEmailSources = vi.mocked(getEmailSources);

const fakeEmails: EmailQueueItem[] = [
  {
    id: 1,
    recipient_email: "alice@example.com",
    recipient_name: "Alice Smith",
    recipient_role: "CTO",
    recipient_source: "LinkedIn",
    subject: "Excited about the Backend Engineer role",
    body_plain: "Hi Alice, I noticed...",
    email_verified: true,
    email_verification_result: "valid",
    status: "draft",
    sent_at: null,
    created_at: "2025-01-15T10:00:00Z",
    job_title: "Backend Engineer",
    job_company: "TechCo",
    job_url: "https://example.com/job/1",
    job_source: "LinkedIn",
    match_score: 88,
    route_action: "email",
  },
  {
    id: 2,
    recipient_email: "bob@startup.io",
    recipient_name: "Bob Jones",
    recipient_role: "Founder",
    recipient_source: "YC",
    subject: "Re: Full Stack role at StartupIO",
    body_plain: "Dear Bob...",
    email_verified: false,
    email_verification_result: null,
    status: "sent",
    sent_at: "2025-01-16T12:00:00Z",
    created_at: "2025-01-16T10:00:00Z",
    job_title: "Full Stack Developer",
    job_company: "StartupIO",
    job_url: "https://example.com/job/2",
    job_source: "YC",
    match_score: 75,
    route_action: "email",
  },
];

const fakeStatusCounts: EmailStatusCounts = {
  draft: 3,
  sent: 5,
  failed: 1,
};

const fakePaginatedEmails: PaginatedResult<EmailQueueItem[]> = {
  data: fakeEmails,
  totalCount: 2,
};

function setupMocks() {
  mockGetEmailQueue.mockResolvedValue(fakePaginatedEmails);
  mockGetEmailStatuses.mockResolvedValue(fakeStatusCounts);
  mockGetEmailSources.mockResolvedValue(["LinkedIn", "YC"]);
}

describe("EmailsPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders loading state initially", () => {
    mockGetEmailQueue.mockReturnValue(new Promise(() => {}));
    mockGetEmailStatuses.mockReturnValue(new Promise(() => {}));
    mockGetEmailSources.mockResolvedValue([]);

    renderWithProviders(<EmailsPage />);
    expect(screen.getByText("Cold Emails")).toBeInTheDocument();
  });

  it("renders email cards with recipient data", async () => {
    setupMocks();
    renderWithProviders(<EmailsPage />);

    await waitFor(() => {
      expect(screen.getByText("Alice Smith")).toBeInTheDocument();
    });
    expect(screen.getByText("Bob Jones")).toBeInTheDocument();
    expect(screen.getByText("TechCo")).toBeInTheDocument();
    expect(screen.getByText("StartupIO")).toBeInTheDocument();
  });

  it("shows status count badges", async () => {
    setupMocks();
    renderWithProviders(<EmailsPage />);

    await waitFor(() => {
      expect(screen.getByText("Alice Smith")).toBeInTheDocument();
    });

    // Status counts rendered as "status: count" badges
    expect(screen.getByText(/draft: 3/)).toBeInTheDocument();
    expect(screen.getByText(/sent: 5/)).toBeInTheDocument();
    expect(screen.getByText(/failed: 1/)).toBeInTheDocument();
  });

  it("shows empty state when no emails", async () => {
    mockGetEmailQueue.mockResolvedValue({ data: [], totalCount: 0 });
    mockGetEmailStatuses.mockResolvedValue({});
    mockGetEmailSources.mockResolvedValue([]);

    renderWithProviders(<EmailsPage />);

    await waitFor(() => {
      expect(screen.getByText("No emails in queue")).toBeInTheDocument();
    });
  });

  it("shows error state with retry button", async () => {
    mockGetEmailQueue.mockRejectedValue(new Error("Connection failed"));
    mockGetEmailStatuses.mockResolvedValue({});
    mockGetEmailSources.mockResolvedValue([]);

    renderWithProviders(<EmailsPage />);

    await waitFor(() => {
      expect(screen.getByText("Connection failed")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
