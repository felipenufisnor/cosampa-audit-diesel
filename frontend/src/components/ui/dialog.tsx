"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
}

/**
 * Dialog modal acessivel construido sobre o elemento HTML <dialog>. Sem
 * dependencia de Radix; foco trapping/escape ja sao nativos. Aria roles
 * herdados do elemento.
 */
export function Dialog({ open, onOpenChange, children }: DialogProps) {
  const ref = React.useRef<HTMLDialogElement>(null);

  React.useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    if (open && !dlg.open) dlg.showModal();
    if (!open && dlg.open) dlg.close();
  }, [open]);

  React.useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    const onClose = () => onOpenChange(false);
    dlg.addEventListener("close", onClose);
    return () => dlg.removeEventListener("close", onClose);
  }, [onOpenChange]);

  return (
    <dialog
      ref={ref}
      onClick={(e) => {
        if (e.target === ref.current) onOpenChange(false);
      }}
      className={cn(
        "rounded-2xl border border-app-border bg-white shadow-2xl backdrop:bg-zinc-900/45",
        "p-0 m-auto max-w-2xl w-[min(680px,92vw)] max-h-[88vh] overflow-hidden",
      )}
    >
      <div className="flex flex-col max-h-[88vh]">{children}</div>
    </dialog>
  );
}

export function DialogHeader({
  className,
  ...p
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "px-6 py-4 border-b border-zinc-100 flex items-start justify-between gap-3",
        className,
      )}
      {...p}
    />
  );
}

export function DialogTitle({
  className,
  ...p
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn("text-lg font-semibold text-zinc-950", className)} {...p} />;
}

export function DialogSubtitle({
  className,
  ...p
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-sm text-zinc-500 mt-1", className)} {...p} />;
}

export function DialogBody({
  className,
  ...p
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("px-6 py-5 overflow-y-auto flex-1 text-sm", className)}
      {...p}
    />
  );
}

export function DialogFooter({
  className,
  ...p
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "px-6 py-4 border-t border-zinc-100 bg-zinc-50/60 flex items-center justify-end gap-2",
        className,
      )}
      {...p}
    />
  );
}
