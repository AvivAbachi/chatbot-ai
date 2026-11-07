// Adapted from the Astryx ai-chat page template (Meta Platforms, Inc. and affiliates).
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Button } from "@astryxdesign/core/Button";
import { Text, Heading } from "@astryxdesign/core/Text";
import { Spark } from "./Spark";

const suggestions = [
  {
    title: "Make something clear",
    description: "Break down a complex idea",
    prompt: "Help me understand a complex idea. Ask me what I’m curious about.",
  },
  {
    title: "Find a fresh perspective",
    description: "Explore an idea together",
    prompt: "I’d like to brainstorm an idea. Help me explore it from a fresh perspective.",
  },
  {
    title: "Get a little unstuck",
    description: "Work through a problem",
    prompt: "Help me work through a problem, one step at a time. Ask me where I’m stuck.",
  },
];

export function WelcomeScreen({ onSelectPrompt }: { onSelectPrompt: (prompt: string) => void }) {
  return (
    <VStack className="welcome" gap={6} hAlign="center" vAlign="center">
      <HStack className="welcome-mark" hAlign="center" vAlign="center">
        <Spark large />
      </HStack>
      <VStack gap={3} hAlign="center">
        <Text type="supporting" color="secondary" className="eyebrow">
          A QUESTION IS A GOOD BEGINNING
        </Text>
        <Heading level={1} className="welcome-title">
          What’s on your mind?
        </Heading>
        <Text color="secondary" className="welcome-description" justify="center">
          A big idea, a small question, or a blank page.
          <br />
          Let’s see where it takes us.
        </Text>
      </VStack>
      <HStack gap={3} className="suggestions">
        {suggestions.map((suggestion, index) => (
          <Button
            key={suggestion.title}
            label={suggestion.title}
            variant="ghost"
            className="suggestion"
            onClick={() => onSelectPrompt(suggestion.prompt)}
          >
            <VStack gap={4} hAlign="start">
              <Text type="supporting" color="secondary" className="suggestion-number">
                0{index + 1}
              </Text>
              <VStack gap={1} hAlign="start">
                <Text type="label" weight="semibold">
                  {suggestion.title}
                </Text>
                <Text type="supporting" color="secondary">
                  {suggestion.description}
                </Text>
              </VStack>
            </VStack>
          </Button>
        ))}
      </HStack>
    </VStack>
  );
}
