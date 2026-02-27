import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Providers } from "../providers";

describe("Providers", () => {
  it("renders children", () => {
    render(
      <Providers>
        <div data-testid="child">Hello</div>
      </Providers>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
    expect(screen.getByTestId("child")).toHaveTextContent("Hello");
  });

  it("renders multiple children", () => {
    render(
      <Providers>
        <span>First</span>
        <span>Second</span>
      </Providers>,
    );
    expect(screen.getByText("First")).toBeInTheDocument();
    expect(screen.getByText("Second")).toBeInTheDocument();
  });
});
