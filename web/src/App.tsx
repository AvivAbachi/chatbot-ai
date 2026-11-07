import { ChatLayout } from "@astryxdesign/core/Chat";
import { VStack } from "@astryxdesign/core/Layout";
import { AppHeader } from "./components/AppHeader";
import { Conversation } from "./components/Conversation";
import { MessageComposer } from "./components/MessageComposer";
import { WelcomeScreen } from "./components/WelcomeScreen";
import { useChat } from "./hooks/useChat";
import { PlanDialog } from "./components/PlanDialog";

export default function App() {
  const chat = useChat();
  return (
    <VStack className="app-shell">
      <AppHeader onReset={chat.resetConversation} />
      <VStack as="main" className="chat-column" aria-label="Chatbot">
        <ChatLayout
          className="chat-layout"
          density="spacious"
          composer={<MessageComposer {...chat} />}
        >
          {chat.messages.length === 0 ? (
            <WelcomeScreen
              onSelectPrompt={(prompt) => {
                chat.setDraft(prompt);
                chat.inputRef.current?.focus();
              }}
            />
          ) : (
            <Conversation messages={chat.messages} isPending={chat.isPending} />
          )}
        </ChatLayout>
      </VStack>
      <PlanDialog plan={chat.pendingPlan} feedback={chat.planFeedback} setFeedback={chat.setPlanFeedback}
        error={chat.planError} isPending={chat.isPending} submit={chat.submitPlan} />
    </VStack>
  );
}
