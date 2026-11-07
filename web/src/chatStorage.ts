import { createLocalId, readFile, readTokenUsage, type Message, type ToolResult } from "./chat";

const STORAGE_KEY = "chat-messages";
let storageVersion = 0;

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object";
}

function isToolResult(value: unknown): value is ToolResult {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    typeof value.content === "string"
  );
}

export function restoreMessages(): Message[] {
  try {
    const data: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    if (!Array.isArray(data)) return [];
    if (
      !data.every(
        (item) =>
          isRecord(item) &&
          (item.role === "user" || item.role === "assistant") &&
          typeof item.content === "string" &&
          Array.isArray(item.attachments) &&
          item.attachments.every(
            (attachment: unknown) =>
              isRecord(attachment) &&
              typeof attachment.name === "string" &&
              typeof attachment.size === "number",
          ),
      )
    )
      return [];
    return data.map((item) => ({
      id: createLocalId(),
      role: item.role,
      content: item.content,
      usage: readTokenUsage(item.usage),
      attachments: item.attachments.map(
        (attachment: { name: string; size: number; dataUrl?: string; lastModified?: number }) => {
          let file: File | undefined;
          if (typeof attachment.dataUrl === "string") {
            const match = /^data:(text\/[^;,]+);base64,(.*)$/i.exec(attachment.dataUrl);
            if (match) {
              try {
                const bytes = Uint8Array.from(atob(match[2]!), (char) => char.charCodeAt(0));
                file = new File([bytes], attachment.name, { type: match[1]!, lastModified: attachment.lastModified });
              } catch {
                // Older or corrupted entries can still retain their attachment metadata.
              }
            }
          }
          return { id: createLocalId(), name: attachment.name, size: attachment.size, file };
        },
      ),
      toolResults: Array.isArray(item.toolResults)
        ? item.toolResults.filter(isToolResult)
        : [],
    }));
  } catch {
    return [];
  }
}

export async function storeMessages(messages: Message[]): Promise<void> {
  const version = ++storageVersion;
  try {
    if (messages.length) {
      const stored = await Promise.all(messages.map(async ({ role, content, attachments, toolResults, usage }) => ({
        role,
        content,
        attachments: await Promise.all(attachments.map(async ({ name, size, file }) => ({
          name,
          size,
          ...(file?.type.startsWith("text/") ? { dataUrl: await readFile(file), lastModified: file.lastModified } : {}),
        }))),
        ...(toolResults?.length ? { toolResults } : {}),
        ...(usage ? { usage } : {}),
      })));
      if (version !== storageVersion) return;
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
      } catch {
        // Preserve the conversation when attachment contents exceed the storage quota.
        const withoutFileData = stored.map((message) => ({
          ...message,
          attachments: message.attachments.map(({ name, size }) => ({ name, size })),
        }));
        localStorage.setItem(STORAGE_KEY, JSON.stringify(withoutFileData));
      }
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // Chat remains usable if browser storage is unavailable or full.
  }
}
