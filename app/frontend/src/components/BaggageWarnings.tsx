import { Callout } from "./Callout";

interface BaggageWarningsProps {
  warnings: string[];
}

export function BaggageWarnings({ warnings }: BaggageWarningsProps) {
  if (warnings.length === 0) {
    return null;
  }

  return (
    <Callout variant="caution" label="CAUTION">
      <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
        {warnings.map((warning) => (
          <li key={warning}>{warning}</li>
        ))}
      </ul>
    </Callout>
  );
}

interface WarningListProps {
  warnings: string[];
}

export function WarningList({ warnings }: WarningListProps) {
  if (warnings.length === 0) {
    return null;
  }

  return (
    <Callout variant="warning" label="WARNING">
      <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
        {warnings.map((warning) => (
          <li key={warning}>{warning}</li>
        ))}
      </ul>
    </Callout>
  );
}

interface DisclaimerProps {
  disclaimer: string;
}

export function RulesDisclaimer({ disclaimer }: DisclaimerProps) {
  return (
    <Callout variant="note" label="NOTE">
      {disclaimer}
    </Callout>
  );
}

interface ProfileConsiderationsProps {
  items: string[];
}

export function ProfileConsiderations({ items }: ProfileConsiderationsProps) {
  if (items.length === 0) {
    return null;
  }

  return (
    <ul style={{ margin: 0, paddingLeft: "1.25rem", fontSize: "0.875rem" }}>
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}
