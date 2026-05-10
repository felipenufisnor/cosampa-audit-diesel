"use client";

import { cn } from "@/lib/utils";

export interface FilterTabOption<T extends string> {
  value: T;
  label: string;
  count?: number;
}

interface FilterTabsProps<T extends string> {
  value: T;
  options: FilterTabOption<T>[];
  onChange: (value: T) => void;
  label: string;
  compact?: boolean;
}

export function FilterTabs<T extends string>({
  value,
  options,
  onChange,
  label,
  compact,
}: FilterTabsProps<T>) {
  return (
    <div
      className="inline-flex flex-wrap items-center gap-1 rounded-xl border border-app-border bg-zinc-50 p-1"
      role="group"
      aria-label={label}
    >
      {options.map((option) => {
        const active = value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-lg font-semibold transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary/25",
              compact
                ? "px-2.5 py-1 text-[11px] uppercase tracking-[0.06em]"
                : "px-3 py-1.5 text-sm",
              active
                ? "bg-brand-primary-light text-brand-primary-dark shadow-sm"
                : "text-zinc-600 hover:bg-white hover:text-zinc-950",
            )}
          >
            {option.label}
            {option.count !== undefined && (
              <span
                className={cn(
                  "tabular rounded-full px-1.5 py-0.5 text-xs",
                  active ? "bg-white/70 text-brand-primary-dark" : "bg-white text-zinc-500",
                )}
              >
                {option.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
