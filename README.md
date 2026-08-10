# 小黑盒文章发布助手

基于 Python + Playwright 的小黑盒（xiaoheihe.cn）文章自动化发布工具：自动登录复用、进入编辑器、填充标题/正文，并支持**不重开浏览器的原地更新**。

## 功能

- **登录复用**：将系统 Edge 默认 profile 的登录态（cookie）复制到独立调试 profile，扫码登录一次后长期复用，无需重复登录
- **自动填充**：一键进入小黑盒文章编辑器，自动填入标题与正文（支持 markdown 语法）
- **原地更新**：常驻服务监听文章源文件变化，在**当前编辑器标签页**原地重填内容 —— 不重开浏览器、不新建草稿
- **人工确认发布**：所有自动填充都停在「发布」按钮前，由用户人工确认后点击发布

## 环境要求

- Windows + 已安装 Microsoft Edge
- Python 3.9+，`pip install playwright`

## 快速开始

```bash
# 1. 安装依赖
pip install playwright

# 2.（可选）如 Edge 不在默认路径，或用其他机器，设置环境变量
set XIAOHEIHE_EDGE=C:\path\to\msedge.exe
set XIAOHEIHE_PROFILE=D:\my_auto_profile

# 3. 准备登录态：把系统 Edge 的登录 cookie 复制到调试 profile 并启动调试浏览器
python setup_debug_profile.py

# 4. 首次登录：脚本打开小黑盒，点右上角「登录」弹二维码，用 App 扫码
python login_helper.py

# 5. 常驻服务：打开编辑器并填充 `xiaoheihe_article.md`，此后文件一变就原地重填
python -u publish_server.py
```

## 使用方式

| 脚本 | 作用 |
|---|---|
| `config.py` | 集中配置（Edge 路径、profile 目录、CDP 端口），可用环境变量覆盖 |
| `setup_debug_profile.py` | 复制系统 Edge 登录态到调试 profile 并以调试模式启动 |
| `login_helper.py` | 引导扫码登录，登录态保存在调试 profile |
| `publish_server.py` | 常驻服务：填充 + 监听文章文件变化原地更新 |
| `publish_to_xiaoheihe.py` | 一键启动填充；`--update` 模式附加到已打开浏览器原地重填 |

### 准备文章内容

仓库不附带文章内容，请自行创建 `xiaoheihe_article.md`（与脚本同目录）：

```markdown
# 这里是文章标题（第一行以 # 开头）

这里是正文，支持 markdown 语法（## 小标题、- 列表、> 引用、**加粗**）。
```

### 原地更新（不重开浏览器）

```bash
# 方式一：常驻服务（推荐，自动监听文件变化）
python -u publish_server.py

# 方式二：单次更新（附加到已打开的浏览器）
python publish_to_xiaoheihe.py --update
```

修改 `xiaoheihe_article.md` 后，编辑器会自动重填（服务模式），或手动运行 `--update`。

### 用 AI Agent 实现自动化

这套脚本适合由 AI Agent（如 Claude、GitHub Copilot、Reasonix 等）编排调用，形成「AI 撰写文章 → 脚本自动填充 → 人工确认发布」的自动化流水线：

1. **AI 生成内容**：AI Agent 将文章写入 `xiaoheihe_article.md`（第一行 `# ` 为标题，其余为正文）
2. **首次登录**：运行 `python login_helper.py`，用户扫码登录一次，登录态存入调试 profile
3. **启动服务**：运行 `python -u publish_server.py`，浏览器自动打开小黑盒编辑器并填充内容
4. **持续修改**：AI 每次改写 `xiaoheihe_article.md`，常驻服务检测到变化后**在原编辑器标签页原地重填**，无需重新登录、不会新建草稿
5. **人工发布**：内容就绪后由用户在浏览器中点击「发布」（脚本刻意不自动点击，避免误发）

典型 AI Agent 对话式用法：

```text
用户：帮我把文章发到小黑盒
AI：  1. 已生成文章内容到 xiaoheihe_article.md
      2. 正在启动浏览器并打开小黑盒编辑器…
      3. 内容已填充，请检查后点击「发布」
```

> 提示：AI Agent 调用脚本前，请先确认调试 profile 已登录（运行过一次 `login_helper.py`）；否则会提示「未找到『发布内容』按钮」。

## 原理说明

- 新版 Chromium/Edge 在未指定 `--user-data-dir` 时会**禁用 remote debugging**，因此必须使用独立 profile
- Edge cookie 加密密钥存放在 `Local State`（基于 Windows 用户账户的 DPAPI 加密），同一用户下复制后仍可解密，从而实现登录态复用
- 内容修改一律在原编辑器标签页内进行（Ctrl+A 覆盖），不会新建草稿

## 注意事项

- 复制 profile 会包含你的浏览器登录信息，请勿将调试 profile 目录或本仓库提交内容之外的数据公开
- 文章内容文件 `xiaoheihe_article.md` 由用户自行创建与保管，不随仓库分发
- 发布的文章内容由用户自行确认，本工具不自动点击「发布」
- 仅支持 Windows（依赖 `taskkill` 与 Edge 路径）
