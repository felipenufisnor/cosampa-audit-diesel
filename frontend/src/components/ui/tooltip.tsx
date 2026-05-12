"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactElement;
  side?: "top" | "bottom";
  className?: string;
}

export function Tooltip({
  content,
  children,
  side = "top",
  className,
}: TooltipProps) {
  const [open, setOpen] = React.useState(false);
  const tooltipId = React.useId();

  const trigger = React.cloneElement(
    children as React.ReactElement<Record<string, unknown>>,
    {
      "aria-describedby": open ? tooltipId : undefined,
      onMouseEnter: () => setOpen(true),
      onMouseLeave: () => setOpen(false),
      onFocus: () => setOpen(true),
      onBlur: () => setOpen(false),
    },
  );

  return (
    <span className="relative inline-flex">
      {trigger}
      {open && (
        <span
          id={tooltipId}
          role="tooltip"
          className={cn(
            "pointer-events-none absolute left-1/2 z-50 w-max max-w-[260px] -translate-x-1/2 rounded-md bg-zinc-900 px-2.5 py-1.5 text-xs font-medium leading-snug text-white shadow-lg",
            side === "top" ? "bottom-full mb-1.5" : "top-full mt-1.5",
            className,
          )}
        >
          {content}
        </span>
      )}
    </span>
  );
}
