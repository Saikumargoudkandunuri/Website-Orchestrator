import React, { useState } from "react";

export interface ApprovalItem {
  id: string;
  workflowName: string;
  reason: string;
  createdAt: string;
}

export interface PendingApprovalsGridProps {
  approvals: ApprovalItem[];
  onDecide: (id: string, approve: boolean) => void;
}

export const PendingApprovalsGrid: React.FC<PendingApprovalsGridProps> = ({
  approvals,
  onDecide,
}) => {
  return (
    <div className="pending-approvals bg-slate-950 p-4 border border-slate-800 rounded text-white">
      <h3 className="text-lg font-bold mb-3">Pending Executive Approvals</h3>
      {approvals.length === 0 ? (
        <div className="text-sm text-slate-500">No executions suspended awaiting review.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {approvals.map((appr) => (
            <div key={appr.id} className="approval-card bg-slate-900 border border-slate-800 rounded p-4 shadow">
              <div className="font-semibold text-violet-400 text-sm mb-1">{appr.workflowName}</div>
              <div className="text-xs text-slate-400 mb-3">{appr.reason}</div>
              <div className="flex gap-2">
                <button
                  onClick={() => onDecide(appr.id, true)}
                  className="flex-1 bg-violet-600 hover:bg-violet-700 text-white rounded py-1.5 text-xs font-semibold transition-colors"
                >
                  Approve / Resume
                </button>
                <button
                  onClick={() => onDecide(appr.id, false)}
                  className="flex-1 bg-slate-800 hover:bg-slate-700 text-white rounded py-1.5 text-xs font-semibold transition-colors"
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export interface TraceLog {
  nodeId: string;
  type: string;
  timestamp: string;
}

export interface TraceDebuggerConsoleProps {
  logs: TraceLog[];
  status: string;
}

export const TraceDebuggerConsole: React.FC<TraceDebuggerConsoleProps> = ({
  logs,
  status,
}) => {
  return (
    <div className="trace-debugger bg-slate-900 border border-slate-800 text-white p-4 rounded font-mono text-xs">
      <div className="flex justify-between items-center mb-3">
        <span className="font-semibold uppercase text-slate-400">Execution Live Trace</span>
        <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold ${
          status === "completed" ? "bg-green-950 text-green-400 border border-green-800" :
          status === "paused" ? "bg-yellow-950 text-yellow-400 border border-yellow-800" :
          "bg-violet-950 text-violet-400 border border-violet-800"
        }`}>
          {status}
        </span>
      </div>
      <div className="space-y-2 max-h-60 overflow-y-auto">
        {logs.map((log, index) => (
          <div key={index} className="flex gap-2 text-slate-300">
            <span className="text-violet-400">[{log.timestamp}]</span>
            <span className="text-slate-400 font-semibold">{log.type}:</span>
            <span>node {log.nodeId} execution successful</span>
          </div>
        ))}
      </div>
    </div>
  );
};
