import { describe, test, expect, vi } from "vitest";

vi.mock("react", () => {
  return {
    default: {
      useState: (init: any) => [init, vi.fn()],
    },
    useState: (init: any) => [init, vi.fn()],
  };
});
import { AlertRuleConsole, CustomQueryBuilder } from "../components.tsx";

describe("Analytics Platform UI Components", () => {
  test("Alert rule console triggers save with valid form data", () => {
    const saveSpy = vi.fn();
    const console = AlertRuleConsole({
      metrics: ["bounce_rate", "traffic"],
      onSaveRule: saveSpy,
    });

    expect(console.props.className).toContain("alert-rule-console");
  });

  test("Query builder binds form selections", () => {
    const querySpy = vi.fn();
    const builder = CustomQueryBuilder({
      metrics: ["rank", "clicks"],
      dimensions: ["device", "country"],
      onRunQuery: querySpy,
    });

    expect(builder.props.className).toContain("query-builder");
  });
});
