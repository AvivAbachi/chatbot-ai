// Adapted from the Astryx ai-chat page template (Meta Platforms, Inc. and affiliates).
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Button } from "@astryxdesign/core/Button";
import { Text } from "@astryxdesign/core/Text";
import { ChatComposer } from "@astryxdesign/core/Chat";
import { TextArea } from "@astryxdesign/core/TextArea";
import { ArrowUp, Paperclip } from "lucide-react";
import { AttachmentList } from "./AttachmentList";
import type { useChat } from "../hooks/useChat";

type Props = Omit<ReturnType<typeof useChat>, "messages" | "resetConversation">;

export function MessageComposer({
  draft,
  setDraft,
  attachments,
  isPending,
  error,
  failedHistory,
  pendingPlan,
  inputRef,
  fileInputRef,
  requestReply,
  send,
  addFiles,
  removeAttachment,
  handleKeyDown,
}: Props) {
  return (
    <VStack gap={3} className="composer-wrap">
      {error && (
        <HStack
          gap={3}
          wrap="wrap"
          vAlign="center"
          hAlign="between"
          className="request-error"
          role="alert"
        >
          <Text type="supporting">{error}</Text>
          {failedHistory && (
            <Button
              label="Try again"
              variant="secondary"
              size="sm"
              onClick={() => {
                if (failedHistory) void requestReply(failedHistory);
              }}
            />
          )}
        </HStack>
      )}
      <ChatComposer
        value={draft}
        onChange={setDraft}
        onSubmit={send}
        elevation="none"
        input={
          <VStack gap={3}>
            <AttachmentList attachments={attachments} onRemove={removeAttachment} />
            <TextArea
              ref={inputRef}
              label="Message"
              isLabelHidden
              value={draft}
              onChange={setDraft}
              placeholder="Ask anything, or think out loud…"
              rows={2}
              onKeyDown={handleKeyDown}
              controlClassName="message-input"
              containerClassName="message-field"
            />
          </VStack>
        }
        footerActions={
          <HStack gap={2} vAlign="center">
            <Button
              label="Attach text files"
              tooltip="Add text files"
              variant="ghost"
              isIconOnly
              icon={<Paperclip size={18} aria-hidden="true" />}
              onClick={() => fileInputRef.current?.click()}
            />
            <Text type="supporting" color="secondary" className="composer-label">
              A little room for your ideas
            </Text>
          </HStack>
        }
        sendButton={
          <Button
            label="Send message"
            variant="primary"
            isIconOnly
            icon={<ArrowUp size={20} aria-hidden="true" />}
            isDisabled={isPending || !!failedHistory || !!pendingPlan || !draft.trim()}
            onClick={send}
          />
        }
      />
      <input
        ref={fileInputRef}
        className="visually-hidden"
        type="file"
        multiple
        aria-label="Choose text files"
        accept="text/plain,text/csv,text/markdown,text/html,text/css,text/javascript"
        tabIndex={-1}
        onChange={(event) => addFiles(event.target.files)}
      />
      <HStack hAlign="end" gap={3} className="composer-footnote">
        <Text type="supporting" color="secondary" className="keyboard-hint">
          Enter to send · Shift + Enter for a new line
        </Text>
      </HStack>
    </VStack>
  );
}
