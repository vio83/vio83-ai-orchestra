// VIO 83 AI ORCHESTRA - Type Definitions

export type AIProvider = 'claude' | 'gpt4' | 'grok' | 'mistral' | 'deepseek' | 'ollama';

export type AIMode = 'cloud' | 'local';

export interface AIModel {
  id: string;
  name: string;
  provider: AIProvider;
  mode: AIMode;
  description: string;
  maxTokens: number;
  costPer1kTokens?: number; // undefined for local models
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  provider?: AIProvider;
  model?: string;
  timestamp: number;
  qualityScore?: number; // Cross-check quality badge
  verified?: boolean;    // RAG verification status
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  model: string;
  provider: AIProvider;
  mode: AIMode;
  createdAt: number;
  updatedAt: number;
}

export interface APIKeyConfig {
  provider: AIProvider;
  key: string;
  isValid: boolean;
  lastChecked?: number;
}

export interface OrchestratorConfig {
  mode: AIMode;
  primaryProvider: AIProvider;
  fallbackProviders: AIProvider[];
  crossCheckEnabled: boolean;
  ragEnabled: boolean;
  autoRouting: boolean; // Smart routing based on request type
}

export interface AppSettings {
  theme: 'vio-dark' | 'light';
  language: 'it' | 'en';
  orchestrator: OrchestratorConfig;
  apiKeys: APIKeyConfig[];
  ollamaHost: string;
  fontSize: number;
}

// AI Response with metadata
export interface AIResponse {
  content: string;
  provider: AIProvider;
  model: string;
  tokensUsed: number;
  latencyMs: number;
  crossCheckResult?: {
    concordance: boolean;
    secondProvider: AIProvider;
    secondResponse?: string;
  };
}
