// Adapted from the Astryx ai-chat page template (Meta Platforms, Inc. and affiliates).
import { HStack } from "@astryxdesign/core/Layout";
import { Button } from "@astryxdesign/core/Button";
import { Text } from "@astryxdesign/core/Text";
import { Plus } from "lucide-react";
import { Spark } from "./Spark";

export function AppHeader({ onReset }: { onReset: () => void }) {
  return (
    <HStack as="header" hAlign="between" vAlign="center" gap={3} className="app-header">
      <HStack gap={3} vAlign="center">
        <HStack className="brand-mark" hAlign="center" vAlign="center">
          <Spark />
        </HStack>
        <Text type="label" weight="semibold" className="brand-name">
          Chatbot AI
        </Text>
        <Text type="supporting" color="secondary" className="header-caption">
          Your space to explore
        </Text>
      </HStack>
      <Button
        label="New conversation"
        variant="secondary"
        icon={<Plus size={18} aria-hidden="true" />}
        onClick={onReset}
      />
    </HStack>
  );
}
