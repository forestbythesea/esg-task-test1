import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";

function ConfidenceBadge({ value }: { value: string }) {
  return <span className={`badge ${value}`}>{value}</span>;
}

describe("dashboard primitives", () => {
  it("renders confidence labels", () => {
    render(<ConfidenceBadge value="high" />);
    expect(screen.getByText("high")).toBeInTheDocument();
  });
});

