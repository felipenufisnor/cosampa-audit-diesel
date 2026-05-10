import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-[0.06em]",
  {
    variants: {
      variant: {
        neutral: "bg-zinc-100 text-zinc-700 border-zinc-200",
        info: "bg-brand-primary-light text-brand-primary-dark border-emerald-200",
        success: "bg-emerald-100 text-emerald-800 border-emerald-300",
        warn: "bg-amber-100 text-amber-900 border-amber-300",
        danger: "bg-red-100 text-red-800 border-red-300",
        muted: "bg-zinc-100 text-zinc-700 border-zinc-300",
        duplicate: "bg-violet-50 text-violet-800 border-violet-200",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
