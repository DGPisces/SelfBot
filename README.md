# SelfBot

基于 Discord 的“自我模仿”机器人，调用本地/自托管的 Ollama 生成回复，支持多风格路由、语音转写、网页管理与 Docker 部署。

## 快速开始

1. 安装依赖（建议 virtualenv）：
   ```bash
   python -m pip install -r requirements.txt
   ```
2. 复制并修改环境变量：
   ```bash
   cp .env.example .env
   # 设置 DISCORD_BOT_TOKEN / ADMIN_TOKEN / CONFIG_PATH 等
   ```
3. 根据需要调整 `configs/config.yaml`（风格、白名单、限流等）。
4. 启动：
   ```bash
   python -m bot.main
   ```
5. 打开网页管理：默认 `http://localhost:8000/admin`，在输入框填入 `ADMIN_TOKEN` 后即可管理。

## Docker 一键

```bash
docker compose up -d --build
```
默认启动：
- `selfbot`：Python 应用（8000），挂载 `./configs`、`./data`
- `ollama`：11434 端口；可自行加载需要的模型（如 `ollama run llama3`）

查看日志：
```bash
docker compose logs -f selfbot
```

## 配置要点

- `configs/config.yaml`：核心配置（风格列表、路由阈值、限流、上下文策略、白/黑名单、管理端口）。
- `.env`：
  - `DISCORD_BOT_TOKEN`：Discord Bot Token
  - `ADMIN_TOKEN`：Web 管理鉴权，所有 API 需要 `X-Admin-Token`
  - `CONFIG_PATH`：可覆盖配置路径（默认 `configs/config.yaml`）
  - `OLLAMA_BASE_URL`：可覆盖 Ollama 地址（默认指向 compose 中的 `ollama` 服务）

## 运行特性

- **多风格人格**：理工/温柔/毒舌/正式；路由自动选择，置信度低回退默认；可通过 `/selfbot_style` 或 Web Admin 手动指定 scope。
- **上下文多轮**：按配置的 scope（channel/user/thread）保存最近对话，自动引用。
- **限流与去重**：滑动窗口限流（可提示“稍后再回”），重复消息/相似消息短时不再回复。
- **图片策略**：纯图片礼貌提示“请用文字描述”；图文混合仅使用文字并提示图片无法读取。
- **语音策略**：识别音频附件/语音文件 -> ASR（默认 dummy，可切 HTTP）；失败给出温和提示。
- **Web 管理**：开关、风格即时修改、白/黑名单与限流更新、路由/错误日志查看、脱敏对话导出。
- **Slash Commands**：
  - `/selfbot_status` 查看状态
  - `/selfbot_toggle` 开/关
  - `/selfbot_style` 设置 guild/channel 的风格或切回自动

## 开发提示

- 代码入口：`bot/main.py`；Discord 客户端在 `bot/discord/client.py`，管理 API 在 `bot/web/admin_app.py`。
- 日志输出 stdout，敏感信息会脱敏。对话与审计保存在 `data/`。
- ASR：`bot/asr/providers.py` 默认 Dummy，可配置 HTTP ASR 服务（`asr.provider=http` 和对应 endpoint）。
- 模型输出通过 Ollama `/api/chat` 调用，可在风格配置里为不同人格指定不同模型/采样参数。

## 安全与隐私

- `.env` 与 `data/` 已在 `.gitignore` 中，避免提交敏感信息。
- 日志与导出均通过简单规则脱敏（手机号/邮箱/证件号/银行卡）。
- 管理端需要 `X-Admin-Token`，默认绑定 0.0.0.0，必要时请在配置中改为内网或加反向代理。
