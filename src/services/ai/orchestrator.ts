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

  const apiMessages = messages.map(m => ({ role: m.role, content: m.content }));

  // Routing intelligente
  let provider = config.primaryProvider;
  let requestType: RequestType = 'conversation';
  if (config.autoRouting && config.mode === 'cloud') {
    requestType = classifyRequest(lastMessage.content);
    provider = routeToProvider(requestType, config.mode);
  } else if (config.autoRouting && config.mode === 'local') {
    requestType = classifyRequest(lastMessage.content);
  }
  console.log(`[Orchestra] Tipo: ${requestType} | Mode: ${config.mode} | Provider: ${provider}`);

  // Tenta provider principale
  try {
    let response: AIResponse;

    if (config.mode === 'local' || provider === 'ollama') {
      response = await callOllama(
        apiMessages,
        config.ollamaModel || 'qwen2.5-coder:3b',
        config.ollamaHost,
        onToken,
      );
    } else {
      response = await callCloud(apiMessages, provider, config.apiKeys, onToken);
    }

    // Cross-check opzionale
    if (config.crossCheckEnabled && config.mode === 'cloud' && config.fallbackProviders.length > 0) {
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
    // Fallback
    console.warn(`[Orchestra] ${provider} fallito, tentativo fallback...`);
    for (const fallback of config.fallbackProviders) {
      try {
        if (fallback === 'ollama') {
          return await callOllama(apiMessages, config.ollamaModel, config.ollamaHost, onToken);
        }
        return await callCloud(apiMessages, fallback, config.apiKeys, onToken);
      } catch (e) {
        console.warn(`[Orchestra] Fallback ${fallback} fallito:`, e);
      }
    }
    throw new Error(`Tutti i provider hanno fallito. Errore originale: ${error}`);
  }
}

export { classifyRequest, routeToProvider, CLOUD_MODELS, LOCAL_MODELS };
