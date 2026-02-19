// VIO 83 AI ORCHESTRA - App Principale
import { Menu } from 'lucide-react';
import { useAppStore } from './stores/appStore';
import Sidebar from './components/sidebar/Sidebar';
import ChatView from './components/chat/ChatView';
import { SettingsPanel } from './components/settings/SettingsPanel';
import './styles/vio-dark.css';

export default function App() {
  const { sidebarOpen, toggleSidebar, settings, settingsOpen } = useAppStore();

  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      width: '100vw',
      overflow: 'hidden',
      backgroundColor: 'var(--vio-bg-primary)',
      color: 'var(--vio-text-primary)',
    }}>
      {/* Sidebar */}
      <Sidebar />

      {/* Main content */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
      }}>
        {/* Top bar */}
        {!sidebarOpen && (
          <div style={{
            padding: '8px 16px',
            borderBottom: '1px solid var(--vio-border)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            backgroundColor: 'var(--vio-bg-secondary)',
          }}>
            <button
              onClick={toggleSidebar}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: 'var(--vio-text-secondary)', padding: '4px',
              }}
            >
              <Menu size={20} />
            </button>
            <span style={{ fontSize: '14px', color: 'var(--vio-green)', fontWeight: 600 }}>
              VIO 83 AI Orchestra
            </span>
            <span style={{
              fontSize: '11px',
              marginLeft: 'auto',
              padding: '2px 8px',
              borderRadius: '10px',
              border: `1px solid ${settings.orchestrator.mode === 'cloud' ? 'var(--vio-cyan)' : 'var(--vio-green)'}`,
              color: settings.orchestrator.mode === 'cloud' ? 'var(--vio-cyan)' : 'var(--vio-green)',
            }}>
              {settings.orchestrator.mode === 'cloud' ? '☁️ Cloud' : '💻 Locale'}
            </span>
          </div>
        )}

        {/* Chat view */}
        <ChatView />
      </div>

      {/* Settings modal */}
      {settingsOpen && <SettingsPanel />}
    </div>
  );
}
