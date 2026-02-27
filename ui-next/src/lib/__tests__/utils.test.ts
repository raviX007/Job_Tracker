import { describe, it, expect } from "vitest";
import {
  scoreColor,
  scoreBadgeColor,
  decisionColor,
  statusColor,
  formatDate,
  formatDateTime,
  stripAnsi,
} from "../utils";

describe("scoreColor", () => {
  it("returns emerald for scores >= 80", () => {
    expect(scoreColor(80)).toContain("emerald");
    expect(scoreColor(100)).toContain("emerald");
  });

  it("returns teal for scores 60-79", () => {
    expect(scoreColor(60)).toContain("teal");
    expect(scoreColor(79)).toContain("teal");
  });

  it("returns amber for scores 40-59", () => {
    expect(scoreColor(40)).toContain("amber");
    expect(scoreColor(59)).toContain("amber");
  });

  it("returns red for scores < 40", () => {
    expect(scoreColor(0)).toContain("red");
    expect(scoreColor(39)).toContain("red");
  });
});

describe("scoreBadgeColor", () => {
  it("returns emerald-500 for scores >= 80", () => {
    expect(scoreBadgeColor(85)).toBe("bg-emerald-500");
  });

  it("returns teal-500 for scores 60-79", () => {
    expect(scoreBadgeColor(65)).toBe("bg-teal-500");
  });

  it("returns amber-500 for scores 40-59", () => {
    expect(scoreBadgeColor(50)).toBe("bg-amber-500");
  });

  it("returns red-500 for scores < 40", () => {
    expect(scoreBadgeColor(20)).toBe("bg-red-500");
  });
});

describe("decisionColor", () => {
  it("returns emerald for YES", () => {
    expect(decisionColor("YES")).toContain("emerald");
  });

  it("returns amber for MAYBE", () => {
    expect(decisionColor("MAYBE")).toContain("amber");
  });

  it("returns purple for MANUAL", () => {
    expect(decisionColor("MANUAL")).toContain("purple");
  });

  it("returns red for NO", () => {
    expect(decisionColor("NO")).toContain("red");
  });

  it("returns gray for unknown values", () => {
    expect(decisionColor("UNKNOWN")).toContain("gray");
  });
});

describe("statusColor", () => {
  it("returns gray for draft", () => {
    expect(statusColor("draft")).toContain("gray");
  });

  it("returns blue for verified", () => {
    expect(statusColor("verified")).toContain("blue");
  });

  it("returns teal for ready", () => {
    expect(statusColor("ready")).toContain("teal");
  });

  it("returns amber for queued", () => {
    expect(statusColor("queued")).toContain("amber");
  });

  it("returns emerald for sent", () => {
    expect(statusColor("sent")).toContain("emerald");
  });

  it("returns emerald for delivered", () => {
    expect(statusColor("delivered")).toContain("emerald");
  });

  it("returns red for bounced", () => {
    expect(statusColor("bounced")).toContain("red");
  });

  it("returns red for failed", () => {
    expect(statusColor("failed")).toContain("red");
  });

  it("returns gray for unknown values", () => {
    expect(statusColor("unknown")).toContain("gray");
  });
});

describe("formatDate", () => {
  it("returns — for null", () => {
    expect(formatDate(null)).toBe("—");
  });

  it("returns — for undefined", () => {
    expect(formatDate(undefined)).toBe("—");
  });

  it("formats a valid date string", () => {
    const result = formatDate("2024-01-15");
    expect(result).toContain("Jan");
    expect(result).toContain("2024");
  });
});

describe("formatDateTime", () => {
  it("returns — for null", () => {
    expect(formatDateTime(null)).toBe("—");
  });

  it("returns — for undefined", () => {
    expect(formatDateTime(undefined)).toBe("—");
  });

  it("formats a valid datetime string", () => {
    const result = formatDateTime("2024-03-15T10:30:00");
    expect(result).toContain("Mar");
  });
});

describe("stripAnsi", () => {
  it("removes ANSI color codes", () => {
    expect(stripAnsi("\x1B[31mred text\x1B[0m")).toBe("red text");
  });

  it("handles strings without ANSI codes", () => {
    expect(stripAnsi("plain text")).toBe("plain text");
  });

  it("handles empty string", () => {
    expect(stripAnsi("")).toBe("");
  });

  it("removes multiple ANSI codes", () => {
    expect(stripAnsi("\x1B[1m\x1B[32mgreen bold\x1B[0m")).toBe("green bold");
  });
});
