import type { ReactNode } from "react";

export type CalloutVariant = "note" | "caution" | "warning";

interface CalloutProps {
  variant: CalloutVariant;
  label: string;
  children: ReactNode;
}

export function Callout({ variant, label, children }: CalloutProps) {
  return (
    <div className={`lab-callout lab-callout--${variant}`} role="note">
      <span className="lab-callout__label">{label}</span>
      <div className="lab-callout__content">{children}</div>
    </div>
  );
}
