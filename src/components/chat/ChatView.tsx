// VIO 83 AI ORCHESTRA - Vista Chat Principale con Streaming
import { useRef, useEffect, useState } from 'react';
import { Music } from 'lucide-react';
import { useAppStore } from '../../stores/appStore';
import { sendToOrchestra } from '../../services/ai/orchestrator';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import type { Message } from '../../types';

export default function ChatView() {
  const {
    conversations,
    activeConversationId,
    settings,
    isStreaming,
    createConversation,
    addMessage,
    setStreaming,
  } = useAppStore();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [streamingContent, setStreamingContent] = useState('');
  const [streamingProvider, setStreamingProvider] = useState('');
  const activeConversation = conversations.find(c => c.id === activeConversationId);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeConversation?.messages, streamingContent]);

  const handleSend = async (content: string) => {
    let convId = activeConversationId;
    if (!convId) {
      convId = createConversation();
    }

    // Aggiungi messaggio utente
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: Date.now(),
    };
    addMessage(convId, userMessage);
    setStreaming(true);
    setStreamingContent('');
    setStreamingProvider(settings.orchestrator.mode === 'local' ? 'ollama' : settings.orchestrator.primaryProvider);

    try {
      const apiKeys: Record<string, string> = {};
      settings.apiKeys.forEach(k => {
        const keyName = {
          claude: 'ANTHROPIC_API_KEY',
          gpt4: 'OPENAI_API_KEY',
          grok: 'XAI_API_KEY',
          mistral: 'MISTRAL_API_KEY',
          deepseek: 'DEEPSEEK_API_KEY',
          ollama: '',
        }[k.provider];
        if (keyName) apiKeys[keyName] = k.key;
      });

      const conv = useAppStore.getState().conversations.find(c => c.id === convId);
      const allMessages = conv?.messages || [userMessage];

      // Streaming callback — aggiorna il testo in tempo reale
      const onToken = (token: string) => {
        setStreamingContent(prev => prev + token);
      };

      const response = await sendToOrchestra(allMessages, {
        mode: settings.orchestrator.mode,
        primaryProvider: settings.orchestrator.primaryProvider,
        fallbackProviders: settings.orchestrator.fallbackProviders,
        autoRouting: settings.orchestrator.autoRouting,
        crossCheckEnabled: settings.orchestrator.crossCheckEnabled,
        apiKeys,
        ollamaHost: settings.ollamaHost,
        ollamaModel: settings.ollamaModel || 'qwen2.5-coder:3b',
      }, onToken);

      // Aggiungi risposta finale
      const aiMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: response.content,
        provider: response.provider,
        model: response.model,
        timestamp: Date.now(),
        verified: response.crossCheckResult?.concordance,
        qualityScore: response.crossCheckResult ? (response.crossCheckResult.concordance ? 1 : 0.5) : undefined,
      };
      addMessage(convId, aiMessage);

    } catch (error: any) {
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `**Errore:** ${error.message || 'Impossibile contattare il provider AI.'}\n\n${
          settings.orchestrator.mode === 'local'
            ? '**Soluzioni:**\n1. Verifica che Ollama sia attivo: `ollama serve`\n2. Verifica il modello: `ollama list`\n3. Scarica un modello: `ollama pull qwen2.5-coder:3b`'
            : '**Soluzioni:**\n1. Verifica le API keys nelle Impostazioni\n2. Controlla la connessione internet\n3. Prova a cambiare provider'
        }`,
        timestamp: Date.now(),
      };
      addMessage(convId, errorMessage);
    } finally {
      setStreaming(false);
      setStreamingContent('');
    }
  };

  // === Welcome Screen ===
  if (!activeConversation || activeConversation.messages.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', backgroundColor: 'var(--vio-bg-primary)' }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px', gap: '20px' }}>
          <div style={{
            width: '80px', height: '80px', borderRadius: '50%',
            background: 'linear-gradient(135deg, rgba(0,255,0,0.2), rgba(255,0,255,0.2))',
            border: '2px solid var(--vio-green)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Music size={36} color="var(--vio-green)" />
          </div>

          <h1 style={{
            fontSize: '28px', fontWeight: 700,
            background: 'linear-gradient(90deg, var(--vio-green), var(--vio-cyan))',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', textAlign: 'center',
          }}>
            VIO 83 AI Orchestra
          </h1>

          <p style={{ color: 'var(--vio-text-secondary)', fontSize: '14px', textAlign: 'center', maxWidth: '500px', lineHeight: '1.6' }}>
            L'orchestra AI che unisce i modelli più potenti del mondo.
            {settings.orchestrator.mode === 'cloud'
              ? ' Modalità Cloud attiva — connesso ai provider AI.'
              : ' Modalità Locale attiva — tutto gira sul tuo Mac, zero dati trasmessi.'
            }
          </p>

          <div style={{ display: 'flex', gap: '12px', marginTop: '16px', flexWrap: 'wrap', justifyContent: 'center' }}>
            {['Scrivi codice Python', 'Analizza questi dati', 'Spiega la meccanica quantistica', 'Crea una REST API'].map((suggestion, i) => (
              <button key={i} onClick={() => handleSend(suggestion)}
                style={{
                  padding: '8px 16px', borderRadius: '20px',
                  border: '1px solid var(--vio-border)', backgroundColor: 'transparent',
                  color: 'var(--vio-text-secondary)', fontSize: '13px', cursor: 'pointer', transition: 'all 0.2s',
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--vio-green)'; e.currentTarget.style.color = 'var(--vio-green)'; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--vio-border)'; e.currentTarget.style.color = 'var(--vio-text-secondary)'; }}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
        <ChatInput onSend={handleSend} />
      </div>
    );
  }

  // === Chat con messaggi ===
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', backgroundColor: 'var(--vio-bg-primary)' }}>
      <div style={{ flex: 1, overflowY: 'auto', paddingBottom: '20px' }}>
        {activeConversation.messages.map(msg => (
          <ChatMessage key={msg.id} message={msg} />
        ))}

        {/* Streaming in tempo reale */}
        {isStreaming && streamingContent && (
          <ChatMessage
            message={{
              id: 'streaming',
              role: 'assistant',
              content: streamingContent,
              provider: streamingProvider as any,
              timestamp: Date.now(),
            }}
          />
        )}

        {/* Indicatore "sta scrivendo" */}
        {isStreaming && !streamingContent && (
          <div style={{
            display: 'flex', gap: '12px', padding: '16px 20px',
            backgroundColor: 'var(--vio-bg-secondary)',
          }}>
            <div style={{
              width: '32px', height: '32px', borderRadius: '50%',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              backgroundColor: 'rgba(0,255,0,0.1)', border: '1px solid var(--vio-green-dim)',
            }}>
              <Music size={16} color="var(--vio-green)" />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ color: 'var(--vio-green)', fontSize: '13px' }}>L'orchestra sta elaborando</span>
              <span style={{ color: 'var(--vio-green)', animation: 'pulse 1.5s infinite' }}>...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>
      <ChatInput onSend={handleSend} />
    </div>
  );
}
