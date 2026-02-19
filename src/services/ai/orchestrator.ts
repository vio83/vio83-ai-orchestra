// VIO 83 AI ORCHESTRA - AI Orchestrator Service
// Il cuore dell'app: gestisce routing, fallback, e cross-check

import type { AIProvider, AIMode, AIResponse, Message } from '../../types';

// Model mapping per LiteLLM (formato provider/model)
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

  // Codice
  if (/\b(codice|code|funzione|function|bug|debug|api|database|sql|python|javascript|typescript|react|css|html)\b/.test(lower)) {
    return 'code';
  }
  // Creativo
  if (/\b(scrivi|write|storia|story|poesia|poem|creativo|creative|articolo|article|blog)\b/.test(lower)) {
    return 'creative';
  }
  // Analisi dati
  if (/\b(analiz|analy|dati|data|grafico|chart|statistic|csv|excel|tabella)\b/.test(lower)) {
    return 'analysis';
  }
  // Informazioni in tempo reale
  if (/\b(oggi|today|attual|current|news|notizie|ultimo|latest|2026|2025)\b/.test(lower)) {
    return 'realtime';
  }
  // Ragionamento complesso
  if (/\b(spiega|explain|perch[eé]|why|come funziona|how does|ragion|reason|logic|matematica|math)\b/.test(lower)) {
    return 'reasoning';
  }
  return 'conversation';
}

// Router intelligente: sceglie il modello migliore per ogni richiesta
function routeToProvider(requestType: RequestType, mode: AIMode): AIProvider {
  if (mode === 'local') return 'ollama';

  switch (requestType) {
    case 'code':
      return 'claude';       // Claude eccelle nel codice
    case 'creative':
      return 'gpt4';         // GPT-4 eccelle nella scrittura creativa
    case 'realtime':
      return 'grok';         // Grok ha accesso dati X/Twitter in tempo reale
    case 'analysis':
      return 'claude';       // Claude eccelle nell'analisi
    case 'reasoning':
      return 'claude';       // Claude eccelle nel ragionamento
    case 'conversation':
    default:
      return 'claude';       // Default: Claude come modello primario
  }
}

// Interfaccia con Ollama (locale)
async function callOllama(
  messages: Array<{ role: string; content: string }>,
  model: string = 'qwen2.5-coder:3b',
  host: string = 'http://localhost:11434'
): Promise<AIResponse> {
  const start = Date.now();

  const response = await fetch(`${host}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model,
      messages,
      stream: false,
    }),
  });

  if (!response.ok) {
    throw new Error(`Ollama error: ${response.status} ${response.statusText}`);
  }

  const data = await response.json();

  return {
    content: data.message?.content || '',
    provider: 'ollama',
    model,
    tokensUsed: (data.prompt_eval_count || 0) + (data.eval_count || 0),
    latencyMs: Date.now() - start,
  };
}

// Interfaccia con LiteLLM proxy (cloud)
async function callCloud(
  messages: Array<{ role: string; content: string }>,
  provider: AIProvider,
  apiKeys: Record<string, string>
): Promise<AIResponse> {
  const start = Date.now();
  const model = CLOUD_MODELS[provider];

  if (!model) throw new Error(`Provider non supportato: ${provider}`);

  // Determina l'API key corretta
  const keyMap: Record<string, string> = {
    claude: apiKeys.ANTHROPIC_API_KEY || '',
    gpt4: apiKeys.OPENAI_API_KEY || '',
    grok: apiKeys.XAI_API_KEY || '',
    mistral: apiKeys.MISTRAL_API_KEY || '',
    deepseek: apiKeys.DEEPSEEK_API_KEY || '',
  };

  const apiKey = keyMap[provider];
  if (!apiKey) throw new Error(`API key mancante per ${provider}`);

  // Chiama direttamente l'API OpenAI-compatible del provider
  // (LiteLLM normalizza tutto nel formato OpenAI)
  const baseUrls: Record<string, string> = {
    claude: 'https://api.anthropic.com/v1',
    gpt4: 'https://api.openai.com/v1',
    grok: 'https://api.x.ai/v1',
    mistral: 'https://api.mistral.ai/v1',
    deepseek: 'https://api.deepseek.com/v1',
  };

  const response = await fetch(`${baseUrls[provider]}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
      ...(provider === 'claude' ? { 'x-api-key': apiKey, 'anthropic-version': '2023-06-01' } : {}),
    },
    body: JSON.stringify({
      model: model.split('/')[1],
      messages,
      max_tokens: 4096,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`${provider} API error: ${response.status} - ${error}`);
  }

  const data = await response.json();

  return {
    content: data.choices?.[0]?.message?.content || '',
    provider,
    model: model.split('/')[1],
    tokensUsed: data.usage?.total_tokens || 0,
    latencyMs: Date.now() - start,
  };
}

// FUNZIONE PRINCIPALE: Invia messaggio all'orchestra AI
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
  }
): Promise<AIResponse> {
  const lastMessage = messages[messages.length - 1];
  if (!lastMessage) throw new Error('Nessun messaggio da inviare');

  // Formatta messaggi per l'API
  const apiMessages = messages.map(m => ({
    role: m.role,
    content: m.content,
  }));

  // Routing intelligente
  let provider = config.primaryProvider;
  if (config.autoRouting && config.mode === 'cloud') {
    const requestType = classifyRequest(lastMessage.content);
    provider = routeToProvider(requestType, config.mode);
    console.log(`[Orchestra] Tipo richiesta: ${requestType} → Provider: ${provider}`);
  }

  // Tenta con il provider principale
  try {
    let response: AIResponse;

    if (config.mode === 'local' || provider === 'ollama') {
      response = await callOllama(
        apiMessages,
        config.ollamaModel || 'qwen2.5-coder:3b',
        config.ollamaHost
      );
    } else {
      response = await callCloud(apiMessages, provider, config.apiKeys);
    }

    // Cross-check opzionale
    if (config.crossCheckEnabled && config.mode === 'cloud' && config.fallbackProviders.length > 0) {
      try {
        const checkProvider = config.fallbackProviders[0];
        const checkResponse = await callCloud(
          [
            ...apiMessages,
            { role: 'assistant', content: response.content },
            { role: 'user', content: 'Verifica se la risposta precedente è accurata e corretta. Rispondi solo con "CONFERMATO" se è corretta, o spiega brevemente gli errori.' }
          ],
          checkProvider,
          config.apiKeys
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
    // Fallback: prova i provider di backup
    console.warn(`[Orchestra] Provider ${provider} fallito, tentativo fallback...`);

    for (const fallback of config.fallbackProviders) {
      try {
        if (fallback === 'ollama') {
          return await callOllama(apiMessages, config.ollamaModel, config.ollamaHost);
        } else {
          return await callCloud(apiMessages, fallback, config.apiKeys);
        }
      } catch (fallbackError) {
        console.warn(`[Orchestra] Fallback ${fallback} fallito:`, fallbackError);
        continue;
      }
    }

    throw new Error(`Tutti i provider hanno fallito. Ultimo errore: ${error}`);
  }
}

export { classifyRequest, routeToProvider, CLOUD_MODELS, LOCAL_MODELS };
