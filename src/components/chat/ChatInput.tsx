// VIO 83 AI ORCHESTRA - Input Chat con selettore modello
import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Zap, Cloud, HardDrive, Cpu } from 'lucide-react';
import { useAppStore } from '../../stores/appStore';
import type { AIProvider } from '../../types';

// Modelli Ollama disponibili localmente (su MacBook Air M1 8GB)
// Ordinati per potenza: Llama 3.2 3B è il più potente per uso generale (MMLU 63.4)
const OLLAMA_MODELS = [
  { id: 'llama3.2:3b', name: 'Llama 3.2 3B', desc: 'Più potente — generale', ram: '~2GB' },
  { id: 'qwen2.5-coder:3b', name: 'Qwen Coder 3B', desc: 'Migliore per codice', ram: '~2GB' },
  { id: 'gemma2:2b', name: 'Gemma 2 2B', desc: 'Leggero — rapido', ram: '~1.5GB' },
];

const cloudProviders: { id: AIProvider; name: string; icon: string }[] = [
  { id: 'claude', name: 'Claude', icon: '🟠' },
  { id: 'gpt4', name: 'GPT-4', icon: '🟢' },
  { id: 'grok', name: 'Grok', icon: '🔵' },
  { id: 'mistral', name: 'Mistral', icon: '🟣' },
  { id: 'deepseek', name: 'DeepSeek', icon: '🩷' },
];

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { settings, setMode, setProvider, setOllamaModel, isStreaming } = useAppStore();
  const { mode, primaryProvider } = settings.orchestrator;
  const currentOllamaModel = settings.ollamaModel || 'llama3.2:3b';

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px';
    }
  }, [input]);

  const handleSend = () => {
    if (!input.trim() || disabled || isStreaming) return;
    onSend(input.trim());
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const currentModelInfo = OLLAMA_MODELS.find(m => m.id === currentOllamaModel);

  return (
    <div style={{
      borderTop: '1px solid var(--vio-border)',
      backgroundColor: 'var(--vio-bg-secondary)',
      padding: '12px 20px',
    }}>
      {/* Mode + Provider/Model selector */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        marginBottom: '10px',
        flexWrap: 'wrap',
      }}>
        {/* Cloud / Local toggle */}
        <button
          onClick={() => setMode(mode === 'cloud' ? 'local' : 'cloud')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '4px 12px',
            borderRadius: '20px',
            border: `1px solid ${mode === 'cloud' ? 'var(--vio-cyan)' : 'var(--vio-green)'}`,
            backgroundColor: `${mode === 'cloud' ? 'rgba(0,255,255,0.1)' : 'rgba(0,255,0,0.1)'}`,
            color: mode === 'cloud' ? 'var(--vio-cyan)' : 'var(--vio-green)',
            cursor: 'pointer',
            fontSize: '12px',
            fontWeight: 600,
          }}
        >
          {mode === 'cloud' ? <Cloud size={14} /> : <HardDrive size={14} />}
          {mode === 'cloud' ? 'Cloud' : 'Locale'}
        </button>

        {/* === LOCAL MODE: Ollama model selector === */}
        {mode === 'local' && OLLAMA_MODELS.map(model => (
          <button
            key={model.id}
            onClick={() => setOllamaModel(model.id)}
            title={`${model.desc} (${model.ram})`}
            style={{
              padding: '4px 10px',
              borderRadius: '16px',
              border: `1px solid ${currentOllamaModel === model.id ? 'var(--vio-green)' : 'var(--vio-border)'}`,
              backgroundColor: currentOllamaModel === model.id ? 'rgba(0,255,0,0.1)' : 'transparent',
              color: currentOllamaModel === model.id ? 'var(--vio-green)' : 'var(--vio-text-secondary)',
              cursor: 'pointer',
              fontSize: '11px',
              transition: 'all 0.2s',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <Cpu size={10} />
            {model.name}
          </button>
        ))}

        {mode === 'local' && (
          <span style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '11px',
            color: 'var(--vio-green-dim)',
            marginLeft: 'auto',
          }}>
            <HardDrive size={11} />
            Ollama {currentModelInfo ? `— ${currentModelInfo.ram}` : ''}
          </span>
        )}

        {/* === CLOUD MODE: Provider buttons === */}
        {mode === 'cloud' && cloudProviders.map(p => (
          <button
            key={p.id}
            onClick={() => setProvider(p.id)}
            style={{
              padding: '4px 10px',
              borderRadius: '16px',
              border: `1px solid ${primaryProvider === p.id ? 'var(--vio-green)' : 'var(--vio-border)'}`,
              backgroundColor: primaryProvider === p.id ? 'rgba(0,255,0,0.1)' : 'transparent',
              color: primaryProvider === p.id ? 'var(--vio-green)' : 'var(--vio-text-secondary)',
              cursor: 'pointer',
              fontSize: '11px',
              transition: 'all 0.2s',
            }}
          >
            {p.icon} {p.name}
          </button>
        ))}

        {/* Auto-routing indicator */}
        {mode === 'cloud' && settings.orchestrator.autoRouting && (
          <span style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '11px',
            color: 'var(--vio-magenta)',
            marginLeft: 'auto',
          }}>
            <Zap size={12} /> Auto-routing attivo
          </span>
        )}
      </div>

      {/* Input area */}
      <div style={{
        display: 'flex',
        gap: '10px',
        alignItems: 'flex-end',
      }}>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={mode === 'local'
            ? `Scrivi un messaggio... (${currentModelInfo?.name || 'Ollama'})`
            : `Scrivi un messaggio... (${cloudProviders.find(p => p.id === primaryProvider)?.name || 'Cloud'})`
          }
          disabled={disabled || isStreaming}
          rows={1}
          style={{
            flex: 1,
            resize: 'none',
            padding: '10px 16px',
            borderRadius: 'var(--vio-radius)',
            border: '1px solid var(--vio-border)',
            backgroundColor: 'var(--vio-bg-primary)',
            color: 'var(--vio-text-primary)',
            fontSize: '14px',
            fontFamily: 'var(--vio-font-sans)',
            lineHeight: '1.5',
            outline: 'none',
            transition: 'border-color 0.2s',
            maxHeight: '200px',
          }}
          onFocus={(e) => e.target.style.borderColor = 'var(--vio-green)'}
          onBlur={(e) => e.target.style.borderColor = 'var(--vio-border)'}
        />

        <button
          onClick={handleSend}
          disabled={!input.trim() || disabled || isStreaming}
          style={{
            width: '42px',
            height: '42px',
            borderRadius: 'var(--vio-radius)',
            border: 'none',
            backgroundColor: input.trim() ? 'var(--vio-green)' : 'var(--vio-bg-tertiary)',
            color: input.trim() ? '#000' : 'var(--vio-text-dim)',
            cursor: input.trim() ? 'pointer' : 'default',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'all 0.2s',
            flexShrink: 0,
          }}
        >
          {isStreaming ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
        </button>
      </div>
    </div>
  );
}
