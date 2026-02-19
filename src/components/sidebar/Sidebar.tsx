// VIO 83 AI ORCHESTRA - Sidebar Conversazioni
import { MessageSquarePlus, Trash2, Settings, Music, ChevronLeft } from 'lucide-react';
import { useAppStore } from '../../stores/appStore';

export default function Sidebar() {
  const {
    conversations,
    activeConversationId,
    sidebarOpen,
    createConversation,
    setActiveConversation,
    deleteConversation,
    toggleSidebar,
    toggleSettings,
  } = useAppStore();

  if (!sidebarOpen) return null;

  return (
    <div style={{
      width: '260px',
      height: '100%',
      backgroundColor: 'var(--vio-bg-secondary)',
      borderRight: '1px solid var(--vio-border)',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
    }}>
      {/* Header */}
      <div style={{
        padding: '16px',
        borderBottom: '1px solid var(--vio-border)',
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
      }}>
        <Music size={20} color="var(--vio-green)" />
        <span style={{
          fontSize: '15px',
          fontWeight: 700,
          color: 'var(--vio-green)',
          flex: 1,
        }}>
          VIO 83
        </span>
        <button
          onClick={toggleSidebar}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--vio-text-dim)', padding: '4px',
          }}
        >
          <ChevronLeft size={16} />
        </button>
      </div>

      {/* New chat button */}
      <div style={{ padding: '12px' }}>
        <button
          onClick={() => createConversation()}
          style={{
            width: '100%',
            padding: '10px',
            borderRadius: 'var(--vio-radius)',
            border: '1px dashed var(--vio-green-dim)',
            backgroundColor: 'transparent',
            color: 'var(--vio-green)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            fontSize: '13px',
            fontWeight: 500,
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(0,255,0,0.05)'}
          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
        >
          <MessageSquarePlus size={16} />
          Nuova conversazione
        </button>
      </div>

      {/* Conversation list */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '0 8px',
      }}>
        {conversations.length === 0 ? (
          <p style={{
            color: 'var(--vio-text-dim)',
            fontSize: '12px',
            textAlign: 'center',
            padding: '20px',
          }}>
            Nessuna conversazione
          </p>
        ) : (
          conversations.map(conv => (
            <div
              key={conv.id}
              onClick={() => setActiveConversation(conv.id)}
              style={{
                padding: '10px 12px',
                borderRadius: '6px',
                marginBottom: '2px',
                cursor: 'pointer',
                backgroundColor: conv.id === activeConversationId ? 'rgba(0,255,0,0.08)' : 'transparent',
                border: conv.id === activeConversationId ? '1px solid rgba(0,255,0,0.2)' : '1px solid transparent',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                transition: 'all 0.15s',
              }}
              onMouseEnter={(e) => {
                if (conv.id !== activeConversationId)
                  e.currentTarget.style.backgroundColor = 'var(--vio-bg-hover)';
              }}
              onMouseLeave={(e) => {
                if (conv.id !== activeConversationId)
                  e.currentTarget.style.backgroundColor = 'transparent';
              }}
            >
              <span style={{
                flex: 1,
                fontSize: '13px',
                color: conv.id === activeConversationId ? 'var(--vio-green)' : 'var(--vio-text-secondary)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}>
                {conv.title}
              </span>

              <button
                onClick={(e) => { e.stopPropagation(); deleteConversation(conv.id); }}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--vio-text-dim)', padding: '2px',
                  opacity: 0.5, transition: 'opacity 0.2s',
                }}
                onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
                onMouseLeave={(e) => e.currentTarget.style.opacity = '0.5'}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))
        )}
      </div>

      {/* Footer: Settings */}
      <div style={{
        padding: '12px',
        borderTop: '1px solid var(--vio-border)',
      }}>
        <button
          onClick={toggleSettings}
          style={{
            width: '100%',
            padding: '8px',
            borderRadius: '6px',
            border: 'none',
            backgroundColor: 'var(--vio-bg-tertiary)',
            color: 'var(--vio-text-secondary)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            fontSize: '13px',
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--vio-bg-hover)';
            e.currentTarget.style.color = 'var(--vio-green)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--vio-bg-tertiary)';
            e.currentTarget.style.color = 'var(--vio-text-secondary)';
          }}
        >
          <Settings size={16} />
          Impostazioni
        </button>
      </div>
    </div>
  );
}
