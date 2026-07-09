import React from 'react';
import { motion, HTMLMotionProps } from 'framer-motion';

// ─── GlassCard ───
export const GlassCard: React.FC<Omit<HTMLMotionProps<'div'>, 'children'> & { children?: React.ReactNode; hoverElevate?: boolean }> = ({ 
  children, 
  className = '', 
  hoverElevate = true, 
  ...props 
}) => {
  return (
    <motion.div
      whileHover={hoverElevate ? { 
        y: -4, 
        boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.05), 0 10px 10px -5px rgba(0, 0, 0, 0.02)",
        borderColor: "rgba(99, 102, 241, 0.2)"
      } : undefined}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
      className={`glass rounded-2xl border border-white/60 p-5 shadow-sm transition-colors ${className}`}
      {...props}
    >
      {children}
    </motion.div>
  );
};

// ─── GradientCard ───
export const GradientCard: React.FC<Omit<HTMLMotionProps<'div'>, 'children'> & { children?: React.ReactNode; hoverGlow?: boolean }> = ({
  children,
  className = '',
  hoverGlow = true,
  ...props
}) => {
  return (
    <motion.div
      whileHover={hoverGlow ? { scale: 1.01 } : undefined}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
      className={`relative overflow-hidden rounded-2xl border border-white/65 p-6 shadow-md bg-gradient-to-br from-indigo-50/50 via-purple-50/40 to-pink-50/30 backdrop-blur-2xl ${className}`}
      {...props}
    >
      {/* Ambient Radial Highlights */}
      <div className="absolute -right-20 -top-20 h-48 w-48 rounded-full bg-indigo-400/10 blur-3xl" />
      <div className="absolute -left-20 -bottom-20 h-48 w-48 rounded-full bg-pink-400/10 blur-3xl" />
      <div className="relative z-10">{children}</div>
    </motion.div>
  );
};

// ─── MetricCard ───
export const MetricCard: React.FC<{
  label: string;
  value: string | number;
  change?: string;
  changeType?: 'positive' | 'negative' | 'neutral';
  description?: string;
  icon?: React.ReactNode;
}> = ({ label, value, change, changeType = 'neutral', description, icon }) => {
  return (
    <GlassCard className="relative overflow-hidden group">
      <div className="flex justify-between items-start">
        <div className="space-y-1">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-widest block">{label}</span>
          <h3 className="text-3xl font-extrabold text-slate-900 tracking-tight">{value}</h3>
        </div>
        {icon && (
          <div className="p-2.5 bg-indigo-50 rounded-xl border border-indigo-100/50 text-indigo-600 transition-colors group-hover:bg-indigo-600 group-hover:text-white">
            {icon}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 mt-4">
        {change && (
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
            changeType === 'positive' ? 'bg-emerald-50 text-emerald-600 border border-emerald-100' :
            changeType === 'negative' ? 'bg-rose-50 text-rose-600 border border-rose-100' :
            'bg-slate-50 text-slate-600 border border-slate-100'
          }`}>
            {change}
          </span>
        )}
        {description && <span className="text-xs text-slate-400">{description}</span>}
      </div>
    </GlassCard>
  );
};

// ─── AnimatedButton ───
export const AnimatedButton: React.FC<Omit<HTMLMotionProps<'button'>, 'children'> & { children?: React.ReactNode; variant?: 'primary' | 'secondary' | 'ghost' | 'danger' }> = ({
  children,
  className = '',
  variant = 'secondary',
  ...props
}) => {
  const baseStyle = "btn text-xs font-semibold flex items-center justify-center gap-1.5 transition-all outline-none";
  const styles = {
    primary: "bg-indigo-600 text-white shadow-sm border border-indigo-700/50 hover:bg-indigo-700",
    secondary: "bg-white/80 text-slate-700 border border-slate-200/80 hover:bg-slate-50 shadow-sm",
    ghost: "bg-transparent text-slate-500 hover:bg-slate-100/80",
    danger: "bg-rose-600 text-white border border-rose-700/50 hover:bg-rose-700 shadow-sm",
  };

  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      className={`${baseStyle} ${styles[variant]} ${className}`}
      {...props}
    >
      {children}
    </motion.button>
  );
};

// ─── GlassInput ───
export const GlassInput: React.FC<React.InputHTMLAttributes<HTMLInputElement>> = ({ className = '', ...props }) => {
  return (
    <input
      className={`w-full bg-white/50 border border-slate-200/80 text-slate-800 text-xs px-3.5 py-2.5 rounded-xl focus:outline-none focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-500/10 placeholder:text-slate-400 transition-all ${className}`}
      {...props}
    />
  );
};

// ─── StatusBadge ───
export const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const s = status.toLowerCase();
  const styles: Record<string, string> = {
    approved: "bg-emerald-50 text-emerald-700 border-emerald-100",
    applied: "bg-emerald-50 text-emerald-700 border-emerald-100",
    pending: "bg-amber-50 text-amber-700 border-amber-100",
    rejected: "bg-rose-50 text-rose-700 border-rose-100",
    critical: "bg-rose-50 text-rose-700 border-rose-100",
    high: "bg-rose-50 text-rose-700 border-rose-100",
    medium: "bg-amber-50 text-amber-700 border-amber-100",
    low: "bg-sky-50 text-sky-700 border-sky-100",
    success: "bg-emerald-50 text-emerald-700 border-emerald-100",
    failed: "bg-rose-50 text-rose-700 border-rose-100",
  };

  const currentStyle = styles[s] || "bg-slate-50 text-slate-600 border-slate-100";

  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border ${currentStyle}`}>
      {status}
    </span>
  );
};

// ─── TimelineItem ───
export const TimelineItem: React.FC<{
  title: string;
  time: string;
  detail?: string;
  type?: 'success' | 'warning' | 'error' | 'info';
}> = ({ title, time, detail, type = 'info' }) => {
  const dotColor = {
    success: 'bg-emerald-500',
    warning: 'bg-amber-500',
    error: 'bg-rose-500',
    info: 'bg-indigo-500'
  };

  return (
    <div className="flex gap-4 relative group pl-4">
      <div className={`h-2.5 w-2.5 rounded-full ${dotColor[type]} mt-1.5 flex-shrink-0 z-10 ring-4 ring-white shadow-sm`} />
      <div className="space-y-1 pb-4">
        <p className="text-xs font-semibold text-slate-800">{title}</p>
        <p className="text-[10px] text-slate-400">{time}</p>
        {detail && (
          <p className="text-[11px] text-slate-500 bg-slate-50/80 border border-slate-100/50 p-2 rounded-lg font-mono">
            {detail}
          </p>
        )}
      </div>
    </div>
  );
};
