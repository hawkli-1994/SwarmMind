"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import { Send, Upload, FolderOpen, Calendar } from "lucide-react";

interface V0ChatProps {
  conversationId?: string;
  onConversationCreated?: (id: string) => void;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  thinking?: string;
}

const AGENTS = [
  { name: "CRM Agent", ready: true },
  { name: "财务 Agent", ready: true },
  { name: "项目 Agent", ready: true },
  { name: "交付 Agent", ready: true },
  { name: "+2 待命", ready: false },
];

const QUICK_CHIPS = [
  { label: "Q3 财务报告", icon: "📊", prompt: "Q3 财务报告" },
  { label: "代码审查", icon: "🔍", prompt: "代码审查" },
  { label: "撰写邮件", icon: "✉️", prompt: "撰写邮件" },
  { label: "续费风险", icon: "⚠️", prompt: "客户续费风险分析" },
  { label: "竞品调研", icon: "🧭", prompt: "深度竞品调研" },
];

const CAPS = [
  { icon: "🔗", title: "跨系统调研", desc: "一问打通 CRM、财务与项目，答案带依据" },
  { icon: "💬", title: "可追问", desc: "不只给结论，支持逐层深挖与上下文继续" },
  { icon: "🛡️", title: "人类裁决", desc: "关键动作保留审批权，治理边界清晰" },
];

function generateId() {
  return Math.random().toString(36).substring(2, 9);
}

export function V0Chat({ conversationId, onConversationCreated }: V0ChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentConversationId, setCurrentConversationId] = useState<string | undefined>(conversationId);
  const [enableReasoning] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load messages when conversationId changes
  useEffect(() => {
    if (conversationId) {
      setCurrentConversationId(conversationId);
      loadMessages(conversationId);
    } else {
      setMessages([]);
      setCurrentConversationId(undefined);
    }
  }, [conversationId]);

  const loadMessages = async (convId: string) => {
    try {
      const res = await fetch(`/conversations/${convId}/messages`);
      if (res.ok) {
        const data = await res.json();
        setMessages(
          data.items.map((msg: { id: string; role: string; content: string }) => ({
            id: msg.id,
            role: msg.role as "user" | "assistant",
            content: msg.content,
          }))
        );
      }
    } catch (e) {
      console.error("Failed to load messages:", e);
    }
  };

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const handleSubmit = useCallback(async (prompt?: string) => {
    const text = (prompt ?? input).trim();
    if (!text || isLoading) return;

    if (!prompt) {
      setInput("");
    }
    setIsLoading(true);
    setError(null);

    const userMessage: Message = { id: generateId(), role: "user", content: text };
    setMessages((prev) => [...prev, userMessage]);

    if (currentConversationId) {
      await handleConversationSubmit(text, userMessage.id, enableReasoning);
    } else {
      try {
        const createRes = await fetch("/conversations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ goal: text }),
        });
        if (createRes.ok) {
          const newConv = await createRes.json();
          setCurrentConversationId(newConv.id);
          onConversationCreated?.(newConv.id);
          await handleConversationSubmitWithId(text, newConv.id, userMessage.id, enableReasoning);
        } else {
          throw new Error(`HTTP ${createRes.status}`);
        }
      } catch (e) {
        setIsLoading(false);
        setMessages((prev) => [
          ...prev,
          { id: generateId(), role: "assistant", content: `Error: ${e instanceof Error ? e.message : "Unknown error"}` },
        ]);
      }
    }
  }, [input, isLoading, currentConversationId, enableReasoning]);

  const handleConversationSubmit = async (text: string, _userMsgId: string, reasoning: boolean) => {
    try {
      const res = await fetch(`/conversations/${currentConversationId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: text, reasoning }),
      });
      if (res.ok) {
        const data = await res.json();
        setMessages((prev) => [
          ...prev,
          {
            id: data.assistant_message.id,
            role: "assistant" as const,
            content: data.assistant_message.content,
          },
        ]);
      } else {
        throw new Error(`HTTP ${res.status}`);
      }
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { id: generateId(), role: "assistant", content: `Error: ${e instanceof Error ? e.message : "Unknown error"}` },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleConversationSubmitWithId = async (text: string, convId: string, _userMsgId: string, reasoning: boolean) => {
    try {
      const res = await fetch(`/conversations/${convId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: text, reasoning }),
      });
      if (res.ok) {
        const data = await res.json();
        setMessages((prev) => [
          ...prev,
          {
            id: data.assistant_message.id,
            role: "assistant" as const,
            content: data.assistant_message.content,
          },
        ]);
      } else {
        throw new Error(`HTTP ${res.status}`);
      }
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { id: generateId(), role: "assistant", content: `Error: ${e instanceof Error ? e.message : "Unknown error"}` },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  const resizeTextarea = (el: HTMLTextAreaElement) => {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  };

  const fillInput = (text: string) => {
    setInput(text);
    inputRef.current?.focus();
    if (inputRef.current) resizeTextarea(inputRef.current);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Content Area */}
      <div className="flex-1 overflow-y-auto">
        <div className="flex flex-col items-center justify-center min-h-full px-6 py-8">
          {messages.length === 0 && !isLoading ? (
            <div className="w-full max-w-[520px] animate-[up_0.35s_ease_both]">
              {/* Hero Eyebrow */}
              <div className="inline-flex items-center gap-1.5 border border-border rounded-full px-2.5 py-1 mb-5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                <span className="text-[11px] font-mono text-muted-foreground tracking-wider">6 个 Agent 就绪</span>
              </div>

              {/* Title */}
              <h1 className="text-[30px] font-semibold text-foreground tracking-tight leading-tight mb-2.5">
                向 Agent 团队提问
              </h1>
              <p className="text-[13.5px] text-muted-foreground leading-relaxed mb-7 font-light">
                描述目标或问题，系统自动协调跨系统调研、聚合依据，<br />返回可追问的结构化答案。
              </p>

              {/* Agent Tags */}
              <div className="flex flex-wrap gap-1.5 justify-center mb-7">
                {AGENTS.map((agent) => (
                  <div
                    key={agent.name}
                    className="flex items-center gap-1.5 border border-border rounded-full px-2.5 py-1 text-[10.5px] font-mono text-muted-foreground hover:border-secondary hover:text-foreground transition-colors cursor-default"
                  >
                    <span className={`w-1 h-1 rounded-full ${agent.ready ? "bg-green-500" : "bg-muted-foreground"}`} />
                    {agent.name}
                  </div>
                ))}
              </div>

              {/* Quick Chips Label */}
              <p className="text-[10px] font-mono tracking-widest uppercase text-muted-foreground/50 mb-2.5 text-center">快速开始</p>

              {/* Quick Chips */}
              <div className="flex flex-wrap gap-2 justify-center mb-7">
                {QUICK_CHIPS.map((chip) => (
                  <button
                    key={chip.label}
                    onClick={() => fillInput(chip.prompt)}
                    className="inline-flex items-center gap-1.5 border border-border bg-transparent rounded-md px-3 py-1.5 text-[12.5px] text-muted-foreground hover:bg-secondary hover:border-secondary hover:text-foreground transition-colors cursor-pointer"
                  >
                    <span>{chip.icon}</span>
                    {chip.label}
                  </button>
                ))}
              </div>

              {/* Capability Cards */}
              <div className="grid grid-cols-3 gap-2 w-full mb-9 animate-[up_0.35s_0.08s_ease_both]">
                {CAPS.map((cap) => (
                  <div
                    key={cap.title}
                    className="border border-border rounded-md p-3.5 text-left bg-card hover:bg-secondary hover:border-secondary transition-colors cursor-pointer"
                  >
                    <div className="flex items-center gap-1.5 mb-1.5">
                      <span className="text-[13px]">{cap.icon}</span>
                      <span className="text-[12.5px] font-medium text-foreground">{cap.title}</span>
                    </div>
                    <p className="text-[11.5px] text-muted-foreground leading-relaxed">{cap.desc}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            /* Messages Thread */
            <div className="w-full max-w-[720px] py-4 space-y-4">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={message.role === "user" ? "flex justify-end" : "flex justify-start"}
                >
                  {message.role === "user" ? (
                    <div className="max-w-[85%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap bg-primary text-primary-foreground">
                      {message.content}
                    </div>
                  ) : (
                    <div className="max-w-[85%] rounded-2xl px-4 py-3 text-sm bg-muted text-foreground">
                      {enableReasoning && message.thinking && (
                        <details className="mb-2">
                          <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground select-none">
                            Thinking...
                          </summary>
                          <div className="mt-2 text-xs text-muted-foreground/70 whitespace-pre-wrap font-mono border-l-2 border-muted-foreground/20 pl-3">
                            {message.thinking}
                          </div>
                        </details>
                      )}
                      {message.content && (
                        <div className="prose prose-sm max-w-none dark:prose-invert">
                          <ReactMarkdown>{message.content}</ReactMarkdown>
                        </div>
                      )}
                      {!message.content && !message.thinking && (
                        <span className="animate-pulse">Thinking...</span>
                      )}
                    </div>
                  )}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </div>

      {/* Input Area - Fixed at bottom */}
      <div className="flex-shrink-0 px-5 pb-4">
        <div className="max-w-[720px] mx-auto">
          <div className="border border-border rounded-lg bg-card transition-colors focus-within:border-muted-foreground/50 focus-within:shadow-[0_0_0_3px_rgba(255,255,255,0.04)] overflow-hidden">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                resizeTextarea(e.target);
              }}
              onKeyDown={handleKeyDown}
              placeholder="描述你的目标，或直接提问…"
              className="w-full px-4 py-3.5 pb-2 bg-transparent border-none text-[13.5px] text-foreground placeholder:text-muted-foreground/50 focus:outline-none resize-none min-h-[56px] max-h-[160px] leading-relaxed font-light"
              rows={2}
              disabled={isLoading}
            />
            <div className="flex items-center px-3 py-2 gap-1 border-t border-border">
              <button className="flex items-center gap-1 text-[11.5px] text-muted-foreground hover:text-foreground hover:bg-secondary border border-transparent hover:border-border rounded px-2 py-1 transition-colors">
                <Upload className="w-3 h-3" />
                上传文件
              </button>
              <button className="flex items-center gap-1 text-[11.5px] text-muted-foreground hover:text-foreground hover:bg-secondary border border-transparent hover:border-border rounded px-2 py-1 transition-colors">
                <FolderOpen className="w-3 h-3" />
                关联项目
              </button>
              <button className="flex items-center gap-1 text-[11.5px] text-muted-foreground hover:text-foreground hover:bg-secondary border border-transparent hover:border-border rounded px-2 py-1 transition-colors">
                <Calendar className="w-3 h-3" />
                定时执行
              </button>
              <button
                onClick={() => handleSubmit()}
                disabled={!input.trim() || isLoading}
                className="ml-auto flex items-center gap-1.5 bg-primary text-primary-foreground hover:opacity-85 rounded px-3.5 py-1.5 text-[12.5px] font-medium transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
              >
                发送
                <Send className="w-3 h-3" />
              </button>
            </div>
          </div>
          <p className="text-center mt-2 text-[10px] font-mono text-muted-foreground/40 tracking-wider">
            <kbd className="font-mono text-[10px] bg-secondary border border-border rounded px-1.5 text-muted-foreground/60">Enter</kbd> 发送 &nbsp;·&nbsp; <kbd className="font-mono text-[10px] bg-secondary border border-border rounded px-1.5 text-muted-foreground/60">Shift+Enter</kbd> 换行 &nbsp;·&nbsp; <kbd className="font-mono text-[10px] bg-secondary border border-border rounded px-1.5 text-muted-foreground/60">⌘K</kbd> 快速指令
          </p>
        </div>
      </div>

      {error && (
        <div className="px-4 pb-4 text-destructive text-sm text-center">{error}</div>
      )}
    </div>
  );
}
