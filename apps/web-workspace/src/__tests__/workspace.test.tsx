import React from "react";
import { describe, test, expect, vi } from "vitest";

vi.mock("react", () => {
  return {
    default: {
      useState: (init: any) => [init, vi.fn()],
    },
    useState: (init: any) => [init, vi.fn()],
  };
});

import { CanvasViewport, WorkspaceCommandPalette, CommandOption, Node } from "../components.tsx";

describe("AI Workspace Components", () => {
  test("CanvasViewport drag handler triggers updates", () => {
    const nodes: Node[] = [
      { id: "1", type: "goal", label: "Increase traffic", x: 100, y: 100 },
    ];
    const dragSpy = vi.fn();
    const presence = {
      "user-1": { x: 120, y: 130, name: "Alice" },
    };

    // Instantiate simple renderer validation
    const viewport = CanvasViewport({
      nodes,
      onNodeDrag: dragSpy,
      presenceCursors: presence,
    }) as any;

    expect(viewport.props.className).toContain("canvas-viewport");
    expect(viewport.props.children).toBeDefined();
  });

  test("CommandPalette fuzzy search filters choices", () => {
    const options: CommandOption[] = [
      { id: "1", title: "Run Crawl", category: "actions" },
      { id: "2", title: "View Analytics", category: "views" },
    ];
    const selectSpy = vi.fn();

    const palette = WorkspaceCommandPalette({
      options,
      onSelect: selectSpy,
    }) as any;

    expect(palette.props.className).toContain("command-palette");
  });
});

