import { Markdown } from "@astryxdesign/core";
import { Button } from "@astryxdesign/core/Button";
import { Dialog, DialogHeader } from "@astryxdesign/core/Dialog";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Text } from "@astryxdesign/core/Text";
import { TextArea } from "@astryxdesign/core/TextArea";

export function PlanDialog({ plan, feedback, setFeedback, error, isPending, submit }: {
  plan: string | null;
  feedback: string;
  setFeedback: (value: string) => void;
  error: string | null;
  isPending: boolean;
  submit: (feedback: string | null) => Promise<void>;
}) {
  return (
    <Dialog isOpen={plan !== null} onOpenChange={() => {}} purpose="required" width="min(40rem, 100%)">
      <DialogHeader title="Review implementation plan" subtitle="Accept the plan or request changes." />
      <VStack gap={4} className="plan-dialog-content">
        <Markdown className="plan-dialog-plan">{plan ?? ""}</Markdown>
        <TextArea label="Feedback" value={feedback} onChange={setFeedback} rows={3}
          placeholder="Describe what you would like to change" />
        {error && <Text role="alert">{error}</Text>}
        <HStack gap={2} hAlign="end" wrap="wrap">
          <Button label="Send feedback" variant="secondary" isDisabled={isPending || !feedback.trim()}
            onClick={() => void submit(feedback)} />
          <Button label="Accept plan" variant="primary" isDisabled={isPending}
            onClick={() => void submit(null)} />
        </HStack>
      </VStack>
    </Dialog>
  );
}
