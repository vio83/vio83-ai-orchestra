<p align="center">
  <img src="https://img.shields.io/badge/VIO_83-AI_ORCHESTRA-00ff00?style=for-the-badge&logo=music&logoColor=black" alt="VIO 83 AI ORCHESTRA" />
</p>

<h1 align="center">🎵 VIO 83 AI ORCHESTRA</h1>

<p align="center">
  <strong>The World's First Intelligent Multi-AI Orchestration Platform</strong><br>
  <em>One app. Every AI. Smart routing. Verified answers.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Claude-Opus_4-D97706?style=flat-square&logo=anthropic" />
  <img src="https://img.shields.io/badge/GPT--4o-OpenAI-10B981?style=flat-square&logo=openai" />
  <img src="https://img.shields.io/badge/Grok_2-xAI-3B82F6?style=flat-square" />
  <img src="https://img.shields.io/badge/Mistral-Large-8B5CF6?style=flat-square" />
  <img src="https://img.shields.io/badge/DeepSeek-R1-EC4899?style=flat-square" />
  <img src="https://img.shields.io/badge/Ollama-Local-00ff00?style=flat-square" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Tauri_2.0-Rust_+_WebView-FFC131?style=flat-square&logo=tauri" />
  <img src="https://img.shields.io/badge/React_19-TypeScript-61DAFB?style=flat-square&logo=react" />
  <img src="https://img.shields.io/badge/LiteLLM-100+_Providers-FF6B6B?style=flat-square" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" />
</p>

<p align="center">
  <a href="#-why-vio-83">Why VIO 83?</a> •
  <a href="#-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-sponsor">Sponsor</a>
</p>

---

## 🎯 Why VIO 83?

**The problem is simple**: today you pay for 5 different AI subscriptions, switch between 10 browser tabs, get inconsistent answers, and have zero verification that the AI isn't hallucinating.

**VIO 83 AI Orchestra** solves this with one elegant principle:

> **One interface. Every AI model in the world. The smartest one answers your question. Verified.**

### What Makes It Different

| Feature | ChatGPT | Claude.ai | VIO 83 |
|---------|---------|-----------|--------|
| Multiple AI models | ❌ GPT only | ❌ Claude only | ✅ **6+ providers** |
| Smart auto-routing | ❌ | ❌ | ✅ **AI picks the best model per task** |
| Cross-check verification | ❌ | ❌ | ✅ **Second AI verifies the first** |
| RAG with certified sources | ❌ | ❌ | ✅ **Academic/library verification** |
| Works 100% offline | ❌ | ❌ | ✅ **Ollama local models** |
| Desktop native app | ❌ Web only | ❌ Web only | ✅ **Tauri 2.0 (2MB app!)** |
| Privacy-first | ❌ Cloud only | ❌ Cloud only | ✅ **Your data stays on your Mac** |
| Open source | ❌ | ❌ | ✅ **MIT License** |

---

## ✨ Features

### 🧠 Intelligent Routing
The Orchestra doesn't just call an AI — it **thinks about which AI to call**:

- **Code questions** → Claude Sonnet (best reasoning) or Qwen Coder (local)
- **Creative writing** → GPT-4o (strongest creative) or Llama (local)
- **Real-time info** → Grok 2 (connected to X/Twitter)
- **Deep reasoning** → Claude Opus or DeepSeek R1
- **Quick tasks** → Haiku or Gemma 2 (fastest, cheapest)

### 🔍 Cross-Check Verification
For critical answers, a **second AI model** independently verifies the first response. If they disagree, you see both perspectives with a concordance score.

### 📚 RAG — Certified Knowledge Base
Every answer can be checked against a local database of **verified sources** — academic papers, official documentation, library records. No social media noise. No hallucinations passing as facts.

Quality badges on every response:
- 🥇 **Gold** — Verified by 3+ certified sources
- 🥈 **Silver** — Partially corroborated
- 🥉 **Bronze** — Low confidence, use with caution
- ⚪ **Unverified** — No matching sources found

### 🌐 Cloud + Local: You Choose
- **Cloud Mode**: Always-latest models via API (Claude Opus 4, GPT-4o, Grok 2, Mistral Large, DeepSeek R1)
- **Local Mode**: 100% offline with Ollama (Llama 3.2, Qwen, Mistral, Phi-3, Gemma 2)
- **Hybrid Mode**: Cloud primary, local fallback when offline

### 🔒 Security First
- API keys stored in **macOS Keychain** (hardware-encrypted)
- Local mode = zero data leaves your machine
- No telemetry, no tracking, no data collection
- Open source = fully auditable

### 🎨 Vio Dark Fluorescent Theme
A custom-designed dark theme optimized for long coding sessions:
- Pure black background (#000000)
- Fluorescent green accents (#00FF00)
- Magenta highlights (#FF00FF)
- Cyan cursor (#00FFFF)
- JetBrains Mono for code, Inter for UI

---

## 🚀 Quick Start

### Prerequisites
- **macOS** (Apple Silicon recommended)
- **Node.js** 20+ (`nvm install 20`)
- **Rust** (`curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`)
- **Python** 3.11+ (`brew install python`)
- **Ollama** (`brew install ollama`)

### Install

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/vio83-ai-orchestra.git
cd vio83-ai-orchestra

# Frontend
npm install

# Backend
pip3 install litellm fastapi uvicorn chromadb anthropic openai httpx

# Download a local model
ollama pull qwen2.5-coder:3b

# Configure API keys (optional, for cloud mode)
cp .env.example .env
# Edit .env with your keys
```

### Run

```bash
# Terminal 1: Backend API
python -m backend.api.server

# Terminal 2: Frontend dev server
npm run dev

# Terminal 3 (optional): Tauri desktop app
npm run tauri dev
```

Open `http://localhost:5173` — your Orchestra is ready. 🎵

---

## 🏗 Architecture

```
USER types a question
        ↓
┌─────────────────────────┐
│  Frontend (React/Tauri)  │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  Request Classifier      │  ← Categorizes: code/creative/analysis/realtime
└───────────┬─────────────┘
            ↓
    ┌───────┴───────┐
    │  CLOUD MODE?   │
    │                │
    │ YES → LiteLLM  │ → Claude / GPT-4 / Grok / Mistral / DeepSeek
    │                │
    │ NO → Ollama    │ → Llama / Qwen / Mistral / Phi (on your Mac)
    └───────┬───────┘
            ↓
┌─────────────────────────┐
│  Cross-Check (optional)  │  ← Second AI validates first response
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  RAG Verification        │  ← Check against certified sources
└───────────┬─────────────┘
            ↓
   Response + Quality Badge
            ↓
      USER gets verified answer ✓
```

### Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Desktop | **Tauri 2.0** | 2MB app vs 100MB Electron. Native performance. |
| Frontend | **React 19 + TypeScript** | World's largest ecosystem. Type-safe. |
| Styling | **Tailwind CSS** | Utility-first, fast to write. |
| State | **Zustand** | 1KB, simple, powerful. |
| AI Gateway | **LiteLLM** | 100+ providers, unified API. Used by Netflix. |
| Local AI | **Ollama** | Run any model locally. Privacy-first. |
| Backend | **FastAPI** | Fastest Python web framework. Async. |
| Vector DB | **ChromaDB** | Embeddings + semantic search for RAG. |
| Security | **macOS Keychain** | Hardware-encrypted key storage. |

---

## 📊 Supported Models

### Cloud (API required)
| Provider | Model | Best For | Context |
|----------|-------|----------|---------|
| Anthropic | Claude Opus 4 | Complex reasoning, research | 200K |
| Anthropic | Claude Sonnet 4 | Code, analysis, writing | 200K |
| OpenAI | GPT-4o | Creative, multimodal | 128K |
| xAI | Grok 2 | Real-time info, unfiltered | 131K |
| Mistral | Mistral Large | Multilingual, reasoning | 128K |
| DeepSeek | DeepSeek R1 | Math, science, deep reasoning | 64K |

### Local (Ollama, no API needed)
| Model | Size | RAM | Best For |
|-------|------|-----|----------|
| Qwen 2.5 Coder 3B | 2.0 GB | 2.5 GB | Code generation |
| Llama 3.2 3B | 2.0 GB | 2.5 GB | General assistant |
| Mistral 7B | 4.1 GB | 5.0 GB | Reasoning |
| Phi-3 3.8B | 2.3 GB | 3.0 GB | Efficient reasoning |
| DeepSeek Coder V2 Lite | 2.5 GB | 3.5 GB | Code + debugging |
| Gemma 2 2B | 1.6 GB | 2.0 GB | Ultra-fast responses |

---

## 🗺 Roadmap

- [x] **Phase 1** — Core architecture (Tauri + React + TypeScript)
- [x] **Phase 2** — AI orchestrator with smart routing
- [x] **Phase 3** — RAG engine with verified sources
- [ ] **Phase 4** — VS Code extension
- [ ] **Phase 5** — iPhone companion app (iCloud sync)
- [ ] **Phase 6** — Marketplace for custom AI workflows
- [ ] **Phase 7** — Enterprise features (team management, SSO)

---

## 💚 Sponsor This Project

<p align="center">
  <a href="https://github.com/sponsors/YOUR_USERNAME">
    <img src="https://img.shields.io/badge/GitHub_Sponsors-Support_VIO_83-ea4aaa?style=for-the-badge&logo=github-sponsors" />
  </a>
  &nbsp;&nbsp;
  <a href="https://ko-fi.com/YOUR_USERNAME">
    <img src="https://img.shields.io/badge/Ko--fi-Buy_me_a_coffee-FF5E5B?style=for-the-badge&logo=ko-fi" />
  </a>
</p>

VIO 83 AI Orchestra is built with passion by **one independent developer** on a MacBook Air M1 with 8GB RAM. Every sponsorship directly funds:

- 🖥 **Better hardware** — A Mac Studio M4 Ultra (192GB RAM) for running larger models locally and faster development
- 🧪 **API costs** — Testing all cloud providers costs real money
- ⏰ **Full-time development** — More time = faster features
- 🌍 **Keeping it open source** — Forever free for the community

### Sponsor Tiers

| Tier | Amount | Perks |
|------|--------|-------|
| ☕ Coffee | $3/mo | Name in README + early access to releases |
| 🎵 Musician | $10/mo | Above + priority feature requests + Discord role |
| 🎼 Conductor | $25/mo | Above + monthly 1:1 call + custom routing rules |
| 🏆 Patron | $100/mo | Above + your logo in the app + dedicated support |

**Every dollar counts.** Even $3/month helps keep this project alive and growing.

---

## 🤝 Contributing

Contributions are welcome! Whether it's code, documentation, translations, or bug reports.

```bash
# Fork, clone, create branch
git checkout -b feature/amazing-feature

# Make changes, test
npm run build

# Submit PR
git push origin feature/amazing-feature
```

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

<p align="center">
  <strong>Built with 💚 by PadronaVio</strong><br>
  <em>One developer. One vision. The entire AI world in one app.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Made_with-Passion-00ff00?style=flat-square" />
  <img src="https://img.shields.io/badge/Powered_by-Music_🎵-ff00ff?style=flat-square" />
  <img src="https://img.shields.io/badge/Running_on-MacBook_Air_M1-00ffff?style=flat-square" />
</p>
