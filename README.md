<p align="center">
  <img src="assets/logo.png" alt="Music Recommendation Agent logo" width="140">
</p>

<h1 align="center">音乐推荐 Agent · Music Recommendation Agent</h1>

<p align="center">
  一句自然语言，串起心情、场景与故事的整条音乐旅程。
</p>

<p align="center">
  <a href="http://localhost:3000/recommendations"><strong>立即体验流式推荐</strong></a>
  ·
  <a href="#quick-start">快速开始</a>
  ·
  <a href="#-%E6%9E%B6%E6%9E%84%E4%B8%80%E8%A7%88">架构一览</a>
</p>

---

## Highlights

- 🎯 **自然语言驱动的音乐推荐**：智能理解心情、场景、流派等需求，一句话生成推荐歌单
- 🔍 **可解释推荐**：集成搜索 + 推荐 + 说明，让你真正知道每首歌“为什么被选中”
- ⚡ **实时流式体验**：SSE 流式渲染推荐结果，回应内容逐词出现、歌曲逐首上屏
- 🌐 **现代化前后端架构**：FastAPI 后端 + Next.js 前端，便于二次开发与集成
- ⚙️ **LangGraph 工作流编排**：将意图识别、搜索、推荐解释拆分为清晰节点，便于扩展
- 🔐 **灵活接入 LLM 与数据源**：支持自定义 LLM（DeepSeek、Qwen 等）与本地音乐数据
- 🎼 **音乐旅程生成器**：按故事或情绪曲线自动划分段落，并为每一段流式生成契合的配套音乐

## 项目概览

音乐推荐 Agent 是一个面向内容创作者与音乐爱好者的 AI 助手，你可以像和朋友聊天一样，用自然语言描述你“想听什么”，其余交给系统完成：

- **心情 / 场景驱动的歌单生成**：例如「适合深夜加班写代码的节奏」或「和朋友自驾去海边」
- **基于歌手 / 流派的探索**：例如「按照周杰伦的风格，再找一些同样浪漫的中文 R&B」
- **推荐背后逻辑的透明解释**：不仅给出歌单，还用自然语言说明为什么推荐这些歌
- **音乐旅程编排**：根据故事 / 情绪曲线划分段落，为每一段挑选节奏与氛围都契合的配套音乐
- **流式交互体验**：推荐结果逐词显示、歌曲逐个添加，随时可以打断或调整输入
- **RESTful API**：提供完整的 API 接口，支持前后端分离与系统集成
- **面向扩展的 API 化设计**：便于后续接入更多音乐平台或个性化画像

项目默认使用硅基流动提供的 DeepSeek / Qwen 模型，也可接入其他兼容 OpenAI 接口风格的 LLM 服务。

### 主页面预览

<p align="center">
  <img src="assets/首页.png" alt="应用首页界面" width="780">
  <br />
  <sub>前端主页面：左侧导航 + 右侧推荐输入与结果区</sub>
</p>

### 音乐旅程编排（Music Journey）

在传统歌单之外，本项目特别提供「音乐旅程生成器」，适合播客创作者、展览策划、沉浸式空间与长时间专注场景使用：

- 你可以输入一段**故事**（例如“一天的情绪变化”）或一组**情绪时间点**（mood timeline）
- 系统会分析故事结构或情绪曲线，将整个时长划分为若干个**音乐阶段（Segments）**
- 每个阶段都会给出清晰的情绪标签、文字描述，并推荐一组节奏与氛围匹配的歌曲
- 通过 SSE 流式接口，**旅程结构、片段信息与每首歌会被逐步推送到前端**，便于实时可视化与交互
- 对于有二次开发需求的用户，也可以直接调用 `/api/journey` 与 `/api/journey/stream` 接口，将音乐旅程编排能力嵌入自己的产品中

### 架构特点

- **后端**：FastAPI + LangGraph，支持SSE流式输出
- **前端**：Next.js + React，现代化UI体验
- **数据流**：SSE（Server-Sent Events）实现实时流式渲染
- **代理层**：Next.js API路由作为SSE代理，简化前后端通信


## 使用指南

### Web 界面

1. 打开浏览器访问 `http://localhost:8501`
2. 在「音乐推荐」页输入需求（心情、场景、歌手等），通过 LangGraph 工作流 + LLM 生成带解释的音乐推荐
<p align="center">
  <img src="assets/音乐推荐.png" alt="音乐推荐页：自然语言输入与流式推荐结果" width="800">
</p>
3. 在「音乐搜索」页，通过在线乐库 + 网络搜索进行歌曲网络推荐 / 搜索，支持“歌手 + 流派”等自然语言请求
<p align="center">
  <img src="assets/歌曲搜索.png" alt="音乐搜索页：关键词与流派驱动的歌曲网络推荐" width="800">
</p>
4. 在「歌单创作」与「音乐旅程」视图中，查看推荐说明、歌单结构与整条音乐旅程的分段编排
<p align="center">
  <img src="assets/歌单创作.png" alt="歌单创作视图：推荐理由与歌单结构" width="800">
</p>
<p align="center">
  <img src="assets/音乐旅程.png" alt="音乐旅程视图：按情绪分段的音乐旅程时间线" width="800">
</p>

## Quick Start

### 环境要求

- Python 3.8+
- pip / uv / poetry 等任意包管理工具
- 可选：GPU 环境以加速本地推理

### 安装

```bash
git clone <your-repo-url>
cd deep-search
pip install -r requirements.txt
```

### 配置密钥

```json
{
  "SILICONFLOW_API_KEY": "",
  "SILICONFLOW_BASE_URL": "https://api.siliconflow.cn/v1",
  "SILICONFLOW_CHAT_MODEL": "Qwen/Qwen2.5-72B-Instruct",
  "TAILYAPI_API_KEY": "",
  "TAILYAPI_BASE_URL": "https://api.tavily.com",
  "APP_NAME": "DeepSearch Quickstart",
  "SPOTIFY_CLIENT_ID": "",
  "SPOTIFY_CLIENT_SECRET": ""
}
```

> 提示：也可通过环境变量 `SILICONFLOW_API_KEY` 等方式配置，无需 `setting.json`。

### 本地运行

#### 方式1：使用Streamlit界面（传统方式）

```bash
python run_music_app.py
```

访问 `http://localhost:8501` 即可体验 Web 界面。  
如需使用 Streamlit 自带命令，替换为：

```bash
streamlit run music_app.py
```

#### 方式2：使用FastAPI + Next.js（推荐，支持流式输出）

**启动后端API服务器：**

```bash
# 方式1：使用便捷脚本（推荐）
python run_api_server.py

# 方式2：使用启动脚本
python api/start_server.py
```

后端将在 `http://localhost:8501` 启动，API文档：`http://localhost:8501/docs`

**启动前端：**

```bash
cd web
npm install  # 首次运行需要安装依赖
npm run dev
```

前端将在 `http://localhost:3000` 启动

访问 `http://localhost:3000/recommendations` 体验流式推荐功能。

> 💡 **提示**：确保设置了 `SILICONFLOW_API_KEY` 环境变量或在 `setting.json` 中配置。

## 配置说明

- `SILICONFLOW_API_KEY`：硅基流动平台获取的 API Key
- `SILICONFLOW_BASE_URL`：硅基流动 API 路径，默认为 `https://api.siliconflow.cn/v1`
- `SILICONFLOW_CHAT_MODEL`：对话模型，例如 `deepseek-ai/DeepSeek-V3`


如需接入更多第三方服务，只需在 `setting.json` 中新增字段，并在 `config/settings_loader.py` 中读取。

## MCP 工具集

- `mcp/music_server_updated_2025.py`：封装 `search_tracks`、`get_recommendations`、`create_playlist`、`analyze_playlist` 等工具，直接调用 Spotify API（基于 Spotipy）。
- `mcp/siliconflow_server.py`：可选的 MCP 服务，用于与 SiliconFlow API 协同。
- `mcp/ARCHITECTURE_DIAGRAM.md`：系统架构示意，展示从 LangGraph 工作流到 MCP 再到 Spotify 的链路。
- `mcp/csv_to_json.py`、`mcp/analyze_songs.py`：辅助数据处理脚本，可生成/分析本地歌单。
- `mcp/verify_config.py`、`verify_spotify_config.py`：用于诊断凭证与网络状态。

> 想要单独运行 MCP 服务器，可在 `mcp/` 下安装 `requirements.txt` 后执行 `python music_server_updated_2025.py`，再在主项目中通过 `tools.mcp_adapter` 调用。

## 架构一览

### 工作流架构

```
用户请求
  └─▶ 意图识别 (analyze_intent)
        └─▶ 条件路由 (route_by_intent)
                ├─▶ search_songs           → 推荐解释
                ├─▶ generate_recommendations → 推荐解释
                └─▶ general_chat
                      ↓
                  最终响应
```

### 前后端数据流架构（SSE）

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  前端组件   │ ──────> │ Next.js API   │ ──────> │ FastAPI     │
│ (React)     │         │ Route (代理)  │         │ Server      │
└─────────────┘         └──────────────┘         └─────────────┘
     ▲                        │                        │
     │                        │                        ▼
     │                        │                 ┌─────────────┐
     │                        │                 │ Music Agent │
     │                        │                 │ & Services  │
     │                        │                 └─────────────┘
     │                        │                        │
     └────────────────────────┴────────────────────────┘
                    SSE Stream (流式数据)
```

### 核心组件

- **LangGraph 工作流**：基于有向图节点管理不同任务
- **音乐工具层**：负责搜索、相似度匹配、心情标签解析
- **LLM 层**：负责自然语言理解与推荐解释生成
- **音乐旅程服务**：`MusicJourneyService` 支持故事/情绪曲线分析、分段规划与流式输出
- **FastAPI 后端**：提供RESTful API和SSE流式接口
- **Next.js 前端**：现代化UI，支持实时流式渲染
- **Streamlit 前端**（可选）：传统Web界面，展示推荐结果、可视化推荐理由

## 技术栈

### 后端
- **FastAPI**：现代化Python Web框架，支持SSE流式输出
- **LangGraph**：工作流编排
- **LangChain**：LLM 能力封装
- **Uvicorn**：ASGI服务器
- **Pydantic**：数据校验与状态管理
- **asyncio**：异步调度，提高响应效率

### 前端
- **Next.js 14**：React框架，支持App Router
- **TypeScript**：类型安全
- **React Hooks**：状态管理
- **Fetch API**：SSE流式数据处理

### 可选界面
- **Streamlit**：快速原型和传统Web界面

## 数据与扩展

- 音乐条目字段包含标题、艺术家、流派、情绪标签、推荐理由等
- 未来可对接 Spotify、网易云、Apple Music 等真实数据源
- 支持嵌入模型，将用户喜好与历史行为写入向量数据库

## 测试与验证

- `python test_config.py`：确认 `setting.json` 加载成功、环境变量写入正确、SiliconFlow 模型可用。
- `python test_music_mcp.py`：在配置好 Spotify 凭证后运行，逐项验证搜索、心情/活动推荐与 LangGraph 智能体链路。
- Streamlit UI 内置系统状态面板，可实时检查 API Key、最近推荐、MCP 运行情况。

> 建议在首次部署或更换凭证后先跑通以上脚本，确保外部依赖可用。

## Repository Map

```
deep search/
├── api/                    # FastAPI后端服务器
│   ├── server.py          # API服务器主文件
│   ├── start_server.py    # 启动脚本
│   └── README.md          # API文档
├── web/                    # Next.js前端应用
│   ├── app/               # Next.js App Router
│   │   ├── api/           # API路由（SSE代理）
│   │   ├── recommendations/ # 推荐页面
│   │   └── ...
│   ├── components/        # React组件
│   └── lib/               # 工具函数（API客户端）
├── music_agent.py          # 智能推荐核心
├── music_app.py            # Streamlit 前端
├── run_music_app.py        # Streamlit启动脚本
├── run_api_server.py       # API服务器启动脚本
├── config/                 # 配置加载
├── graphs/                 # LangGraph 工作流
├── services/               # 服务层（歌单推荐等）
├── tools/                  # 推荐与搜索工具
├── data/music_database.json# 示例音乐数据
├── SSE_DATAFLOW.md        # SSE数据流设计文档
└── QUICKSTART.md           # 快速启动指南
```

## 新功能：SSE流式数据流

### 特性

- ✅ **实时流式输出**：响应文本逐词显示，提供打字机效果
- ✅ **状态实时更新**：思考、处理中、完成等状态实时反馈
- ✅ **歌曲逐个添加**：推荐歌曲逐个添加到列表，提升用户体验
- ✅ **错误处理**：完善的错误处理和连接管理
- ✅ **可取消请求**：支持随时取消正在进行的请求

### 使用示例

访问 `http://localhost:3000/recommendations`，输入查询后即可看到：
1. 思考指示器显示当前处理状态
2. 响应文本逐词流式显示
3. 推荐歌曲逐个添加到列表

### 相关文档

- `SSE_DATAFLOW.md` - 详细的数据流设计文档
- `api/README.md` - API服务器使用文档
- `QUICKSTART.md` - 快速启动指南

## Roadmap

- [x] SSE流式输出支持
- [x] FastAPI后端API
- [x] Next.js前端界面
- [x] 对接 Spotify，实现实时乐库
- [ ] 支持用户登录与偏好记忆
- [ ] 在线播放 & 歌单分享功能
- [ ] 推荐算法优化（协同过滤、向量检索）
- [ ] 多语言界面与推荐说明
- [ ] WebSocket支持（双向通信）
- [ ] 推荐进度条显示

## Contributing

欢迎以 Issue / PR 的形式提交需求或改进建议：

- Fork 本仓库并创建新分支
- 遵循已有代码风格，尽量补充测试或示例
- 在 PR 中说明变更背景与验证方式

## License

MIT License
