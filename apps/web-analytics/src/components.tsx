import React, { useState } from "react";

export interface AlertRuleConfig {
  metricName: string;
  threshold: number;
  comparison: "above" | "below";
}

export interface AlertRuleConsoleProps {
  onSaveRule: (rule: AlertRuleConfig) => void;
  metrics: string[];
}

export const AlertRuleConsole: React.FC<AlertRuleConsoleProps> = ({
  onSaveRule,
  metrics,
}) => {
  const [metric, setMetric] = useState<string>(metrics[0] || "");
  const [threshold, setThreshold] = useState<number>(0);
  const [comparison, setComparison] = useState<"above" | "below">("above");

  const handleSave = () => {
    onSaveRule({
      metricName: metric,
      threshold,
      comparison,
    });
  };

  return (
    <div className="alert-rule-console bg-slate-900 text-white p-4 rounded shadow">
      <h3 className="text-lg font-bold mb-3">Configure KPI Threshold Alert</h3>
      <div className="space-y-3">
        <div>
          <label className="block text-xs text-slate-400 uppercase font-bold">Metric</label>
          <select
            value={metric}
            onChange={(e) => setMetric(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-white"
          >
            {metrics.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs text-slate-400 uppercase font-bold">Trigger Rule</label>
          <div className="flex gap-2">
            <select
              value={comparison}
              onChange={(e) => setComparison(e.target.value as "above" | "below")}
              className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-white"
            >
              <option value="above">Above</option>
              <option value="below">Below</option>
            </select>
            <input
              type="number"
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-white"
            />
          </div>
        </div>

        <button
          onClick={handleSave}
          className="w-full bg-violet-600 hover:bg-violet-700 text-white rounded py-2 text-sm font-semibold transition-colors"
        >
          Activate Alert Rule
        </button>
      </div>
    </div>
  );
};

export interface CustomQueryBuilderProps {
  metrics: string[];
  dimensions: string[];
  onRunQuery: (query: { metric: string; dimension: string; range: string }) => void;
}

export const CustomQueryBuilder: React.FC<CustomQueryBuilderProps> = ({
  metrics,
  dimensions,
  onRunQuery,
}) => {
  const [metric, setMetric] = useState<string>(metrics[0] || "");
  const [dimension, setDimension] = useState<string>(dimensions[0] || "");
  const [range, setRange] = useState<string>("7d");

  return (
    <div className="query-builder bg-slate-950 p-4 rounded border border-slate-800 text-white">
      <div className="flex flex-wrap gap-4 items-end">
        <div>
          <label className="block text-xs text-slate-400 font-bold uppercase mb-1">Metric</label>
          <select
            value={metric}
            onChange={(e) => setMetric(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-sm text-white"
          >
            {metrics.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs text-slate-400 font-bold uppercase mb-1">Dimension</label>
          <select
            value={dimension}
            onChange={(e) => setDimension(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-sm text-white"
          >
            {dimensions.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs text-slate-400 font-bold uppercase mb-1">Time Range</label>
          <select
            value={range}
            onChange={(e) => setRange(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-sm text-white"
          >
            <option value="24h">Last 24 Hours</option>
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
          </select>
        </div>

        <button
          onClick={() => onRunQuery({ metric, dimension, range })}
          className="bg-violet-600 hover:bg-violet-700 text-white font-semibold rounded px-4 py-1 text-sm transition-colors"
        >
          Query
        </button>
      </div>
    </div>
  );
};
