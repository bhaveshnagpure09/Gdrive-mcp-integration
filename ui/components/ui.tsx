"use client";
import { cn } from "@/lib/utils";
import React from "react";

export function Badge({
  children,
  variant = "default",
  className,
}: {
  children: React.ReactNode;
  variant?: "default" | "success" | "warning" | "danger" | "info" | "outline";
  className?: string;
}) {
  const variants = {
    default: "bg-slate-100 text-slate-700 border-slate-200",
    success: "bg-emerald-50 text-emerald-700 border-emerald-200",
    warning: "bg-amber-50 text-amber-700 border-amber-200",
    danger: "bg-red-50 text-red-700 border-red-200",
    info: "bg-blue-50 text-blue-700 border-blue-200",
    outline: "bg-transparent text-slate-600 border-slate-300",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  );
}

export function Button({
  children,
  variant = "primary",
  size = "md",
  className,
  loading,
  ...props
}: {
  children: React.ReactNode;
  variant?: "primary" | "secondary" | "danger" | "ghost" | "outline";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  className?: string;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const variants = {
    primary:
      "bg-indigo-600 text-white hover:bg-indigo-700 border-indigo-600 shadow-sm",
    secondary: "bg-white text-slate-700 hover:bg-slate-50 border-slate-300 shadow-sm",
    danger: "bg-red-600 text-white hover:bg-red-700 border-red-600 shadow-sm",
    ghost: "bg-transparent text-slate-600 hover:bg-slate-100 border-transparent",
    outline: "bg-transparent text-indigo-600 hover:bg-indigo-50 border-indigo-300",
  };
  const sizes = {
    sm: "px-3 py-1.5 text-sm",
    md: "px-4 py-2 text-sm",
    lg: "px-6 py-3 text-base",
  };
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg border font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed",
        variants[variant],
        sizes[size],
        className
      )}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading && (
        <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
        </svg>
      )}
      {children}
    </button>
  );
}

export function Card({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("rounded-xl border border-slate-200 bg-white shadow-sm", className)}>
      {children}
    </div>
  );
}

export function Input({
  label,
  error,
  className,
  ...props
}: {
  label?: string;
  error?: string;
  className?: string;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className="space-y-1">
      {label && (
        <label className="block text-sm font-medium text-slate-700">{label}</label>
      )}
      <input
        className={cn(
          "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 disabled:bg-slate-50",
          error && "border-red-400 focus:border-red-500 focus:ring-red-500/20",
          className
        )}
        {...props}
      />
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}

export function Textarea({
  label,
  error,
  className,
  ...props
}: {
  label?: string;
  error?: string;
  className?: string;
} & React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <div className="space-y-1">
      {label && (
        <label className="block text-sm font-medium text-slate-700">{label}</label>
      )}
      <textarea
        className={cn(
          "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 resize-y",
          error && "border-red-400",
          className
        )}
        {...props}
      />
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}

export function Select({
  label,
  error,
  className,
  children,
  ...props
}: {
  label?: string;
  error?: string;
  className?: string;
  children: React.ReactNode;
} & React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className="space-y-1">
      {label && (
        <label className="block text-sm font-medium text-slate-700">{label}</label>
      )}
      <select
        className={cn(
          "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20",
          error && "border-red-400",
          className
        )}
        {...props}
      >
        {children}
      </select>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn("animate-spin text-indigo-600", className ?? "h-6 w-6")}
      viewBox="0 0 24 24"
      fill="none"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
    </svg>
  );
}

export function Alert({
  children,
  type = "info",
  className,
}: {
  children: React.ReactNode;
  type?: "info" | "success" | "warning" | "error";
  className?: string;
}) {
  const styles = {
    info: "bg-blue-50 border-blue-200 text-blue-800",
    success: "bg-emerald-50 border-emerald-200 text-emerald-800",
    warning: "bg-amber-50 border-amber-200 text-amber-800",
    error: "bg-red-50 border-red-200 text-red-800",
  };
  return (
    <div className={cn("rounded-lg border p-4 text-sm", styles[type], className)}>
      {children}
    </div>
  );
}

export function ScoreBar({
  value,
  max = 100,
  label,
}: {
  value: number;
  max?: number;
  label?: string;
}) {
  const pct = Math.min(100, (value / max) * 100);
  const color =
    pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="space-y-1">
      {label && (
        <div className="flex justify-between text-xs text-slate-600">
          <span>{label}</span>
          <span className="font-medium">{pct.toFixed(0)}%</span>
        </div>
      )}
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className={cn("h-full rounded-full transition-all duration-700", color)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
