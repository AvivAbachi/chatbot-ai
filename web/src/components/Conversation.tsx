// Adapted from the Astryx ai-chat page template (Meta Platforms, Inc. and affiliates).
import { Fragment } from "react";
import { HStack } from "@astryxdesign/core/Layout";
import { Text } from "@astryxdesign/core/Text";
import { ChatMessage, ChatMessageBubble, ChatMessageList } from "@astryxdesign/core/Chat";
import type { Message } from "../chat";
import { Spark } from "./Spark";
import { AttachmentList } from "./AttachmentList";
import { Markdown } from "@astryxdesign/core";

export function Conversation({ messages, isPending }: { messages: Message[]; isPending: boolean }) {
  return (
    <ChatMessageList align="top" aria-label="Conversation" className="message-list">
      {messages.map((message) => (
        <Fragment key={message.id}>
          {message.toolResults?.map((result, index) => (
            <ChatMessage key={`${result.name}-${index}`} sender="assistant">
              <ChatMessageBubble variant="ghost" name="Tool">
                <details>
                  <summary>Tool result: {result.name}</summary>
                  <Text className="message-text" dir="auto">
                    {result.content}
                  </Text>
                </details>
              </ChatMessageBubble>
            </ChatMessage>
          ))}
          {message.content && (
            <ChatMessage
              sender={message.role}
              avatar={
                message.role === "assistant" ? (
                  <HStack className="assistant-mark" hAlign="center" vAlign="center">
                    <Spark />
                  </HStack>
                ) : undefined
              }
            >
              <ChatMessageBubble
                variant={message.role === "assistant" ? "ghost" : undefined}
                name={message.role === "assistant" ? "Chatbot AI" : "You"}
              >
                <Markdown className="message-text" dir="auto">
                  {message.content}
                </Markdown>
                {message.usage && (
                  <Text type="supporting" color="secondary">
                    Tokens: {message.usage.input_tokens} input · {message.usage.output_tokens} output · {message.usage.total_tokens} total
                  </Text>
                )}
              </ChatMessageBubble>
            </ChatMessage>
          )}
          {message.attachments.map((attachment) => (
            <ChatMessage key={attachment.id} sender="user">
              <ChatMessageBubble name="File">
                <AttachmentList attachments={[attachment]} />
              </ChatMessageBubble>
            </ChatMessage>
          ))}
        </Fragment>
      ))}
      {isPending && messages.at(-1)?.role !== "assistant" && (
        <ChatMessage
          sender="assistant"
          avatar={
            <HStack className="assistant-mark" hAlign="center" vAlign="center">
              <Spark />
            </HStack>
          }
        >
          <ChatMessageBubble variant="ghost">
            <output className="thinking">Thinking…</output>
          </ChatMessageBubble>
        </ChatMessage>
      )}
    </ChatMessageList>
  );
}
