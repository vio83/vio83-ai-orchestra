// VIO 83 AI ORCHESTRA - Vista Chat Principale
import { useRef, useEffect } from 'react';
import { MessageSquarePlus, Music } from 'lucide-react';
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
  const activeConversation = conversations.find(c => c.id === activeConversationId);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeConversation?.messages]);

  const handleSend = async (content: string) => {
    let convId = activeConversationId;

    // Crea nuova conversazione se necessario
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

    try {
      // Prepara API keys
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

      // Prendi tutti i messaggi della conversazione
      const conv = useAppStore.getState().conversations.find(c => c.id === convId);
      const allMessages = conv?.messages || [userMessage];

      // Invia all'orchestra
      const response = await sendToOrchestra(allMessages, {
        mode: settings.orchestrator.mode,
        primaryProvider: settings.orchestrator.primaryProvider,
        fallbackProviders: settings.orchestrator.fallbackProviders,
        autoRouting: settings.orchestrator.autoRouting,
        crossCheckEnabled: settings.orchestrator.crossCheckEnabled,
        apiKeys,
        ollamaHost: settings.ollamaHost,
      });

      // Aggiungi risposta AI
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
      // Messaggio di errore
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `**Errore:** ${error.message || 'Impossibile contattare il provider AI.'}\n\n${
          settings.orchestrator.mode === 'local'
            ? 'Verifica che Ollama sia in esecuzione (`ollama serve` nel terminale).'
            : 'Verifica le tue API keys nelle impostazioni.'
        }`,
        timestamp: Date.now(),
      };
      addMessage(convId, errorMessage);
    } finally {
      setStreaming(false);
    }
  };

  // Schermata di benvenuto quando non c'è conversazione
  if (!activeConversation || activeConversation.messages.length === 0) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        backgroundColor: 'var(--vio-bg-primary)',
      }}>
        {/* Welcome screen */}
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '40px',
          gap: '20px',
        }}>
          <div style={{
            width: '80px',
            height: '80px',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, rgba(0,255,0,0.2), rgba(255,0,255,0.2))',
            border: '2px solid var(--vio-green)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <Music size={36} color="var(--vio-green)" />
          </div>

          <h1 style={{
            fontSize: '28px',
            fontWeight: 700,
            background: 'linear-gradient(90deg, var(--vio-green), var(--vio-cyan))',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            textAlign: 'center',
          }}>
            VIO 83 AI Orchestra
          </h1>

          <p style={{
            color: 'var(--vio-text-secondary)',
            fontSize: '14px',
            textAlign: 'center',
            maxWidth: '500px',
            lineHeight: '1.6',
          }}>
            L'orchestra AI che unisce i modelli più potenti del mondo.
            {settings.orchestrator.mode === 'cloud'
              ? ' Modalità Cloud attiva — connesso ai provider AI.'
              : ' Modalità Locale attiva — tutto gira sul tuo Mac, zero dati trasmessi.'
            }
          </p>

          <div style={{
            display: 'flex',
            gap: '12px',
            marginTop: '16px',
            flexWrap: 'wrap',
            justifyContent: 'center',
          }}>
            {['Scrivi codice Python', 'Analizza questi dati', 'Spiega la meccanica quantistica', 'Crea una REST API'].map((suggestion, i) => (
              <button
                key={i}
                onClick={() => handleSend(suggestion)}
                style={{
                  padding: '8px 16px',
                  borderRadius: '20px',
                  border: '1px solid var(--vio-border)',
                  backgroundColor: 'transparent',
                  color: 'var(--vio-text-secondary)',
                  fontSize: '13px',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--vio-green)';
                  e.currentTarget.style.color = 'var(--vio-green)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--vio-border)';
                  e.currentTarget.style.color = 'var(--vio-text-secondary)';
                }}
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

  // Vista conversazione con messaggi
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      backgroundColor: 'var(--vio-bg-primary)',
    }}>
      {/* Messages area */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        paddingBottom: '20px',
      }}>
        {activeConversation.messages.map(msg => (
          <ChatMessage key={msg.id} message={msg} />
        ))}

        {isStreaming && (
          <div style={{
            display: 'flex',
            gap: '12px',
            padding: '16px 20px',
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
              <span className="dots-loading" style={{ color: 'var(--vio-green)' }}>...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <ChatInput onSend={handleSend} />
    </div>
  );
}
