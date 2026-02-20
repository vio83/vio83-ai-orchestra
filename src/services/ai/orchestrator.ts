// VIO 83 AI ORCHESTRA - AI Orchestrator Service
// Il cuore dell'app: gestisce routing, fallback, cross-check e streaming

import type { AIProvider, AIMode, AIResponse, Message } from '../../types';

// Model mapping per cloud providers
const CLOUD_MODELS: Record<string, string> = {
  claude: 'anthropic/claude-sonnet-4-20250514',
  gpt4: 'openai/gpt-4o',
  grok: 'xai/grok-2',
  mistral: 'mistral/mistral-large-latest',
  deepseek: 'deepseek/deepseek-chat',
};

const LOCAL_MODELS: Record<string, string> = {
  'qwen-coder': 'qwen2.5-coder:3b',
  'llama3': 'llama3.2:3b',
  'mistral': 'mistral:7b',
  'phi3': 'phi3:3.8b',
  'deepseek-coder': 'deepseek-coder-v2:lite',
};

// Classificazione tipo richiesta per routing intelligente
type RequestType = 'code' | 'creative' | 'analysis' | 'conversation' | 'realtime' | 'reasoning';

function classifyRequest(message: string): RequestType {
  const lower = message.toLowerCase();
  if (/\b(codice|code|funzione|function|bug|debug|api|database|sql|python|javascript|typescript|react|css|html|script|algoritmo|classe|metodo|array|json)\b/.test(lower)) return 'code';
  if (/\b(scrivi|write|storia|story|poesia|poem|creativo|creative|articolo|article|blog|racconto|romanzo|canzone)\b/.test(lower)) return 'creative';
  if (/\b(analiz|analy|dati|data|grafico|chart|statistic|csv|excel|tabella|confronta|compare)\b/.test(lower)) return 'analysis';
  if (/\b(oggi|today|attual|current|news|notizie|ultimo|latest|2026|2025|tempo reale)\b/.test(lower)) return 'realtime';
  if (/\b(spiega|explain|perch[eé]|why|come funziona|how does|ragion|reason|logic|matematica|math|teoria|filosofia)\b/.test(lower)) return 'reasoning';
  return 'conversation';
}

// Router intelligente
function routeToProvider(requestType: RequestType, mode: AIMode): AIProvider {
  if (mode === 'local') return 'ollama';
  switch (requestType) {
    case 'code': return 'claude';
    case 'creative': return 'gpt4';
    case 'realtime': return 'grok';
    case 'analysis': return 'claude';
    case 'reasoning': return 'claude';
    case 'conversation': default: return 'claude';
  }
}

// ============================================================
// SYSTEM PROMPT — importato dal modulo dedicato
// ============================================================
import { buildSystemPrompt } from './systemPrompt';

// ============================================================
// OLLAMA — Chiamata locale con streaming
// ============================================================

async function callOllama(
  messages: Array<{ role: string; content: string }>,
  model: string = 'qwen2.5-coder:3b',
  host: string = 'http://localhost:11434',
  onToken?: (token: string) => void,
): Promise<AIResponse> {
  const start = Date.now();

  // Se abbiamo callback streaming, usiamo stream: true
  if (onToken) {
    const response = await fetch(`${host}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, messages, stream: true }),
    });

    if (!response.ok) throw new Error(`Ollama error: ${response.status}`);
    if (!response.body) throw new Error('Ollama: no response body');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullContent = '';
    let totalTokens = 0;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      // Ollama manda un JSON per riga
      const lines = chunk.split('\n').filter(l => l.trim());

      for (const line of lines) {
        try {
          const data = JSON.parse(line);
          if (data.message?.content) {
            fullContent += data.message.content;
            onToken(data.message.content);
          }
          if (data.eval_count) totalTokens = (data.prompt_eval_count || 0) + data.eval_count;
        } catch { /* skip malformed JSON */ }
      }
    }

    return {
      content: fullContent,
      provider: 'ollama',
      model,
      tokensUsed: totalTokens,
      latencyMs: Date.now() - start,
    };
  }

  // Senza streaming
  const response = await fetch(`${host}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, messages, stream: false }),
  });

  if (!response.ok) throw new Error(`Ollama error: ${response.status} ${response.statusText}`);
  const data = await response.json();

  return {
    content: data.message?.content || '',
    provider: 'ollama',
    model,
    tokensUsed: (data.prompt_eval_count || 0) + (data.eval_count || 0),
    latencyMs: Date.now() - start,
  };
}

// ============================================================
// CLOUD — Chiamata API provider con streaming
// ============================================================

async function callCloud(
  messages: Array<{ role: string; content: string }>,
  provider: AIProvider,
  apiKeys: Record<string, string>,
  onToken?: (token: string) => void,
): Promise<AIResponse> {
  const start = Date.now();
  const model = CLOUD_MODELS[provider];
  if (!model) throw new Error(`Provider non supportato: ${provider}`);

  const keyMap: Record<string, string> = {
    claude: apiKeys.ANTHROPIC_API_KEY || '',
    gpt4: apiKeys.OPENAI_API_KEY || '',
    grok: apiKeys.XAI_API_KEY || '',
    mistral: apiKeys.MISTRAL_API_KEY || '',
    deepseek: apiKeys.DEEPSEEK_API_KEY || '',
  };
  const apiKey = keyMap[provider];
  if (!apiKey) throw new Error(`API key mancante per ${provider}. Configurala nelle Impostazioni.`);

  const baseUrls: Record<string, string> = {
    claude: 'https://api.anthropic.com/v1',
    gpt4: 'https://api.openai.com/v1',
    grok: 'https://api.x.ai/v1',
    mistral: 'https://api.mistral.ai/v1',
    deepseek: 'https://api.deepseek.com/v1',
  };

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${apiKey}`,
  };
  if (provider === 'claude') {
    headers['x-api-key'] = apiKey;
    headers['anthropic-version'] = '2023-06-01';
  }

  const useStream = !!onToken;
  const response = await fetch(`${baseUrls[provider]}/chat/completions`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      model: model.split('/')[1],
      messages,
      max_tokens: 4096,
      stream: useStream,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`${provider} API error: ${response.status} - ${error}`);
  }

  // Streaming
  if (useStream && response.body) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullContent = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n').filter(l => l.startsWith('data: '));

      for (const line of lines) {
        const data = line.slice(6); // remove 'data: '
        if (data === '[DONE]') break;
        try {
          const parsed = JSON.parse(data);
          const token = parsed.choices?.[0]?.delta?.content;
          if (token) {
            fullContent += token;
            onToken(token);
          }
        } catch { /* skip */ }
      }
    }

    return {
      content: fullContent,
      provider,
      model: model.split('/')[1],
      tokensUsed: 0,
      latencyMs: Date.now() - start,
    };
  }

  // Non-streaming
  const data = await response.json();
  return {
    content: data.choices?.[0]?.message?.content || '',
    provider,
    model: model.split('/')[1],
    tokensUsed: data.usage?.total_tokens || 0,
    latencyMs: Date.now() - start,
  };
}

// ============================================================
// FUNZIONE PRINCIPALE — Invia messaggio all'orchestra
// ============================================================

export async function sendToOrchestra(
  messages: Message[],
  config: {
    mode: AIMode;
    primaryProvider: AIProvider;
    fallbackProviders: AIProvider[];
    autoRouting: boolean;
    crossCheckEnabled: boolean;
    apiKeys: Record<string, string>;
    ollamaHost: string;
    ollamaModel?: string;
  },
  onToken?: (token: string) => void,
): Promise<AIResponse> {
  const lastMessage = messages[messages.length - 1];
  if (!lastMessage) throw new Error('Nessun messaggio da inviare');

  // Controlla se ci sono API keys configurate
  const hasAnyApiKey = Object.values(config.apiKeys).some(k => k && k.trim().length > 0);

  // Se siamo in cloud mode ma non ci sono API keys, forza Ollama
  const effectiveMode: AIMode = (config.mode === 'cloud' && !hasAnyApiKey) ? 'local' : config.mode;
  const effectiveProvider: AIProvider = effectiveMode === 'local' ? 'ollama' : config.primaryProvider;

  if (effectiveMode !== config.mode) {
    console.log(`[Orchestra] Nessuna API key trovata — fallback automatico a Ollama locale`);
  }

  // Routing intelligente — classifica PRIMA di costruire il prompt
  let provider = effectiveProvider;
  let requestType: RequestType = 'conversation';
  if (config.autoRouting) {
    requestType = classifyRequest(lastMessage.content);
    if (effectiveMode === 'cloud') {
      provider = routeToProvider(requestType, effectiveMode);
    }
  }
  console.log(`[Orchestra] Tipo: ${requestType} | Mode: ${effectiveMode} | Provider: ${provider}`);

  // Prepara messaggi con system prompt SPECIALIZZATO per tipo di richiesta
  const systemPrompt = buildSystemPrompt(requestType);
  const apiMessages: Array<{ role: string; content: string }> = [
    { role: 'system', content: systemPrompt },
    ...messages.map(m => ({ role: m.role, content: m.content })),
  ];

  // Tenta provider principale
  try {
    let response: AIResponse;

    if (effectiveMode === 'local' || provider === 'ollama') {
      response = await callOllama(
        apiMessages,
        config.ollamaModel || 'llama3.2:3b',
        config.ollamaHost,
        onToken,
      );
    } else {
      response = await callCloud(apiMessages, provider, config.apiKeys, onToken);
    }

    // Cross-check opzionale
    if (config.crossCheckEnabled && effectiveMode === 'cloud' && config.fallbackProviders.length > 0) {
      try {
        const checkProvider = config.fallbackProviders[0];
        const checkResponse = await callCloud(
          [
            ...apiMessages,
            { role: 'assistant', content: response.content },
            { role: 'user', content: 'Verifica se la risposta precedente è accurata. Rispondi solo con "CONFERMATO" se corretta, o spiega brevemente gli errori.' },
          ],
          checkProvider,
          config.apiKeys,
        );
        response.crossCheckResult = {
          concordance: checkResponse.content.includes('CONFERMATO'),
          secondProvider: checkProvider,
          secondResponse: checkResponse.content,
        };
      } catch (e) {
        console.warn('[Orchestra] Cross-check fallito:', e);
      }
    }

    return response;
  } catch (error) {
    // Fallback — prova sempre Ollama come ultimo tentativo
    console.warn(`[Orchestra] ${provider} fallito, tentativo fallback...`);

    // Prima prova i fallback configurati
    for (const fallback of config.fallbackProviders) {
      try {
        if (fallback === 'ollama') {
          return await callOllama(apiMessages, config.ollamaModel, config.ollamaHost, onToken);
        }
        // Solo se abbiamo API keys per questo provider
        if (hasAnyApiKey) {
          return await callCloud(apiMessages, fallback, config.apiKeys, onToken);
        }
      } catch (e) {
        console.warn(`[Orchestra] Fallback ${fallback} fallito:`, e);
      }
    }

    // Ultimo tentativo: Ollama sempre (se non già provato)
    if (provider !== 'ollama') {
      try {
        console.log('[Orchestra] Ultimo tentativo: Ollama locale');
        return await callOllama(apiMessages, config.ollamaModel || 'llama3.2:3b', config.ollamaHost, onToken);
      } catch (e) {
        console.warn('[Orchestra] Anche Ollama fallito:', e);
      }
    }

    throw new Error(`Tutti i provider hanno fallito. Errore originale: ${error}`);
  }
}

export { classifyRequest, routeToProvider, CLOUD_MODELS, LOCAL_MODELS };
