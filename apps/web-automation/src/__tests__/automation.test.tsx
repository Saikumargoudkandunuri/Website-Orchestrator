import { describe, test, expect, vi } from "vitest";

vi.mock("react", () => {
  return {
    default: {
      useState: (init: any) => [init, vi.fn()],
    },
    useState: (init: any) => [init, vi.fn()],
  };
});
import { PendingApprovalsGrid, TraceDebuggerConsole } from "../components.tsx";

describe("Automation Studio UI Components", () => {
  test("Pending approvals grid lists suspended runs", () => {
    const decideSpy = vi.fn();
    const approvals = [
      { id: "1", workflowName: "Alt suggest", reason: "approval gate", createdAt: "now" },
    ];

    const grid = PendingApprovalsGrid({
      approvals,
      onDecide: decideSpy,
    });

    expect(grid.props.className).toContain("pending-approvals");
  });

  test("Trace debugger displays sequence of step logs", () => {
    const logs = [
      { nodeId: "n-1", type: "script", timestamp: "12:00:00" },
    ];

    const trace = TraceDebuggerConsole({
      logs,
      status: "completed",
    });

    expect(trace.props.className).toContain("trace-debugger");
  });
});
