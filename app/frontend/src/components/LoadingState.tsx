import { Spinner } from "@patternfly/react-core";

interface LoadingStateProps {
  message?: string;
}

export function LoadingState({ message = "Analyzing your trip..." }: LoadingStateProps) {
  return (
    <div className="lab-loading" role="status" aria-live="polite">
      <Spinner size="md" aria-label="Loading" />
      <span>{message}</span>
    </div>
  );
}

interface ErrorStateProps {
  title: string;
  message: string;
}

export function ErrorState({ title, message }: ErrorStateProps) {
  return (
    <div className="lab-error" role="alert">
      <p className="lab-error__title">{title}</p>
      <p className="lab-error__message">{message}</p>
    </div>
  );
}
