import {
  Button,
  Form,
  FormGroup,
  FormHelperText,
  FormSelect,
  FormSelectOption,
  Grid,
  GridItem,
  TextArea,
} from "@patternfly/react-core";
import type { TripFormValues } from "../models/packmate";
import { LabSection } from "./LabShell";

interface TripFormProps {
  values: TripFormValues;
  onChange: (values: TripFormValues) => void;
  onSubmit: () => void;
  isSubmitting: boolean;
  validationError?: string | null;
}

export function TripForm({
  values,
  onChange,
  onSubmit,
  isSubmitting,
  validationError,
}: TripFormProps) {
  const updateField = <K extends keyof TripFormValues>(key: K, value: TripFormValues[K]) => {
    onChange({ ...values, [key]: value });
  };

  return (
    <Form
      className="lab-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      {validationError && (
        <div className="lab-error" role="alert" aria-live="assertive">
          <p className="lab-error__title">Validation error</p>
          <p className="lab-error__message">{validationError}</p>
        </div>
      )}

      <LabSection title="1. Trip details">
        <Grid hasGutter>
          <GridItem span={12}>
            <FormGroup label="Travel message" isRequired fieldId="travel-message">
              <TextArea
                id="travel-message"
                value={values.message}
                onChange={(_event, value) => updateField("message", value)}
                placeholder="Example: I am travelling to Rome next week with cabin baggage."
                rows={4}
                isRequired
              />
              <FormHelperText>
                Describe your destination, dates, and travel context.
              </FormHelperText>
            </FormGroup>
          </GridItem>

          <GridItem span={12} md={6}>
            <FormGroup label="Trip type" isRequired fieldId="trip-type">
              <FormSelect
                id="trip-type"
                value={values.tripType}
                onChange={(_event, value) =>
                  updateField("tripType", value as TripFormValues["tripType"])
                }
                isRequired
              >
                <FormSelectOption value="leisure" label="Leisure" />
                <FormSelectOption value="business" label="Business" />
              </FormSelect>
            </FormGroup>
          </GridItem>

          <GridItem span={12} md={6}>
            <FormGroup label="Baggage type" isRequired fieldId="baggage-type">
              <FormSelect
                id="baggage-type"
                value={values.baggageType}
                onChange={(_event, value) =>
                  updateField("baggageType", value as TripFormValues["baggageType"])
                }
                isRequired
              >
                <FormSelectOption value="" label="Select baggage type" />
                <FormSelectOption value="cabin" label="Cabin baggage" />
                <FormSelectOption value="checked" label="Checked baggage" />
                <FormSelectOption value="both" label="Cabin and checked baggage" />
              </FormSelect>
              <FormHelperText>
                Select your baggage type explicitly to validate restrictions.
              </FormHelperText>
            </FormGroup>
          </GridItem>
        </Grid>
      </LabSection>

      <Button
        className="lab-btn-primary"
        variant="primary"
        type="submit"
        isDisabled={isSubmitting}
      >
        {isSubmitting ? "Generating packing plan..." : "Generate packing plan"}
      </Button>
    </Form>
  );
}
