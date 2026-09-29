import type { ReactNode } from "react";

export const LAB_STEPS = [
  { id: 1, label: "Trip details" },
  { id: 2, label: "Packing recommendations" },
  { id: 3, label: "Baggage guidance" },
] as const;

interface LabShellProps {
  children: ReactNode;
  activeStep?: number;
}

export function LabShell({ children, activeStep = 1 }: LabShellProps) {
  return (
    <div className="lab-app">
      <header className="lab-header">
        <div className="lab-header__inner">
          <div className="lab-header__brand">
            <span className="lab-header__accent" aria-hidden="true" />
            <div>
              <p className="lab-header__title">Red Hat | Packmate Lab</p>
              <p className="lab-header__subtitle">AI-powered travel preparation</p>
            </div>
          </div>
        </div>
      </header>

      <div className="lab-body">
        <nav className="lab-sidebar" aria-label="Lab steps">
          <ol className="lab-sidebar__list">
            {LAB_STEPS.map((step) => (
              <li
                key={step.id}
                className={`lab-sidebar__item${
                  step.id === activeStep ? " lab-sidebar__item--active" : ""
                }${step.id < activeStep ? " lab-sidebar__item--complete" : ""}`}
              >
                <span className="lab-sidebar__index">{step.id}</span>
                <span className="lab-sidebar__label">{step.label}</span>
              </li>
            ))}
          </ol>
        </nav>

        <main className="lab-main">{children}</main>
      </div>
    </div>
  );
}

interface LabSectionProps {
  title: string;
  children: ReactNode;
}

export function LabSection({ title, children }: LabSectionProps) {
  return (
    <section className="lab-section">
      <h2 className="lab-section__title">{title}</h2>
      {children}
    </section>
  );
}

export function LabDivider() {
  return <hr className="lab-divider" />;
}
