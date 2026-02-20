// VIO 83 AI ORCHESTRA - Componente Messaggio Chat
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Bot, User, CheckCircle, AlertCircle, Clock, Zap } from 'lucide-react';
import type { Message, AIProvider } from '../../types';

const providerColors: Record<AIProvider, string> = {
  claude: '#D97706',
  gpt4: '#10B981',
  grok: '#3B82F6',
  mistral: '#8B5CF6',
  deepseek: '#EC4899',
  ollama: '#00FF00',
};

const providerNames: Record<AIProvider, string> = {
  claude: 'Claude',
  gpt4: 'GPT-4',
  grok: 'Grok',
  mistral: 'Mistral',
  deepseek: 'DeepSeek',
  ollama: 'Ollama (Locale)',
};

interface ChatMessageProps {
  message: Message;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div style={{
      display: 'flex',
      gap: '12px',
      padding: '16px 20px',
      backgroundColor: isUser ? 'transparent' : 'var(--vio-bg-secondary)',
      borderBottom: '1px solid var(--vio-bg-tertiary)',
    }}>
      {/* Avatar */}
      <div style={{
        width: '32px',
        height: '32px',
        borderRadius: '50%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: isUser ? 'var(--vio-bg-tertiary)' : 'rgba(0, 255, 0, 0.1)',
        border: `1px solid ${isUser ? 'var(--vio-border)' : 'var(--vio-green-dim)'}`,
        flexShrink: 0,
      }}>
        {isUser
          ? <User size={16} color="var(--vio-text-secondary)" />
          : <Bot size={16} color="var(--vio-green)" />
        }
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Header: provider badge */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          marginBottom: '6px',
        }}>
          <span style={{
            fontSize: '13px',
            fontWeight: 600,
            color: isUser ? 'var(--vio-text-secondary)' : 'var(--vio-green)',
          }}>
            {isUser ? 'Tu' : 'VIO 83 Orchestra'}
          </span>

          {message.provider && (
            <span style={{
              fontSize: '11px',
              padding: '2px 8px',
              borderRadius: '10px',
              backgroundColor: `${providerColors[message.provider]}20`,
              color: providerColors[message.provider],
              border: `1px solid ${providerColors[message.provider]}40`,
            }}>
              {providerNames[message.provider]}
            </span>
          )}

          {message.verified && (
            <CheckCircle size={14} color="var(--vio-green)" />
          )}

          {message.qualityScore !== undefined && message.qualityScore < 0.7 && (
            <AlertCircle size={14} color="var(--vio-orange)" />
          )}
        </div>

        {/* Message body with Markdown */}
        <div style={{
          fontSize: '14px',
          lineHeight: '1.7',
          color: 'var(--vio-text-primary)',
        }}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code(props) {
                const { children, className, ...rest } = props;
                const match = /language-(\w+)/.exec(className || '');
                const inline = !match;
                return inline ? (
                  <code style={{
                    backgroundColor: 'var(--vio-bg-tertiary)',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    fontSize: '13px',
                    fontFamily: 'var(--vio-font-mono)',
                    color: 'var(--vio-cyan)',
                  }} {...rest}>
                    {children}
                  </code>
                ) : (
                  <SyntaxHighlighter
                    style={vscDarkPlus}
                    language={match[1]}
                    PreTag="div"
                    customStyle={{
                      borderRadius: '8px',
                      margin: '8px 0',
                      fontSize: '13px',
                    }}
                  >
                    {String(children).replace(/\n$/, '')}
                  </SyntaxHighlighter>
                );
              },
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>

        {/* Footer: timestamp + model info */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          marginTop: '8px',
          fontSize: '11px',
          color: 'var(--vio-text-dim)',
        }}>
          <Clock size={11} />
          {new Date(message.timestamp).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })}

          {message.model && (
            <>
              <span style={{ color: 'var(--vio-border)' }}>•</span>
              <span>{message.model}</span>
            </>
          )}

          {message.latencyMs && message.latencyMs > 0 && (
            <>
              <span style={{ color: 'var(--vio-border)' }}>•</span>
              <Zap size={11} />
              <span>{message.latencyMs < 1000 ? `${message.latencyMs}ms` : `${(message.latencyMs / 1000).toFixed(1)}s`}</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
