"use client";

import * as React from "react";
import { Search } from "lucide-react";

import { cn } from "@/lib/utils";

interface SearchInputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> {
  label?: string;
}

export function SearchInput({
  className,
  label = "Buscar",
  ...props
}: SearchInputProps) {
  return (
    <label className={cn("relative block", className)} aria-label={label}>
      <Search
        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400"
        aria-hidden
      />
      <input
        type="search"
        className="h-9 w-full rounded-lg border border-app-border bg-white pl-9 pr-3 text-sm text-zinc-800 shadow-sm placeholder:text-zinc-400 transition-colors focus:outline-none focus:border-brand-primary focus:ring-2 focus:ring-brand-primary/20"
        {...props}
      />
    </label>
  );
}
