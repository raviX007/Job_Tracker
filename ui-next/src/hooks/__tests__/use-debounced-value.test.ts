import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDebouncedValue } from "../use-debounced-value";

describe("useDebouncedValue", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns initial value immediately", () => {
    const { result } = renderHook(() => useDebouncedValue("hello", 300));
    expect(result.current).toBe("hello");
  });

  it("debounces value changes", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebouncedValue(value, 300),
      { initialProps: { value: "hello" } },
    );

    // Change value
    rerender({ value: "world" });

    // Not yet updated
    expect(result.current).toBe("hello");

    // Advance past delay
    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(result.current).toBe("world");
  });

  it("uses custom delay", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebouncedValue(value, 500),
      { initialProps: { value: "a" } },
    );

    rerender({ value: "b" });

    // Not yet at 500ms
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(result.current).toBe("a");

    // Now at 500ms
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(result.current).toBe("b");
  });
});
