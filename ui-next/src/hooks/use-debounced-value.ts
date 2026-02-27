import { useState, useEffect } from "react";

/**
 * Returns a debounced version of the given value.
 * The returned value only updates after `delayMs` milliseconds
 * of inactivity (no new value changes).
 */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delayMs);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delayMs]);

  return debouncedValue;
}
