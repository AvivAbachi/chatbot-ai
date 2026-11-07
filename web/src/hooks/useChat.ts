import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import {
  createLocalId,
  decidePlan,
  deleteThread,
  restoreThread,
  sendChat,
  validateAttachments,
  type Attachment,
  type Message,
} from "../chat";
import { restoreMessages, storeMessages } from "../chatStorage";

export function useChat() {
  const [messages, setMessages] = useState<Message[]>(restoreMessages);
  const [draft, setDraft] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [isPending, setIsPending] = useState(false);
  const [restoreBlocked, setRestoreBlocked] = useState(
    () => !localStorage.getItem("chat-thread") && messages.length > 0,
  );
  const [error, setError] = useState<string | null>(() =>
    !localStorage.getItem("chat-thread") && messages.length > 0
      ? "This saved conversation was created with an older version and cannot be continued. Start a new conversation to continue."
      : null,
  );
  const [failedHistory, setFailedHistory] = useState<Message[] | null>(null);
  const [pendingPlan, setPendingPlan] = useState<string | null>(null);
  const [planFeedback, setPlanFeedback] = useState("");
  const [planError, setPlanError] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const requestRef = useRef<AbortController | null>(null);
  const threadRef = useRef<string | undefined>(
    localStorage.getItem("chat-thread") ?? undefined,
  );
  const previewUrls = useRef(new Set<string>());
  useEffect(() => {
    const threadId = threadRef.current;
    if (!threadId) return;
    const controller = new AbortController();
    setIsPending(true);
    restoreThread(threadId, controller.signal)
      .then((restored) => {
        if (controller.signal.aborted || threadRef.current !== threadId) return;
        if (restored === null) {
          threadRef.current = undefined;
          localStorage.removeItem("chat-thread");
          setRestoreBlocked(true);
          setError(
            "The previous conversation is no longer available on the server. Start a new conversation to continue.",
          );
          return;
        }
        setPendingPlan(restored.pendingPlan ?? null);
        setMessages((current) =>
          restored.messages.map((message, index) => {
            const saved = current[index];
            if (
              saved?.role === message.role &&
              (saved.content === message.content ||
                (saved.attachments.length > 0 &&
                  message.content.startsWith(saved.content + "\n\n")))
            )
              return {
                ...saved,
                usage: message.usage ?? saved.usage,
                toolResults: message.toolResults?.length
                  ? message.toolResults
                  : saved.toolResults,
              };
            return { ...message, id: createLocalId(), attachments: [] };
          }),
        );
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setRestoreBlocked(true);
          setError(
            "Could not restore the conversation. Please reload the page.",
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsPending(false);
      });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    storeMessages(messages);
  }, [messages]);

  useEffect(() => {
    const abortRequest = () => {
      requestRef.current?.abort();
      requestRef.current = null;
    };
    const onPageHide = () => {
      abortRequest();
      setIsPending(false);
    };
    const urls = previewUrls.current;
    window.addEventListener("pagehide", onPageHide);
    return () => {
      window.removeEventListener("pagehide", onPageHide);
      abortRequest();
      urls.forEach((url) => URL.revokeObjectURL(url));
      urls.clear();
    };
  }, []);

  async function requestReply(history: Message[]) {
    if (requestRef.current) return;
    const controller = new AbortController();
    requestRef.current = controller;
    setIsPending(true);
    setError(null);
    setFailedHistory(null);
    const replyId = createLocalId();
    try {
      const message = history.at(-1);
      if (!message?.content.trim())
        throw new Error("A text message is required.");
      if (!threadRef.current) {
        threadRef.current = crypto.randomUUID();
        localStorage.setItem("chat-thread", threadRef.current);
      }
      const reply = await sendChat(
        message,
        controller.signal,
        history.at(-1)?.attachments,
        threadRef.current,
      );
      if (requestRef.current !== controller || controller.signal.aborted)
        return;
      if (reply.threadId) {
        threadRef.current = reply.threadId;
        localStorage.setItem("chat-thread", reply.threadId);
      }
      if (reply.status === "awaiting_approval") {
        setPendingPlan(reply.response);
        return;
      }
      setMessages((current) => [
        ...current,
        {
          id: replyId,
          role: "assistant",
          content: reply.response,
          toolResults: reply.toolResults,
          usage: reply.usage,
          attachments: [],
        },
      ]);
    } catch (cause) {
      if (requestRef.current !== controller || controller.signal.aborted)
        return;
      setMessages((current) =>
        current.filter((message) => message.id !== replyId),
      );
      setError(
        cause instanceof Error
          ? cause.message
          : "Something went wrong. Please try again.",
      );
      setFailedHistory(history);
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null;
        setIsPending(false);
      }
    }
  }

  async function send() {
    const content = draft.trim();
    if (
      requestRef.current ||
      isPending ||
      restoreBlocked ||
      failedHistory ||
      pendingPlan ||
      !content
    )
      return;
    const controller = new AbortController();
    requestRef.current = controller;
    setIsPending(true);
    setError(null);
    try {
      await validateAttachments(attachments);
    } catch (cause) {
      if (requestRef.current === controller) {
        setError(
          cause instanceof Error ? cause.message : "Could not read attachment.",
        );
        requestRef.current = null;
        setIsPending(false);
      }
      return;
    }
    if (requestRef.current !== controller || controller.signal.aborted) return;
    requestRef.current = null;
    const nextMessages: Message[] = [
      ...messages,
      {
        id: createLocalId(),
        role: "user",
        content,
        attachments,
      },
    ];
    setMessages(nextMessages);
    setDraft("");
    setAttachments([]);
    void requestReply(nextMessages);
    inputRef.current?.focus();
  }

  function cancelReply() {
    requestRef.current?.abort();
    requestRef.current = null;
    setIsPending(false);
    inputRef.current?.focus();
  }

  function resetConversation() {
    const threadId = threadRef.current;
    cancelReply();
    threadRef.current = undefined;
    localStorage.removeItem("chat-thread");
    previewUrls.current.forEach((url) => URL.revokeObjectURL(url));
    previewUrls.current.clear();
    setMessages([]);
    setDraft("");
    setAttachments([]);
    setError(null);
    setFailedHistory(null);
    setPendingPlan(null);
    setPlanFeedback("");
    setPlanError(null);
    setRestoreBlocked(false);
    if (threadId)
      void deleteThread(threadId).catch((cause: unknown) => {
        setError(
          cause instanceof Error
            ? cause.message
            : "Could not delete the conversation.",
        );
      });
    if (fileInputRef.current) fileInputRef.current.value = "";
    inputRef.current?.focus();
  }

  function addFiles(files: FileList | null) {
    if (!files) return;
    const selected = Array.from(files).map((file): Attachment => {
      const previewUrl = file.type.startsWith("image/")
        ? URL.createObjectURL(file)
        : undefined;
      if (previewUrl) previewUrls.current.add(previewUrl);
      return {
        id: createLocalId(),
        name: file.name,
        size: file.size,
        file,
        previewUrl,
      };
    });
    setAttachments((current) => [...current, ...selected]);
    if (fileInputRef.current) fileInputRef.current.value = "";
    inputRef.current?.focus();
  }

  function removeAttachment(id: string) {
    const attachment = attachments.find((item) => item.id === id);
    if (attachment?.previewUrl) {
      URL.revokeObjectURL(attachment.previewUrl);
      previewUrls.current.delete(attachment.previewUrl);
    }
    setAttachments((current) => current.filter((item) => item.id !== id));
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing &&
      event.keyCode !== 229
    ) {
      event.preventDefault();
      send();
    }
  }

  async function submitPlan(feedback: string | null) {
    if (
      requestRef.current ||
      !pendingPlan ||
      !threadRef.current ||
      (feedback !== null && !feedback.trim())
    )
      return;
    const controller = new AbortController();
    requestRef.current = controller;
    setIsPending(true);
    setPlanError(null);
    try {
      const reply = await decidePlan(
        threadRef.current,
        feedback?.trim() ?? null,
        controller.signal,
      );
      if (requestRef.current !== controller || controller.signal.aborted)
        return;
      if (reply.status === "awaiting_approval") {
        setPendingPlan(reply.response);
        setPlanFeedback("");
      } else {
        setPendingPlan(null);
        setPlanFeedback("");
        setMessages((current) => [
          ...current,
          {
            id: createLocalId(),
            role: "assistant",
            content: reply.response,
            toolResults: reply.toolResults,
            usage: reply.usage,
            attachments: [],
          },
        ]);
      }
    } catch (cause) {
      if (requestRef.current === controller && !controller.signal.aborted)
        setPlanError(
          cause instanceof Error
            ? cause.message
            : "Could not submit your decision. Please try again.",
        );
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null;
        setIsPending(false);
      }
    }
  }

  return {
    messages,
    draft,
    setDraft,
    attachments,
    isPending,
    error,
    failedHistory,
    pendingPlan,
    planFeedback,
    setPlanFeedback,
    planError,
    submitPlan,
    inputRef,
    fileInputRef,
    requestReply,
    send,
    resetConversation,
    addFiles,
    removeAttachment,
    handleKeyDown,
  };
}
