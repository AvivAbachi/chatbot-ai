import { describe, expect, it, vi } from "vitest";
import { sendChat, validateAttachments } from "./chat";
import { restoreMessages, storeMessages } from "./chatStorage";

describe("client-owned chat", () => {
  it("sends one message and a thread ID", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ response: "Answer" })));
    vi.stubGlobal("fetch", fetchMock);
    const message = { role: "user" as const, content: "Next" };
    expect(await sendChat(message, new AbortController().signal, [], "thread-1")).toEqual({
      response: "Answer",
      toolResults: [],
    });
    expect(JSON.parse(fetchMock.mock.calls[0]?.[1].body)).toEqual({ message, thread_id: "thread-1" });
  });
  it("aborts a pending request", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation(
        (_url, options) =>
          new Promise((_resolve, reject) =>
            options.signal.addEventListener("abort", () =>
              reject(new DOMException("aborted", "AbortError")),
            ),
          ),
      );
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();
    const pending = sendChat(
      { role: "user", content: "Hello" },
      controller.signal,
    );
    controller.abort();
    await expect(pending).rejects.toThrow();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

it.each([
  ["empty", new File([], "empty.txt", { type: "text/plain" })],
  ["not a text file", new File(["text"], "image.png", { type: "image/png" })],
  ["too large", new File([new Uint8Array(786433)], "large.txt", { type: "text/plain" })],
  ["not valid UTF-8", new File([new Uint8Array([255])], "invalid.txt", { type: "text/plain" })],
])("rejects an attachment that is %s", async (_description, file) => {
  await expect(validateAttachments([{ id: "1", name: file.name, size: file.size, file }])).rejects.toThrow();
});

it("stores conversation metadata when attachment data exceeds the quota", async () => {
  localStorage.clear();
  const original = Storage.prototype.setItem;
  const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(function (this: Storage, key, value) {
    if (value.includes("dataUrl")) throw new DOMException("Quota exceeded", "QuotaExceededError");
    return original.call(this, key, value);
  });
  try {
    const file = new File(["text"], "notes.txt", { type: "text/plain" });
    await storeMessages([
      { id: "1", role: "user", content: "Read", attachments: [{ id: "2", name: file.name, size: file.size, file }] },
      { id: "3", role: "assistant", content: "Done", attachments: [] },
    ]);
    const restored = restoreMessages();
    expect(restored.map((message) => message.content)).toEqual(["Read", "Done"]);
    expect(restored[0]?.attachments[0]).toMatchObject({ name: "notes.txt", size: 4 });
    expect(restored[0]?.attachments[0]?.file).toBeUndefined();
  } finally {
    spy.mockRestore();
  }
});


it("restores text files and sends the selected message", async () => {
  localStorage.clear();
  const file = new File(["original text"], "notes.txt", { type: "text/plain", lastModified: 123 });
  await storeMessages([{ id: "1", role: "user", content: "Read this", attachments: [{ id: "2", name: file.name, size: file.size, file }] }]);
  const restored = restoreMessages();
  expect(restored[0]?.attachments[0]?.file?.name).toBe("notes.txt");
  expect(restored[0]?.attachments[0]?.file?.lastModified).toBe(123);
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ response: "Answer" })));
  vi.stubGlobal("fetch", fetchMock);
  await sendChat(restored[0]!, new AbortController().signal);
  const body = JSON.parse(fetchMock.mock.calls[0]![1].body);
  expect(body.message.content[1]).toEqual({ type: "file", base64: "b3JpZ2luYWwgdGV4dA==", mime_type: "text/plain" });
});
