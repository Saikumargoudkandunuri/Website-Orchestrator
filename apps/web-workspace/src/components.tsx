import React, { useState } from "react";

export interface Node {
  id: string;
  type: string;
  label: string;
  x: number;
  y: number;
}

export interface CanvasViewportProps {
  nodes: Node[];
  onNodeDrag: (id: string, x: number, y: number) => void;
  presenceCursors: Record<string, { x: number; y: number; name: string }>;
}

export const CanvasViewport: React.FC<CanvasViewportProps> = ({
  nodes,
  onNodeDrag,
  presenceCursors,
}) => {
  const [zoom, setZoom] = useState<number>(1.0);
  return (
    <div className="canvas-viewport relative w-full h-screen bg-slate-900 overflow-hidden select-none">
      <div className="absolute top-4 left-4 z-10 text-white font-mono text-sm bg-slate-800 p-2 rounded">
        Zoom: {(zoom * 100).toFixed(0)}%
      </div>
      <div
        className="canvas-container relative w-full h-full transform origin-top-left"
        style={{ transform: `scale(${zoom})` }}
      >
        {nodes.map((node) => (
          <div
            key={node.id}
            className="canvas-node absolute bg-slate-800 border border-slate-700 text-white rounded p-4 shadow cursor-pointer hover:border-violet-500 transition-colors"
            style={{ left: node.x, top: node.y, width: 140, height: 80 }}
            onMouseDown={(e) => {
              // Simulating drag-to-reposition
              onNodeDrag(node.id, node.x + 10, node.y + 10);
            }}
          >
            <div className="font-semibold text-xs text-slate-400">{node.type}</div>
            <div className="text-sm font-medium">{node.label}</div>
          </div>
        ))}

        {Object.entries(presenceCursors).map(([id, cursor]) => (
          <div
            key={id}
            className="absolute pointer-events-none text-xs text-white bg-violet-600 px-1 rounded shadow"
            style={{ left: cursor.x, top: cursor.y }}
          >
            {cursor.name}
          </div>
        ))}
      </div>
    </div>
  );
};

export interface CommandOption {
  id: string;
  title: string;
  category: string;
}

export interface WorkspaceCommandPaletteProps {
  options: CommandOption[];
  onSelect: (option: CommandOption) => void;
}

export const WorkspaceCommandPalette: React.FC<WorkspaceCommandPaletteProps> = ({
  options,
  onSelect,
}) => {
  const [filter, setFilter] = useState<string>("");
  const matched = options.filter((o) =>
    o.title.toLowerCase().includes(filter.toLowerCase())
  );
  return (
    <div className="command-palette bg-slate-950 border border-slate-800 rounded-lg p-4 max-w-md w-full shadow-2xl">
      <input
        type="text"
        placeholder="Type a command or action (e.g. Crawl)..."
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-2 text-white focus:outline-none focus:border-violet-500"
      />
      <div className="results mt-3 space-y-1">
        {matched.map((opt) => (
          <div
            key={opt.id}
            onClick={() => onSelect(opt)}
            className="option flex items-center justify-between p-2 rounded hover:bg-slate-900 cursor-pointer text-white transition-colors"
          >
            <span className="text-sm font-medium">{opt.title}</span>
            <span className="text-xs text-slate-500 uppercase">{opt.category}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
