import React, { useState, useRef, useEffect } from "react";
import { Bot, MessageSquare, Send, Sparkles, User, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { sendChatMessage } from "@/lib/api";
import { ChatMarkdown } from "@/lib/chat-markdown";
import { cn } from "@/lib/utils";

interface Message {
  id: string;
  sender: "user" | "bot";
  text: string;
  time: string;
}

const QUICK_PROMPTS = [
  "Direct bus from Kashmere Gate to AIIMS?",
  "How much is DTC AC bus fare?",
  "Is Ashram Chowk or Ring Road jammed?",
  "What is the frequency of route 419?",
];

export function ChatbotDrawer() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "m-0",
      sender: "bot",
      text: "Namaste! I am your Delhi Bus Assistant. Ask me about DTC routes, estimated travel times, transfer points, or current traffic slowdowns.",
      time: "Now",
    },
  ]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (open) scrollToBottom();
  }, [messages, open]);

  const handleSend = async (textToSend?: string) => {
    const query = (textToSend || input).trim();
    if (!query || loading) return;

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      sender: "user",
      text: query,
      time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const reply = await sendChatMessage(query);
      const botMsg: Message = {
        id: `b-${Date.now()}`,
        sender: "bot",
        text: reply,
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: `b-err-${Date.now()}`,
          sender: "bot",
          text: "I could not fetch an answer right now. Please try again in a moment.",
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Floating Launcher Button */}
      <Button
        onClick={() => setOpen(!open)}
        className="fixed bottom-32 right-4 lg:bottom-4 z-[990] size-12 rounded-full shadow-xl bg-primary text-primary-foreground hover:scale-105 transition-all p-0"
        aria-label="Open Bus Assistant"
      >
        {open ? <X className="size-5" /> : <MessageSquare className="size-5" />}
      </Button>

      {/* Floating Chat Modal */}
      {open && (
        <div className="fixed bottom-18 right-4 z-[990] flex h-[500px] w-[370px] max-w-[calc(100vw-2rem)] flex-col rounded-2xl border border-border bg-card shadow-2xl overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-200">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-border bg-muted/50 px-4 py-3">
            <div className="flex items-center gap-2">
              <div className="grid size-8 place-items-center rounded-xl bg-primary/10 text-primary">
                <Bot className="size-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold leading-none">Delhi Bus Assistant</h4>
                <span className="text-[10px] text-muted-foreground flex items-center gap-1 mt-0.5">
                  <span className="size-1.5 rounded-full bg-emerald-500 inline-block" /> DTC & Traffic AI
                </span>
              </div>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <X className="size-4" />
            </button>
          </div>

          {/* Messages list */}
          <div className="scrollbar-thin flex-1 space-y-3 overflow-y-auto p-3 text-xs">
            {messages.map((m) => (
              <div
                key={m.id}
                className={cn(
                  "flex gap-2 max-w-[85%]",
                  m.sender === "user" ? "ml-auto flex-row-reverse" : "mr-auto"
                )}
              >
                <div
                  className={cn(
                    "grid size-6 shrink-0 place-items-center rounded-full text-[10px]",
                    m.sender === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-foreground"
                  )}
                >
                  {m.sender === "user" ? <User className="size-3" /> : <Bot className="size-3" />}
                </div>
                <div>
                  <div
                    className={cn(
                      "rounded-2xl px-3 py-2 leading-relaxed",
                      m.sender === "user"
                        ? "bg-primary text-primary-foreground rounded-tr-xs"
                        : "bg-muted/80 text-foreground rounded-tl-xs border border-border/50"
                    )}
                  >
                    {m.sender === "bot" ? (
                      <ChatMarkdown text={m.text} />
                    ) : (
                      m.text
                    )}
                  </div>
                  <span className="text-[9px] text-muted-foreground mt-0.5 block px-1">
                    {m.time}
                  </span>
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex gap-2 mr-auto items-center text-muted-foreground text-[11px]">
                <Bot className="size-4 animate-bounce" />
                Thinking…
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick Prompts */}
          <div className="scrollbar-thin flex gap-1.5 overflow-x-auto border-t border-border/60 bg-muted/20 px-3 py-1.5">
            {QUICK_PROMPTS.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => handleSend(q)}
                className="shrink-0 rounded-full border border-border bg-background px-2.5 py-0.5 text-[10px] text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
              >
                {q}
              </button>
            ))}
          </div>

          {/* Input Footer */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center gap-1.5 border-t border-border p-2 bg-card"
          >
            <Input
              placeholder="Ask about DTC buses or traffic…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="h-9 text-xs"
              disabled={loading}
            />
            <Button type="submit" size="icon" className="size-9 shrink-0" disabled={loading || !input.trim()}>
              <Send className="size-3.5" />
            </Button>
          </form>
        </div>
      )}
    </>
  );
}
