import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { ProfileProvider, useProfile, isDemoMode } from "../use-profile";

// Helper component that exposes hook values
function ProfileDisplay() {
  const { profileId, setProfileId } = useProfile();
  return (
    <div>
      <span data-testid="profile-id">{profileId}</span>
      <button onClick={() => setProfileId(5)}>Set to 5</button>
    </div>
  );
}

describe("useProfile", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("defaults profileId to 1", () => {
    render(
      <ProfileProvider>
        <ProfileDisplay />
      </ProfileProvider>,
    );
    expect(screen.getByTestId("profile-id")).toHaveTextContent("1");
  });

  it("reads profileId from localStorage", async () => {
    localStorage.setItem("job-tracker-profile-id", "3");
    render(
      <ProfileProvider>
        <ProfileDisplay />
      </ProfileProvider>,
    );
    // useEffect reads localStorage asynchronously
    expect(await screen.findByText("3")).toBeInTheDocument();
  });

  it("ignores invalid localStorage values", () => {
    localStorage.setItem("job-tracker-profile-id", "not-a-number");
    render(
      <ProfileProvider>
        <ProfileDisplay />
      </ProfileProvider>,
    );
    expect(screen.getByTestId("profile-id")).toHaveTextContent("1");
  });

  it("ignores zero or negative localStorage values", () => {
    localStorage.setItem("job-tracker-profile-id", "0");
    render(
      <ProfileProvider>
        <ProfileDisplay />
      </ProfileProvider>,
    );
    expect(screen.getByTestId("profile-id")).toHaveTextContent("1");
  });

  it("setProfileId updates context and localStorage", async () => {
    render(
      <ProfileProvider>
        <ProfileDisplay />
      </ProfileProvider>,
    );
    await act(async () => {
      screen.getByText("Set to 5").click();
    });
    expect(screen.getByTestId("profile-id")).toHaveTextContent("5");
    expect(localStorage.getItem("job-tracker-profile-id")).toBe("5");
  });
});

describe("isDemoMode", () => {
  const originalEnv = process.env.NEXT_PUBLIC_DEMO_MODE;

  afterEach(() => {
    if (originalEnv === undefined) {
      delete process.env.NEXT_PUBLIC_DEMO_MODE;
    } else {
      process.env.NEXT_PUBLIC_DEMO_MODE = originalEnv;
    }
  });

  it("returns false by default", () => {
    delete process.env.NEXT_PUBLIC_DEMO_MODE;
    expect(isDemoMode()).toBe(false);
  });

  it('returns true when env is "true"', () => {
    process.env.NEXT_PUBLIC_DEMO_MODE = "true";
    expect(isDemoMode()).toBe(true);
  });
});
