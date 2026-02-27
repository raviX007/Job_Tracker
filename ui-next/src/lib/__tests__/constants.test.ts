import { describe, it, expect } from "vitest";
import {
  DECISIONS,
  EMAIL_STATUSES,
  RESPONSE_TYPES,
  APPLICATION_METHODS,
  CHART_COLORS,
  PIPELINE_SOURCES,
  STARTUP_SOURCES,
} from "../constants";

describe("DECISIONS", () => {
  it("starts with All", () => {
    expect(DECISIONS[0]).toBe("All");
  });

  it("includes YES, MAYBE, MANUAL, NO", () => {
    expect(DECISIONS).toContain("YES");
    expect(DECISIONS).toContain("MAYBE");
    expect(DECISIONS).toContain("MANUAL");
    expect(DECISIONS).toContain("NO");
  });
});

describe("EMAIL_STATUSES", () => {
  it("starts with All", () => {
    expect(EMAIL_STATUSES[0]).toBe("All");
  });

  it("includes key statuses", () => {
    expect(EMAIL_STATUSES).toContain("draft");
    expect(EMAIL_STATUSES).toContain("sent");
    expect(EMAIL_STATUSES).toContain("bounced");
  });
});

describe("RESPONSE_TYPES", () => {
  it("includes interview and rejection", () => {
    expect(RESPONSE_TYPES).toContain("interview");
    expect(RESPONSE_TYPES).toContain("rejection");
  });
});

describe("APPLICATION_METHODS", () => {
  it("includes auto_apply and cold_email", () => {
    expect(APPLICATION_METHODS).toContain("auto_apply");
    expect(APPLICATION_METHODS).toContain("cold_email");
  });
});

describe("CHART_COLORS", () => {
  it("has at least 6 colors", () => {
    expect(CHART_COLORS.length).toBeGreaterThanOrEqual(6);
  });

  it("contains valid hex colors", () => {
    for (const color of CHART_COLORS) {
      expect(color).toMatch(/^#[0-9a-fA-F]{6}$/);
    }
  });
});

describe("PIPELINE_SOURCES", () => {
  it("has All Scrapers mapped to 'all'", () => {
    expect(PIPELINE_SOURCES["All Scrapers"]).toBe("all");
  });

  it("has multiple source entries", () => {
    expect(Object.keys(PIPELINE_SOURCES).length).toBeGreaterThan(5);
  });
});

describe("STARTUP_SOURCES", () => {
  it("has All Startup Sources entry", () => {
    expect(STARTUP_SOURCES["All Startup Sources"]).toBe("startup_scout");
  });
});
