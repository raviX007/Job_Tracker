import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import React from "react";

// Ensure DOM cleanup between tests (RTL auto-cleanup needs globals: true otherwise)
afterEach(() => {
  cleanup();
});

// Mock recharts ResponsiveContainer — jsdom has no layout engine
vi.mock("recharts", async () => {
  const actual = await vi.importActual<typeof import("recharts")>("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", { "data-testid": "responsive-container" }, children),
  };
});
