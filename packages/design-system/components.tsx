import React from "react";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger";
}

export const Button: React.FC<ButtonProps> = ({
  variant = "primary",
  children,
  className = "",
  ...props
}) => {
  const baseStyle = "px-4 py-2 rounded text-sm font-semibold transition-colors focus:outline-none";
  const styles =
    variant === "primary" ? "bg-violet-600 hover:bg-violet-700 text-white" :
    variant === "danger" ? "bg-red-600 hover:bg-red-700 text-white" :
    "bg-slate-800 hover:bg-slate-700 text-slate-200";

  return (
    <button className={`${baseStyle} ${styles} ${className}`} {...props}>
      {children}
    </button>
  );
};

export interface BadgeProps {
  label: string;
  variant?: "success" | "warning" | "info";
}

export const Badge: React.FC<BadgeProps> = ({
  label,
  variant = "info",
}) => {
  const styles =
    variant === "success" ? "bg-green-950 text-green-400 border-green-800" :
    variant === "warning" ? "bg-yellow-950 text-yellow-400 border-yellow-800" :
    "bg-violet-950 text-violet-400 border-violet-850";

  return (
    <span className={`inline-block px-2.5 py-0.5 text-xs font-bold uppercase rounded border ${styles}`}>
      {label}
    </span>
  );
};

export interface AIStateProps {
  streaming: boolean;
}

export const AIState: React.FC<AIStateProps> = ({
  streaming,
}) => {
  return (
    <div className="flex items-center gap-2 font-mono text-xs text-slate-400">
      <span className={`h-2.5 w-2.5 rounded-full ${streaming ? "bg-violet-500 animate-pulse" : "bg-slate-600"}`} />
      <span>{streaming ? "AI Engine streaming..." : "AI Engine idle"}</span>
    </div>
  );
};
