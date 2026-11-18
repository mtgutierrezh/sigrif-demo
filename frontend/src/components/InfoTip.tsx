import { HelpCircle } from "lucide-react";
import { useId, useState, type ReactNode } from "react";

export function InfoTip({ label, children }: { label: string; children: ReactNode }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-flex align-middle">
      <button
        type="button"
        className="inline-flex size-5 items-center justify-center rounded-full border border-iron text-ash transition-colors hover:border-surveyor hover:text-surveyor focus-visible:border-surveyor"
        aria-label={label}
        aria-expanded={open}
        aria-describedby={open ? `${id}-tip` : undefined}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((value) => !value)}
      >
        <HelpCircle size={12} strokeWidth={1.5} aria-hidden="true" />
      </button>
      {open ? (
        <span
          id={`${id}-tip`}
          role="tooltip"
          className="absolute left-0 top-7 z-[1200] w-60 border border-iron bg-obsidian p-3 font-mono text-[10px] leading-relaxed text-bone shadow-xl"
        >
          {children}
        </span>
      ) : null}
    </span>
  );
}
