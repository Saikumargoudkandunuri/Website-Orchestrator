import React, { useRef, useState } from 'react';
import { motion, HTMLMotionProps } from 'framer-motion';

// Helper: Mouse tracking lighting effect
export const useMouseSpotlight = () => {
  const containerRef = useRef<HTMLDivElement>(null);

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    containerRef.current.style.setProperty('--mouse-x', `${x}px`);
    containerRef.current.style.setProperty('--mouse-y', `${y}px`);
  };

  return { containerRef, handleMouseMove };
};

// Helper: 3D Mouse Tilt effect
export const useMouseTilt = () => {
  const tiltRef = useRef<HTMLDivElement>(null);
  const [glowStyle, setGlowStyle] = useState<React.CSSProperties>({ opacity: 0 });

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!tiltRef.current) return;
    const rect = tiltRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    // Tilt calculations
    const rotateX = ((y - rect.height / 2) / rect.height) * -8; // Max 8 deg
    const rotateY = ((x - rect.width / 2) / rect.width) * 8;   // Max 8 deg

    tiltRef.current.style.transform = `rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
    setGlowStyle({
      opacity: 1,
      background: `radial-gradient(220px circle at ${x}px ${y}px, rgba(255, 255, 255, 0.4), transparent 80%)`,
    });
  };

  const handleMouseLeave = () => {
    if (!tiltRef.current) return;
    tiltRef.current.style.transform = `rotateX(0deg) rotateY(0deg)`;
    setGlowStyle({ opacity: 0 });
  };

  return { tiltRef, handleMouseMove, handleMouseLeave, glowStyle };
};

// ─── GlassCard with Spotlight and Spring Elevation ───
export const GlassCard: React.FC<Omit<HTMLMotionProps<'div'>, 'children'> & { children?: React.ReactNode; hoverElevate?: boolean }> = ({ 
  children, 
  className = '', 
  hoverElevate = true, 
  ...props 
}) => {
  const { containerRef, handleMouseMove } = useMouseSpotlight();

  return (
    <motion.div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      whileHover={hoverElevate ? { 
        y: -5,
        boxShadow: "0 25px 30px -10px rgba(0, 0, 0, 0.04), 0 18px 20px -15px rgba(99, 102, 241, 0.05)",
        borderColor: "rgba(99, 102, 241, 0.3)"
      } : undefined}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className={`glass border border-white/60 p-5 shadow-sm transition-colors relative ${className}`}
      {...props}
    >
      {children}
    </motion.div>
  );
};

// ─── 3D Premium Card ───
export const GlassCard3D: React.FC<{ children?: React.ReactNode; className?: string }> = ({ children, className = '' }) => {
  const { tiltRef, handleMouseMove, handleMouseLeave, glowStyle } = useMouseTilt();

  return (
    <div className="perspective-card-wrapper">
      <div
        ref={tiltRef}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        className={`perspective-card glass border border-white/60 p-6 shadow-md bg-white/40 backdrop-blur-2xl relative ${className}`}
      >
        <div style={glowStyle} className="absolute inset-0 pointer-events-none z-10 transition-opacity duration-300 rounded-2xl" />
        <div className="relative z-20">{children}</div>
      </div>
    </div>
  );
};

// ─── GradientCard with Spotlight ───
export const GradientCard: React.FC<Omit<HTMLMotionProps<'div'>, 'children'> & { children?: React.ReactNode; hoverGlow?: boolean }> = ({
  children,
  className = '',
  hoverGlow = true,
  ...props
}) => {
  const { containerRef, handleMouseMove } = useMouseSpotlight();

  return (
    <motion.div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      whileHover={hoverGlow ? { scale: 1.015 } : undefined}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className={`relative overflow-hidden border border-white/65 p-6 shadow-md bg-gradient-to-br from-indigo-50/50 via-purple-50/40 to-pink-50/30 backdrop-blur-2xl rounded-2xl ${className}`}
      {...props}
    >
      {/* Ambient Glows */}
      <div className="absolute -right-20 -top-20 h-52 w-52 rounded-full bg-indigo-500/10 blur-3xl" />
      <div className="absolute -left-20 -bottom-20 h-52 w-52 rounded-full bg-pink-500/10 blur-3xl" />
      <div className="relative z-10">{children}</div>
    </motion.div>
  );
};

// ─── MetricCard with Glowing Gradient Ring ───
export const MetricCard: React.FC<{
  label: string;
  value: string | number;
  change?: string;
  changeType?: 'positive' | 'negative' | 'neutral';
  description?: string;
  icon?: React.ReactNode;
}> = ({ label, value, change, changeType = 'neutral', description, icon }) => {
  return (
    <GlassCard className="relative overflow-hidden group border border-white/70">
      <div className="flex justify-between items-start">
        <div className="space-y-1.5">
          <span className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest block">{label}</span>
          <h3 className="text-3xl font-black text-slate-900 tracking-tight">{value}</h3>
        </div>
        {icon && (
          <div className="p-3 bg-indigo-50/80 rounded-xl border border-indigo-100/50 text-indigo-600 transition-all duration-300 group-hover:bg-indigo-600 group-hover:text-white group-hover:scale-110 shadow-sm">
            {icon}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 mt-4">
        {change && (
          <span className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full ${
            changeType === 'positive' ? 'bg-emerald-50 text-emerald-600 border border-emerald-100' :
            changeType === 'negative' ? 'bg-rose-50 text-rose-600 border border-rose-100' :
            'bg-slate-50 text-slate-600 border border-slate-100'
          }`}>
            {change}
          </span>
        )}
        {description && <span className="text-xs text-slate-400 font-semibold">{description}</span>}
      </div>
    </GlassCard>
  );
};

// ─── AnimatedButton with Click Ripple ───
export const AnimatedButton: React.FC<Omit<HTMLMotionProps<'button'>, 'children'> & { children?: React.ReactNode; variant?: 'primary' | 'secondary' | 'ghost' | 'danger' }> = ({
  children,
  className = '',
  variant = 'secondary',
  ...props
}) => {
  const baseStyle = "btn text-xs font-bold flex items-center justify-center gap-1.5 transition-all outline-none";
  const styles = {
    primary: "btn-primary",
    secondary: "btn-secondary",
    ghost: "bg-transparent text-slate-500 hover:bg-slate-100/80 border-transparent",
    danger: "bg-rose-600 text-white border border-rose-700/50 hover:bg-rose-700 shadow-sm",
  };

  return (
    <motion.button
      whileHover={{ scale: 1.03, y: -0.5 }}
      whileTap={{ scale: 0.97 }}
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
      className={`w-full bg-white/50 border border-slate-200/80 text-slate-800 text-xs px-4 py-3 rounded-xl focus:outline-none focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-500/10 placeholder:text-slate-400 transition-all font-semibold ${className}`}
      {...props}
    />
  );
};

// ─── Glowing StatusBadge ───
export const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const s = status.toLowerCase();
  const styles: Record<string, string> = {
    approved: "bg-emerald-50 text-emerald-700 border-emerald-200/80 shadow-emerald-100/40",
    applied: "bg-emerald-50 text-emerald-700 border-emerald-200/80 shadow-emerald-100/40",
    pending: "bg-amber-50 text-amber-700 border-amber-200/80 shadow-amber-100/40",
    rejected: "bg-rose-50 text-rose-700 border-rose-200/80 shadow-rose-100/40",
    critical: "bg-rose-50 text-rose-700 border-rose-200/80 shadow-rose-100/40",
    high: "bg-rose-50 text-rose-700 border-rose-200/80 shadow-rose-100/40",
    medium: "bg-amber-50 text-amber-700 border-amber-200/80 shadow-amber-100/40",
    low: "bg-sky-50 text-sky-700 border-sky-200/80 shadow-sky-100/40",
    success: "bg-emerald-50 text-emerald-700 border-emerald-200/80 shadow-emerald-100/40",
    failed: "bg-rose-50 text-rose-700 border-rose-200/80 shadow-rose-100/40",
  };

  const currentStyle = styles[s] || "bg-slate-50 text-slate-600 border-slate-200/80";

  return (
    <span className={`inline-flex items-center px-3 py-1 rounded-full text-[10px] font-extrabold uppercase tracking-wider border shadow-sm ${currentStyle}`}>
      <span className={`h-1.5 w-1.5 rounded-full mr-1.5 ${
        s === 'approved' || s === 'applied' || s === 'success' ? 'bg-emerald-500' :
        s === 'pending' || s === 'medium' ? 'bg-amber-500' :
        s === 'rejected' || s === 'critical' || s === 'high' || s === 'failed' ? 'bg-rose-500' :
        'bg-slate-400'
      }`} />
      {status}
    </span>
  );
};

// ─── TimelineItem with Stagger Indicator ───
export const TimelineItem: React.FC<{
  title: string;
  time: string;
  detail?: string;
  type?: 'success' | 'warning' | 'error' | 'info';
}> = ({ title, time, detail, type = 'info' }) => {
  const dotColor = {
    success: 'bg-emerald-500 ring-emerald-100',
    warning: 'bg-amber-500 ring-amber-100',
    error: 'bg-rose-500 ring-rose-100',
    info: 'bg-indigo-500 ring-indigo-100'
  };

  return (
    <div className="flex gap-4 relative group pl-5">
      <div className={`h-3 w-3 rounded-full ${dotColor[type]} mt-1.5 flex-shrink-0 z-10 ring-4 shadow-sm`} />
      <div className="space-y-1 pb-5">
        <p className="text-xs font-bold text-slate-800">{title}</p>
        <p className="text-[10px] text-slate-400 font-semibold">{time}</p>
        {detail && (
          <p className="text-[11px] text-slate-500 bg-white/80 border border-slate-200/50 p-2.5 rounded-xl font-mono leading-relaxed shadow-sm">
            {detail}
          </p>
        )}
      </div>
    </div>
  );
};
