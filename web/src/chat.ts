export interface ApiMessage {
  role: "user" | "assistant";
  content: string;
}

export interface Attachment {
  id: string;
  name: string;
  size: number;
  previewUrl?: string;
  file?: File;
}

export interface ChatRequest {
  message: ApiMessage;
  thread_id?: string;
}

export interface ToolResult {
  name: string;
  content: string;
}

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
}

export function readTokenUsage(value: unknown): TokenUsage | undefined {
  if (!value || typeof value !== "object") return undefined;
  const data = value as Record<string, unknown>;
  if (![data.input_tokens, data.output_tokens, data.total_tokens].every(
    (count) => typeof count === "number" && Number.isSafeInteger(count) && count >= 0,
  )) return undefined;
  return { input_tokens: data.input_tokens as number, output_tokens: data.output_tokens as number, total_tokens: data.total_tokens as number };
}

export interface Message extends ApiMessage {
  id: string;
  attachments: Attachment[];
  toolResults?: ToolResult[];
  usage?: TokenUsage;
}

let nextLocalId = 0;

// IDs only identify items in this page's memory, so they need no secure-context API.
export function createLocalId(): string {
  return `local-${++nextLocalId}`;
}

async function checked(response: Response): Promise<Response> {
  if (!response.ok) {
    throw new Error("The assistant couldn't reply. Please try again.");
  }
  return response;
}

export async function restoreThread(threadId: string, signal: AbortSignal): Promise<{ messages: (ApiMessage & { toolResults?: ToolResult[]; usage?: TokenUsage })[]; pendingPlan?: string } | null> {
  const response = await fetch(`/api/threads/${encodeURIComponent(threadId)}`, { signal });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error("Could not restore the conversation. Please reload the page.");
  const data: unknown = await response.json();
  if (!data || typeof data !== "object" || !("messages" in data) || !Array.isArray(data.messages) ||
      !data.messages.every((message: unknown) => message && typeof message === "object" &&
        "role" in message && (message.role === "user" || message.role === "assistant") &&
        "content" in message && typeof message.content === "string")) {
    throw new Error("Could not restore the conversation. Please reload the page.");
  }
  const messages = data.messages.map((message: ApiMessage & { tool_results?: unknown }) => ({
    role: message.role,
    content: message.content,
    usage: readTokenUsage(message),
    toolResults: Array.isArray(message.tool_results)
      ? message.tool_results.filter((item: unknown): item is ToolResult =>
          !!item && typeof item === "object" && "name" in item && typeof item.name === "string" &&
          "content" in item && typeof item.content === "string")
      : [],
  }));
  return { messages, ...("pending_plan" in data && typeof data.pending_plan === "string" ? { pendingPlan: data.pending_plan } : {}) };
}

export async function deleteThread(threadId: string): Promise<void> {
  const response = await fetch(`/api/threads/${encodeURIComponent(threadId)}`, { method: "DELETE" });
  if (!response.ok && response.status !== 404) throw new Error("Could not delete the previous conversation from the server.");
}

export async function sendChat(
  message: ApiMessage & { attachments?: Attachment[] },
  signal: AbortSignal,
  attachments: Attachment[] = [],
  threadId?: string,
): Promise<ChatReply> {
  if (signal.aborted) throw new DOMException("Request aborted", "AbortError");
  const serialize = async () => {
    const selected = message.attachments ?? attachments;
    const files = await Promise.all(selected.filter((attachment) => attachment.file).map(async (attachment) => {
      return serializeAttachment(attachment);
    }));
    return { role: message.role, content: files.length
      ? [{ type: "text", text: message.content }, ...files]
      : message.content };
  };
  const serialized = await serialize();
  if (signal.aborted) throw new DOMException("Request aborted", "AbortError");
  const request = { message: serialized, ...(threadId ? { thread_id: threadId } : {}) };
  const response = await checked(
    await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal,
    }),
  );
  return parseReply(await response.json());
}

export interface ChatReply {
  response: string;
  toolResults: ToolResult[];
  threadId?: string;
  usage?: TokenUsage;
  status?: "completed" | "awaiting_approval";
}

export async function decidePlan(threadId: string, feedback: string | null, signal: AbortSignal): Promise<ChatReply> {
  const action = feedback === null ? "approve" : "deny";
  const response = await checked(await fetch(`/api/threads/${encodeURIComponent(threadId)}/plan/${action}`, {
    method: "POST",
    ...(feedback === null ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: feedback }) }),
    signal,
  }));
  return parseReply(await response.json());
}

function parseReply(result: unknown): ChatReply {
  if (
    !result ||
    typeof result !== "object" ||
    !("response" in result) ||
    typeof result.response !== "string" ||
    !result.response.trim()
  ) {
    throw new Error("The assistant returned an empty or invalid reply. Please try again.");
  }
  const toolResults =
    "tool_results" in result && Array.isArray(result.tool_results)
      ? result.tool_results.filter(
          (item): item is ToolResult =>
            item && typeof item.name === "string" && typeof item.content === "string",
        )
      : [];
  const threadIdFromResponse = "thread_id" in result && typeof result.thread_id === "string"
    ? result.thread_id
    : undefined;
  const usage = readTokenUsage(result);
  const status = "status" in result && (result.status === "completed" || result.status === "awaiting_approval") ? result.status : undefined;
  return { response: result.response, toolResults, ...(threadIdFromResponse ? { threadId: threadIdFromResponse } : {}), ...(usage ? { usage } : {}), ...(status ? { status } : {}) };
}

async function serializeAttachment(attachment: Attachment) {
  const file = attachment.file!;
  if (!file.type.startsWith("text/")) throw new Error(`${attachment.name} is not a text file.`);
  if (!file.size) throw new Error(`${attachment.name} is empty.`);
  if (Math.ceil(file.size / 3) * 4 > 1024 ** 2)
    throw new Error(`${attachment.name} is too large to send (1 MB encoded limit).`);
  const dataUrl = await readFile(file);
  const base64 = dataUrl.slice(dataUrl.indexOf(",") + 1);
  try {
    const bytes = Uint8Array.from(atob(base64), (char) => char.charCodeAt(0));
    new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    throw new Error(`${attachment.name} is not valid UTF-8 text.`);
  }
  return { type: "file" as const, base64, mime_type: file.type };
}

export async function validateAttachments(attachments: Attachment[]): Promise<void> {
  await Promise.all(attachments.filter((attachment) => attachment.file).map(serializeAttachment));
}

export function readFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () =>
      typeof reader.result === "string"
        ? resolve(reader.result)
        : reject(new Error(`Could not read ${file.name}.`));
    reader.onerror = () => reject(new Error(`Could not read ${file.name}.`));
    reader.onabort = () => reject(new Error(`Could not read ${file.name}.`));
    reader.readAsDataURL(file);
  });
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
