import { useState, useRef, useEffect } from 'react';
import { queryChat } from '../api';

const SUGGESTED_QUESTIONS = [
  'How many sales orders are there in total?',
  'Which customer has the highest total order value?',
  'Show me the top 5 products by quantity sold',
  'List all pending deliveries',
  'What is the total revenue by customer?',
  'How many invoices have been cancelled?',
];

export default function ChatPanel() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(scrollToBottom, [messages]);

  const sendMessage = async (question) => {
    if (!question.trim()) return;

    const userMsg = { role: 'user', content: question };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      // Build chat history for context
      const chatHistory = messages.slice(-6).map(m => ({
        role: m.role,
        content: m.content,
      }));

      const data = await queryChat(question, chatHistory);

      const assistantMsg = {
        role: 'assistant',
        content: data.answer,
        sql: data.sql,
        results: data.results,
        error: data.error,
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, there was an error processing your question. Please try again.',
          error: err.message,
        },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!loading) sendMessage(input);
  };

  return (
    <div className="chat-panel">
      <div className="chat-panel__header">
        <div className="chat-panel__title">
          <div className="chat-panel__title-icon">💬</div>
          <span>Query Assistant</span>
        </div>
        <div className="chat-panel__subtitle">
          Ask questions about orders, deliveries, invoices & more
        </div>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <>
            <div className="welcome-message">
              <div className="welcome-message__icon">🧠</div>
              <div className="welcome-message__title">Ask me anything</div>
              <div className="welcome-message__sub">
                I can query the SAP Order-to-Cash database using natural language.
                Try one of the suggestions below!
              </div>
            </div>
            <div className="suggested-questions">
              {SUGGESTED_QUESTIONS.map((q, i) => (
                <button
                  key={i}
                  className="suggested-question"
                  onClick={() => sendMessage(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          </>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`chat-message chat-message--${msg.role}`}>
            <div className="chat-message__bubble">
              {msg.content}
            </div>
            {msg.sql && (
              <>
                <div className="chat-message__sql-label">SQL Query</div>
                <div className="chat-message__sql">{msg.sql}</div>
              </>
            )}
            {msg.error && (
              <div className="error-msg">⚠ {msg.error}</div>
            )}
          </div>
        ))}

        {loading && (
          <div className="chat-message chat-message--assistant">
            <div className="chat-message__bubble">
              <div className="typing-indicator">
                <div className="typing-dot" />
                <div className="typing-dot" />
                <div className="typing-dot" />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-wrapper">
        <form className="chat-input" onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            className="chat-input__field"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about orders, customers, deliveries..."
            disabled={loading}
            id="chat-input"
          />
          <button
            className="chat-input__send"
            type="submit"
            disabled={loading || !input.trim()}
            id="chat-send-btn"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </form>
      </div>
    </div>
  );
}
