import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type MetricTone = "neutral" | "success" | "danger" | "warn" | "info";

const toneClasses: Record<
  MetricTone,
  { icon: string; value: string; rail: string }
> = {
  neutral: {
    icon: "bg-zinc-100 text-zinc-700",
    value: "text-zinc-950",
    rail: "bg-zinc-300",
  },
  success: {
    icon: "bg-emerald-50 text-brand-primary",
    value: "text-zinc-950",
    rail: "bg-brand-primary",
  },
  danger: {
    icon: "bg-red-50 text-red-700",
    value: "text-red-700",
    rail: "bg-red-500",
  },
  warn: {
    icon: "bg-amber-50 text-amber-700",
    value: "text-amber-800",
    rail: "bg-amber-400",
  },
  info: {
    icon: "bg-sky-50 text-sky-700",
    value: "text-zinc-950",
    rail: "bg-sky-500",
  },
};

interface MetricCardProps {
  label: string;
  value: string;
  hint?: string;
  icon: LucideIcon;
  tone?: MetricTone;
}

export function MetricCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "neutral",
}: MetricCardProps) {
  const classes = toneClasses[tone];
  return (
    <Card className="group relative overflow-hidden transition-all duration-150 hover:-translate-y-0.5 hover:shadow-[0_10px_28px_rgba(15,23,42,0.09)]">
      <div className={cn("absolute inset-x-0 top-0 h-1", classes.rail)} />
      <CardContent className="flex min-h-[150px] flex-col items-center justify-center px-5 py-5 text-center">
        <div className="flex flex-col items-center gap-3">
          <span
            className={cn(
              "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
              classes.icon,
            )}
            aria-hidden
          >
            <Icon className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <p className="text-[13px] font-bold uppercase tracking-[0.09em] text-zinc-500">
              {label}
            </p>
            <p
              className={cn(
                "tabular mt-3 text-3xl font-bold tracking-tight",
                classes.value,
              )}
            >
              {value}
            </p>
          </div>
        </div>
        {hint && (
          <p className="mt-3 text-center text-[16px] leading-6 text-zinc-500">{hint}</p>
        )}
      </CardContent>
    </Card>
  );
}
