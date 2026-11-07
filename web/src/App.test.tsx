import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Theme } from "@astryxdesign/core/theme";
import { neutralTheme } from "@astryxdesign/theme-neutral/built";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

function renderApp() {
  return render(
    <Theme theme={neutralTheme} mode="light">
      <App />
    </Theme>,
  );
}

describe("conversation", () => {
  beforeEach(() => {
    localStorage.clear();
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:preview"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url === "/api/chat")
          return Promise.resolve(
            new Response(JSON.stringify({ response: "Assistant reply" })),
          );
        return Promise.resolve(new Response(null, { status: 204 }));
      }),
    );
  });

  it("sends and saves messages", async () => {
    const user = userEvent.setup();
    renderApp();
    await user.type(
      screen.getByRole("textbox", { name: "Message" }),
      "Hello{Enter}",
    );
    await screen.findByText("Assistant reply");
    const options = vi
      .mocked(fetch)
      .mock.calls.find(([url]) => url === "/api/chat")?.[1];
    expect(JSON.parse(String(options?.body))).toMatchObject({
      message: { role: "user", content: "Hello" }, thread_id: expect.any(String),
    });
    expect(JSON.parse(localStorage.getItem("chat-messages")!)).toEqual([
      { role: "user", content: "Hello", attachments: [] },
      { role: "assistant", content: "Assistant reply", attachments: [] },
    ]);
  });

  it("reviews a plan, submits feedback and approves the revision", async () => {
    vi.mocked(fetch).mockImplementation(async (url) => {
      if (String(url).endsWith("/plan/deny")) return new Response(JSON.stringify({ response: "Revised plan", status: "awaiting_approval", thread_id: "thread-1" }));
      if (String(url).endsWith("/plan/approve")) return new Response(JSON.stringify({ response: "Finished code", status: "completed", thread_id: "thread-1" }));
      return new Response(JSON.stringify({ response: "Original plan", status: "awaiting_approval", thread_id: "thread-1" }));
    });
    const user = userEvent.setup();
    renderApp();
    await user.type(screen.getByRole("textbox", { name: "Message" }), "Write code{Enter}");
    expect(await screen.findByText("Original plan")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Send feedback" }) as HTMLButtonElement).disabled).toBe(true);
    await user.type(screen.getByRole("textbox", { name: "Feedback" }), "Use Python");
    await user.click(screen.getByRole("button", { name: "Send feedback" }));
    expect(await screen.findByText("Revised plan")).toBeTruthy();
    expect(JSON.parse(String(vi.mocked(fetch).mock.calls[1]?.[1]?.body))).toEqual({ message: "Use Python" });
    await user.click(screen.getByRole("button", { name: "Accept plan" }));
    expect(await screen.findByText("Finished code")).toBeTruthy();
  });

  it("restores a pending plan", async () => {
    localStorage.setItem("chat-thread", "saved-thread");
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({ messages: [{ role: "user", content: "Build it" }], pending_plan: "Saved plan" })));
    renderApp();
    expect(await screen.findByText("Saved plan")).toBeTruthy();
  });

  it("keeps feedback and the plan when submission fails", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({ response: "Plan to review", status: "awaiting_approval", thread_id: "thread-1" })))
      .mockResolvedValueOnce(new Response(null, { status: 500 }));
    const user = userEvent.setup();
    renderApp();
    await user.type(screen.getByRole("textbox", { name: "Message" }), "Write code{Enter}");
    await screen.findByText("Plan to review");
    await user.type(screen.getByRole("textbox", { name: "Feedback" }), "Use Python");
    await user.click(screen.getByRole("button", { name: "Send feedback" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect((screen.getByRole("textbox", { name: "Feedback" }) as HTMLTextAreaElement).value).toBe("Use Python");
    expect(screen.getByText("Plan to review")).toBeTruthy();
  });

  it("shows token usage from the assistant response", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({
      response: "Answer", input_tokens: 11, output_tokens: 51, total_tokens: 62,
    })));
    const user = userEvent.setup();
    renderApp();
    await user.type(screen.getByRole("textbox", { name: "Message" }), "Hello{Enter}");
    expect(await screen.findByText("Tokens: 11 input · 51 output · 62 total")).toBeTruthy();
    expect(JSON.parse(localStorage.getItem("chat-messages")!)[1].usage).toEqual({
      input_tokens: 11, output_tokens: 51, total_tokens: 62,
    });
  });

  it("uses the server conversation for later turns and resets it", async () => {
    vi.mocked(fetch).mockImplementation(async () =>
      new Response(JSON.stringify({ response: "Assistant reply", thread_id: "thread-1" })),
    );
    const user = userEvent.setup();
    renderApp();
    const input = screen.getByRole("textbox", { name: "Message" });
    await user.type(input, "First{Enter}");
    await screen.findByText("Assistant reply");
    await user.type(input, "Next{Enter}");
    await screen.findByText("Next");
    await vi.waitFor(() => expect(screen.getAllByText("Assistant reply")).toHaveLength(2));
    expect(JSON.parse(String(vi.mocked(fetch).mock.calls[1]?.[1]?.body))).toEqual({
      message: { role: "user", content: "Next" }, thread_id: "thread-1",
    });
    await user.click(screen.getByRole("button", { name: "New conversation" }));
    expect(vi.mocked(fetch).mock.calls[2]).toEqual(["/api/threads/thread-1", { method: "DELETE" }]);
    await user.type(screen.getByRole("textbox", { name: "Message" }), "Fresh{Enter}");
    await screen.findByText("Assistant reply");
    expect(JSON.parse(String(vi.mocked(fetch).mock.calls[3]?.[1]?.body))).toMatchObject({
      message: { role: "user", content: "Fresh" }, thread_id: expect.any(String),
    });
  });

  it("restores the server conversation on reload", async () => {
    localStorage.setItem("chat-thread", "saved-thread");
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({ messages: [
      { role: "user", content: "From server" },
      { role: "assistant", content: "Restored answer" },
    ] })));
    renderApp();
    expect(await screen.findByText("Restored answer")).toBeTruthy();
    expect(screen.getByText("From server")).toBeTruthy();
    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("/api/threads/saved-thread");
  });

  it("displays restored tool results even with a saved local reply", async () => {
    localStorage.setItem("chat-thread", "saved-thread");
    localStorage.setItem("chat-messages", JSON.stringify([
      { role: "assistant", content: "Answer", attachments: [] },
    ]));
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({ messages: [
      { role: "assistant", content: "Answer", tool_results: [{ name: "search", content: "Found it" }] },
    ] })));
    renderApp();
    await userEvent.setup().click(await screen.findByText("Tool result: search"));
    expect(screen.getByText("Found it")).toBeTruthy();
  });

  it("reports when a saved conversation is no longer on the server", async () => {
    localStorage.setItem("chat-thread", "missing");
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 404 }));
    renderApp();
    expect(await screen.findByText(/no longer available on the server/)).toBeTruthy();
    expect(localStorage.getItem("chat-thread")).toBeNull();
  });

  it("restores the active conversation", async () => {
    localStorage.setItem(
      "chat-messages",
      JSON.stringify([
        { role: "user", content: "Remember me", attachments: [] },
      ]),
    );
    renderApp();
    expect(await screen.findByText("Remember me")).toBeTruthy();
  });

  it("requires a new conversation before sending from legacy history", async () => {
    localStorage.setItem("chat-messages", JSON.stringify([
      { role: "user", content: "Old question", attachments: [] },
      { role: "assistant", content: "Old answer", attachments: [] },
    ]));
    const user = userEvent.setup();
    renderApp();
    expect(screen.getByText(/older version and cannot be continued/)).toBeTruthy();
    await user.type(screen.getByRole("textbox", { name: "Message" }), "Follow up{Enter}");
    expect(vi.mocked(fetch)).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "New conversation" }));
    expect(screen.queryByText("Old answer")).toBeNull();
    await user.type(screen.getByRole("textbox", { name: "Message" }), "Fresh{Enter}");
    expect(await screen.findByText("Assistant reply")).toBeTruthy();
  });

  it("shows and restores tool results", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          response: "Answer",
          tool_results: [
            { name: "rag_search_tool", content: "Found documentation" },
          ],
        }),
      ),
    );
    const user = userEvent.setup();
    const view = renderApp();
    await user.type(
      screen.getByRole("textbox", { name: "Message" }),
      "Question{Enter}",
    );
    await screen.findByText("Answer");
    await user.click(screen.getByText("Tool result: rag_search_tool"));
    expect(screen.getByText("Found documentation")).toBeTruthy();
    view.unmount();
    renderApp();
    await user.click(screen.getByText("Tool result: rag_search_tool"));
    expect(screen.getByText("Found documentation")).toBeTruthy();
  });

  it("handles malformed saved messages and clears history on reset", async () => {
    localStorage.setItem("chat-messages", "invalid json");
    const user = userEvent.setup();
    renderApp();
    await user.type(
      screen.getByRole("textbox", { name: "Message" }),
      "Hello{Enter}",
    );
    await screen.findByText("Assistant reply");
    await user.click(screen.getByRole("button", { name: "New conversation" }));
    expect(localStorage.getItem("chat-messages")).toBeNull();
  });

  it("retries without duplicating the user message", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 500 }));
    const user = userEvent.setup();
    renderApp();
    await user.type(
      screen.getByRole("textbox", { name: "Message" }),
      "Hello{Enter}",
    );
    await user.click(await screen.findByRole("button", { name: /try again/i }));
    await screen.findByText("Assistant reply");
    const options = vi.mocked(fetch).mock.calls[1]?.[1];
    expect(JSON.parse(String(options?.body))).toMatchObject({
      message: { role: "user", content: "Hello" }, thread_id: expect.any(String),
    });
    expect(screen.getAllByText("Hello")).toHaveLength(1);
  });
  it("preserves Shift+Enter and does not send during IME composition", async () => {
    const user = userEvent.setup();
    renderApp();
    const input = screen.getByRole("textbox", { name: "Message" });
    await user.type(input, "Line one{Shift>}{Enter}{/Shift}Line two");
    expect((input as HTMLTextAreaElement).value).toBe("Line one\nLine two");
    fireEvent.keyDown(input, { key: "Enter", isComposing: true });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("sends text attachments with a message", async () => {
    const user = userEvent.setup();
    const file = new File(["text"], "notes.txt", { type: "text/plain" });
    renderApp();
    const picker = screen.getByLabelText("Choose text files");
    await user.upload(picker, file);
    await user.type(
      screen.getByRole("textbox", { name: "Message" }),
      "See files{Enter}",
    );
    await screen.findByText("Assistant reply");
    const options = vi.mocked(fetch).mock.calls[0]?.[1];
    const body = JSON.parse(String(options?.body));
    expect(body.message.content).toEqual([
      { type: "text", text: "See files" },
      { type: "file", base64: "dGV4dA==", mime_type: "text/plain" },
    ]);
    expect(screen.getByText("notes.txt")).toBeTruthy();
    const conversation = screen.getByLabelText("Conversation");
    const text = conversation.textContent ?? "";
    expect(text.indexOf("See files")).toBeLessThan(text.indexOf("notes.txt"));
    expect(text.indexOf("notes.txt")).toBeLessThan(
      text.indexOf("Assistant reply"),
    );
    await user.click(screen.getByRole("button", { name: "New conversation" }));
    expect(screen.queryByText("notes.txt")).toBeNull();
  });

  it("keeps an invalid attachment in the draft so it can be removed", async () => {
    const user = userEvent.setup();
    renderApp();
    await user.upload(
      screen.getByLabelText("Choose text files"),
      new File([], "empty.txt", { type: "text/plain" }),
    );
    const input = screen.getByRole("textbox", { name: "Message" });
    await user.type(input, "See file{Enter}");
    await screen.findByText("empty.txt is empty.");
    expect((input as HTMLTextAreaElement).value).toBe("See file");
    expect(fetch).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Remove empty.txt" }));
    await user.type(input, "{Enter}");
    await screen.findByText("Assistant reply");
  });
});
