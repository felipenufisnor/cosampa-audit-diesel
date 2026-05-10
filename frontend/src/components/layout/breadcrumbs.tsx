import Link from "next/link";

import { cn } from "@/lib/utils";

interface BreadcrumbItem {
  label: string;
  href?: string;
}

export function Breadcrumbs({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav aria-label="Breadcrumbs" className="text-xs text-zinc-500 mb-4">
      <ol className="flex items-center gap-1.5">
        {items.map((it, i) => {
          const last = i === items.length - 1;
          return (
            <li key={`${it.label}-${i}`} className="flex items-center gap-1.5">
              {it.href && !last ? (
                <Link href={it.href} className="hover:text-zinc-900">
                  {it.label}
                </Link>
              ) : (
                <span className={cn(last && "text-zinc-900 font-medium")}>{it.label}</span>
              )}
              {!last && <span className="text-zinc-300">/</span>}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
