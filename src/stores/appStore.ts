// VIO 83 AI ORCHESTRA - Global State Management (Zustand)
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AIProvider, AIMode, Conversation, Message, AppSettings } from '../types';

interface AppState {
  // Current conversation
  conversations: Conversation[];
  activeConversationId: string | null;

  // AI Settings
  settings: AppSettings;

  // UI State
  sidebarOpen: boolean;
  settingsOpen: boolean;
  isStreaming: boolean;

  // Actions
  createConversation: () => string;
  setActiveConversation: (id: string) => void;
  addMessage: (conversationId: string, message: Message) => void;
  updateSettings: (settings: Partial<AppSettings>) => void;
  setMode: (mode: AIMode) => void;
  setProvider: (provider: AIProvider) => void;
  setOllamaModel: (model: string) => void;
  toggleSidebar: () => void;
  toggleSettings: () => void;
  setStreaming: (streaming: boolean) => void;
  deleteConversation: (id: string) => void;
  resetToLocal: () => void;
}

const defaultSettings: AppSettings = {
  theme: 'vio-dark',
  language: 'it',
  orchestrator: {
    mode: 'local',
    primaryProvider: 'ollama',
    fallbackProviders: [],
    crossCheckEnabled: false,
    ragEnabled: false,
    autoRouting: false,
  },
  apiKeys: [],
  ollamaHost: 'http://localhost:11434',
  ollamaModel: 'llama3.2:3b',
  fontSize: 14,
};

// Versione dello schema — incrementa per forzare reset dei settings corrotti
const STORE_VERSION = 2;

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      conversations: [],
      activeConversationId: null,
      settings: defaultSettings,
      sidebarOpen: true,
      settingsOpen: false,
      isStreaming: false,

      createConversation: () => {
        const id = crypto.randomUUID();
        const s = get().settings;
        const newConv: Conversation = {
          id,
          title: 'Nuova conversazione',
          messages: [],
          model: s.orchestrator.mode === 'local'
            ? (s.ollamaModel || 'qwen2.5-coder:3b')
            : 'claude-sonnet-4-20250514',
          provider: s.orchestrator.primaryProvider,
          mode: s.orchestrator.mode,
          createdAt: Date.now(),
          updatedAt: Date.now(),
        };
        set(state => ({
          conversations: [newConv, ...state.conversations],
          activeConversationId: id,
        }));
        return id;
      },

      setActiveConversation: (id) => set({ activeConversationId: id }),

      addMessage: (conversationId, message) => {
        set(state => ({
          conversations: state.conversations.map(conv =>
            conv.id === conversationId
              ? {
                  ...conv,
                  messages: [...conv.messages, message],
                  updatedAt: Date.now(),
                  title: conv.messages.length === 0 && message.role === 'user'
                    ? message.content.slice(0, 50) + (message.content.length > 50 ? '...' : '')
                    : conv.title,
                }
              : conv
          ),
        }));
      },

      updateSettings: (newSettings) => {
        set(state => ({
          settings: { ...state.settings, ...newSettings },
        }));
      },

      setMode: (mode) => {
        set(state => ({
          settings: {
            ...state.settings,
            orchestrator: {
              ...state.settings.orchestrator,
              mode,
              primaryProvider: mode === 'local' ? 'ollama' : 'claude',
              autoRouting: mode === 'cloud',
            },
          },
        }));
      },

      setProvider: (provider) => {
        set(state => ({
          settings: {
            ...state.settings,
            orchestrator: {
              ...state.settings.orchestrator,
              primaryProvider: provider,
            },
          },
        }));
      },

      setOllamaModel: (model) => {
        set(state => ({
          settings: {
            ...state.settings,
            ollamaModel: model,
          },
        }));
      },

      toggleSidebar: () => set(state => ({ sidebarOpen: !state.sidebarOpen })),
      toggleSettings: () => set(state => ({ settingsOpen: !state.settingsOpen })),
      setStreaming: (streaming) => set({ isStreaming: streaming }),

      deleteConversation: (id) => {
        set(state => ({
          conversations: state.conversations.filter(c => c.id !== id),
          activeConversationId: state.activeConversationId === id ? null : state.activeConversationId,
        }));
      },

      resetToLocal: () => {
        set(state => ({
          settings: {
            ...state.settings,
            orchestrator: {
              ...defaultSettings.orchestrator,
            },
            ollamaModel: state.settings.ollamaModel || defaultSettings.ollamaModel,
          },
        }));
      },
    }),
    {
      name: 'vio83-ai-orchestra-storage',
      version: STORE_VERSION,
      migrate: (persistedState: any, version: number) => {
        // Se la versione è vecchia, resetta i settings orchestrator a local
        if (version < STORE_VERSION) {
          console.log('[VIO83] Migrazione store: reset a modalità locale');
          return {
            ...persistedState,
            settings: {
              ...defaultSettings,
              // Mantieni le conversazioni e le API keys se esistono
              apiKeys: persistedState?.settings?.apiKeys || [],
              ollamaHost: persistedState?.settings?.ollamaHost || defaultSettings.ollamaHost,
              ollamaModel: persistedState?.settings?.ollamaModel || defaultSettings.ollamaModel,
            },
          };
        }
        return persistedState;
      },
    }
  )
);
