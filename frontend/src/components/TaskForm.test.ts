import { describe, expect, it } from "vitest";
import { errorText } from "./TaskForm";

describe("errorText", () => {
  it("reads FastAPI string detail", () => {
    expect(errorText(new Error('404 {"detail":"session not found"}'))).toBe("session not found");
  });

  it("reads the first validation message", () => {
    const body = JSON.stringify({ detail: [{ msg: "String should have at least 3 characters" }] });
    expect(errorText(new Error(`422 ${body}`))).toBe("String should have at least 3 characters");
  });

  it("hides raw 5xx bodies", () => {
    expect(errorText(new Error("500 Internal Server Error"))).toBe(
      "Server error. Try again in a moment.",
    );
  });

  it("explains network failures", () => {
    expect(errorText(new TypeError("Failed to fetch"))).toMatch(/reach the server/);
  });

  it("passes other messages through", () => {
    expect(errorText(new Error("boom"))).toBe("boom");
  });
});
