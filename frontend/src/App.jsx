import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import Dashboard from "./Dashboard";

const ROUTE_LABELS = {
  deterministic: "Deterministic",
  kb_reasoned_local: "KB Reasoned",
  rag_local: "RAG Local",
  template_engine: "Template",
  web: "Web Search",
  local: "Local Model",
  groq: "Groq",
  rejected: "Rejected",
};

export default function App() {
  const [view, setView] = useState("console");
  const [prompt, setPrompt] = useState("");
  const [webSearch, setWebSearch] = useState(false);
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [copiedKey, setCopiedKey] = useState("");
  const [editingChatId, setEditingChatId] = useState(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [activeChatId, setActiveChatId] = useState(() => {
    const saved = localStorage.getItem("ecoprompt_chats");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        return parsed?.[0]?.id ?? null;
      } catch {
        return null;
      }
    }
    return null;
  });
  const [conversations, setConversations] = useState(() => {
    const saved = localStorage.getItem("ecoprompt_chats");
    return saved ? JSON.parse(saved) : [{ id: Date.now(), title: "New Chat", messages: [] }];
  });

  const abortControllerRef = useRef(null);
  const scrollRef = useRef(null);
  const copyResetRef = useRef(null);

  useEffect(() => {
    localStorage.setItem("ecoprompt_chats", JSON.stringify(conversations));
  }, [conversations]);

  useEffect(() => {
    if (activeChatId === null && conversations.length > 0) {
      setActiveChatId(conversations[0].id);
    }
  }, [conversations, activeChatId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [conversations, activeChatId, view]);

  useEffect(() => () => {
    if (copyResetRef.current) {
      clearTimeout(copyResetRef.current);
    }
  }, []);

  const activeChat = conversations.find((c) => c.id === activeChatId) || conversations[0];

  const createNewChat = () => {
    const newChat = { id: Date.now(), title: "New Chat", messages: [] };
    setConversations([newChat, ...conversations]);
    setActiveChatId(newChat.id);
    setView("console");
  };

  const deleteChat = (id, e) => {
    e.stopPropagation();
    if (conversations.length === 1) {
      setConversations([{ id: Date.now(), title: "New Chat", messages: [] }]);
    } else {
      const filtered = conversations.filter(c => c.id !== id);
      setConversations(filtered);
      if (activeChatId === id) setActiveChatId(filtered[0].id);
    }
  };

  const startRenameChat = (chat, e) => {
    e.stopPropagation();
    setEditingChatId(chat.id);
    setEditingTitle(chat.title);
  };

  const saveRenameChat = (id) => {
    const nextTitle = editingTitle.trim();
    setConversations(prev => prev.map(chat => (
      chat.id === id ? { ...chat, title: nextTitle || "New Chat" } : chat
    )));
    setEditingChatId(null);
    setEditingTitle("");
  };

  const cancelRenameChat = () => {
    setEditingChatId(null);
    setEditingTitle("");
  };

  const runPrompt = async () => {
    if (!prompt.trim() || loading) return;

    const targetChatId = activeChatId ?? activeChat?.id;
    if (!targetChatId) return;

    const userMsg = { role: "user", content: prompt };
    const initialAssistantMsg = { role: "assistant", content: "", level_used: "local", sources: [] };
    
    setConversations(prev => prev.map(c => {
      if (c.id === targetChatId) {
        const newTitle = c.messages.length === 0 ? prompt.substring(0, 20) + (prompt.length > 20 ? "..." : "") : c.title;
        return { ...c, title: newTitle, messages: [...c.messages, userMsg, initialAssistantMsg] };
      }
      return c;
    }));

    setPrompt("");
    setLoading(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const history = (conversations.find((c) => c.id === targetChatId)?.messages || []).map((m) => ({ role: m.role, content: m.content }));
      const res = await fetch("https://ecoprompt-backend-1078329158947.asia-south1.run.app/generate-stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, history, web_search: webSearch }),
        signal: controller.signal
      });

      const route = res.headers.get("X-Route") || "local";
      let sources = [];
      const sourcesHeader = res.headers.get("X-Sources");
      if (sourcesHeader) {
        try {
          sources = JSON.parse(sourcesHeader);
        } catch {
          sources = [];
        }
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let fullContent = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        fullContent += chunk;

        setConversations(prev => prev.map(c => {
          if (c.id === targetChatId) {
            const msgs = [...c.messages];
            if (msgs.length === 0 || msgs[msgs.length - 1]?.role !== "assistant") {
              return c;
            }
            const last = msgs[msgs.length - 1];
            if (last && last.role === "assistant") {
              last.content = fullContent;
              last.level_used = route;
              last.sources = sources;
            }
            return { ...c, messages: msgs };
          }
          return c;
        }));
      }
    } catch (err) {
      if (err.name !== "AbortError") console.error("Stream error:", err);
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  };

  const stopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const copyToClipboard = async (text, key) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      if (copyResetRef.current) {
        clearTimeout(copyResetRef.current);
      }
      copyResetRef.current = setTimeout(() => {
        setCopiedKey("");
      }, 1600);
    } catch (error) {
      console.error("Copy failed:", error);
    }
  };

  return (
    <div className="app">
      <div
        className={`sidebar-overlay ${sidebarOpen ? "visible" : ""}`}
        onClick={() => setSidebarOpen(false)}
      />
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <button className="sidebar-close" onClick={() => setSidebarOpen(false)}>✕</button>
        <div className="brand-block">
          <div>
            <h2 style={{ fontSize: "1.4rem", fontWeight: 800, color: "var(--secondary)" }}>EcoPrompt</h2>
          </div>
        </div>

        <button className="new-chat-btn" onClick={createNewChat}>
          + New Chat
        </button>

        <nav className="sidebar-nav main-nav">
          <button className={`nav-link ${view === "console" ? "active" : ""}`} onClick={() => setView("console")}>
            Console
          </button>
          <button className={`nav-link ${view === "dashboard" ? "active" : ""}`} onClick={() => setView("dashboard")}>
            Dashboard
          </button>
        </nav>

        <div className="chat-history-label">Chat History</div>
        <div className="chat-list">
          {conversations.map(chat => (
            <div 
              key={chat.id} 
              className={`chat-item ${activeChatId === chat.id ? 'active' : ''}`}
              onClick={() => { setActiveChatId(chat.id); setView("console"); setSidebarOpen(false); }}
            >
              {editingChatId === chat.id ? (
                <input
                  className="chat-rename-input"
                  value={editingTitle}
                  autoFocus
                  onClick={(e) => e.stopPropagation()}
                  onChange={(e) => setEditingTitle(e.target.value)}
                  onBlur={() => saveRenameChat(chat.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      saveRenameChat(chat.id);
                    }
                    if (e.key === "Escape") {
                      cancelRenameChat();
                    }
                  }}
                />
              ) : (
                <span className="chat-item-title">{chat.title}</span>
              )}
              <div className="chat-item-actions">
                <button className="icon-btn" onClick={(e) => startRenameChat(chat, e)}>✎</button>
                <button className="icon-btn" onClick={(e) => deleteChat(chat.id, e)}>✕</button>
              </div>
            </div>
          ))}
        </div>
      </aside>

      <div className="main">
        <div className="mobile-header">
          <button className="hamburger" onClick={() => setSidebarOpen(true)}>
            <span /><span /><span />
          </button>
          <span className="mobile-title">EcoPrompt</span>
        </div>
        {view === "console" && (
          <div className="console-shell">
            <div className="chat-container" ref={scrollRef}>
              {!activeChat || activeChat.messages.length === 0 ? (
                <div className="empty-state">
                  <h1>Start a conversation</h1>
                  <p>Ask a question to begin.</p>
                </div>
              ) : (
                activeChat.messages.map((msg, idx) => (
                  <div key={idx} className={`message-wrapper ${msg.role}`}>
                    <div className="bubble-header">
                      <span className="role-label">{msg.role === "user" ? "You" : "EcoPrompt"}</span>
                      {msg.role === "assistant" && msg.level_used && (
                        <span className="route-badge">{ROUTE_LABELS[msg.level_used] || msg.level_used}</span>
                      )}
                      {msg.role === "assistant" && msg.content && (
                        <button
                          type="button"
                          className="copy-chip"
                          onClick={() => copyToClipboard(msg.content, `${activeChat.id}-${idx}-message`)}
                        >
                          {copiedKey === `${activeChat.id}-${idx}-message` ? "Copied" : "Copy"}
                        </button>
                      )}
                    </div>
                    <div className={`message-bubble ${msg.role}`}>
                      {msg.role === "assistant" && !msg.content ? (
                        <div className="thinking-indicator" aria-label="EcoPrompt is thinking">
                          <span className="thinking-dot" />
                          <span className="thinking-dot" />
                          <span className="thinking-dot" />
                        </div>
                      ) : (
                        <ReactMarkdown
                          components={{
                            code({ inline, className, children }) {
                              const match = /language-(\w+)/.exec(className || "");
                              const codeText = String(children).replace(/\n$/, "");
                              const codeKey = `${activeChat.id}-${idx}-code-${codeText.slice(0, 24)}`;
                              return !inline ? (
                                <div className="code-block">
                                  <button
                                    type="button"
                                    className="code-copy-btn"
                                    onClick={() => copyToClipboard(codeText, codeKey)}
                                  >
                                    {copiedKey === codeKey ? "Copied" : "Copy code"}
                                  </button>
                                  <SyntaxHighlighter
                                    style={vscDarkPlus}
                                    language={match ? match[1] : "python"}
                                    PreTag="div"
                                  >
                                    {codeText}
                                  </SyntaxHighlighter>
                                </div>
                              ) : (
                                <code>{children}</code>
                              );
                            }
                          }}
                        >
                          {msg.content}
                        </ReactMarkdown>
                      )}
                      {msg.role === "assistant" && msg.sources?.length > 0 && (
                        <div className="sources-row">
                          {msg.sources.slice(0, 4).map((source, sourceIdx) => {
                            let hostname = source.url;
                            try {
                              hostname = new URL(source.url).hostname.replace(/^www\./, "");
                            } catch {}
                            return (
                              <a
                                key={`${source.url}-${sourceIdx}`}
                                className="source-chip"
                                href={source.url}
                                target="_blank"
                                rel="noreferrer"
                                title={source.title || hostname}
                              >
                                <span className="source-index">{sourceIdx + 1}</span>
                                <span className="source-title">{source.title || hostname}</span>
                              </a>
                            );
                          })}
                          {msg.sources.length > 4 && (
                            <span className="sources-more">+{msg.sources.length - 4} more</span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="prompt-panel-bottom">
              <div className="input-wrapper">
                <textarea
                  className="prompt-input"
                  placeholder="Message EcoPrompt..."
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      runPrompt();
                    }
                  }}
                  rows={1}
                />
                <div className="input-actions">
                  <label className="web-toggle" aria-label="Toggle web search">
                    <span className="web-toggle-label">Web</span>
                    <button
                      type="button"
                      className={`toggle-switch ${webSearch ? "on" : "off"}`}
                      aria-pressed={webSearch}
                      onClick={() => setWebSearch((value) => !value)}
                    >
                      <span className="toggle-thumb" />
                    </button>
                  </label>
                  {loading ? (
                    <button className="stop-button" onClick={stopGeneration}>Stop</button>
                  ) : (
                    <button className="send-button" onClick={runPrompt}>Send</button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
        {view === "dashboard" && <Dashboard />}
      </div>
    </div>
  );
}
                                                                                                                                                                                                                                                                                                                           
