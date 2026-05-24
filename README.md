# DeepSeek Balance Monitor

多 AI 平台 API 余额监控桌面工具，支持任务栏悬浮窗实时查看余额。

## 功能

- **多平台支持** — DeepSeek、SiliconFlow、Moonshot、OpenRouter、智谱 AI
- **主窗口管理** — 添加/删除账号，查看详细余额信息
- **悬浮窗模式** — 最小化到桌面悬浮窗，实时显示余额
- **自动刷新** — 可配置刷新间隔（默认 60 秒）
- **系统托盘** — 后台运行，托盘菜单快速操作
- **开机自启** — 支持 Windows 开机自启动
- **深色/浅色主题** — 内置两种界面主题
- **动画效果** — 自定义波纹动画颜色

## 安装

### 方式一：下载打包版

从 [Releases](https://github.com/micc99/deepseek-balance-monitor/releases) 下载最新版 `DeepSeekBalanceMonitor.exe`，双击运行。

### 方式二：源码运行

**环境要求：** Python 3.10+

```bash
# 克隆仓库
git clone https://github.com/micc99/deepseek-balance-monitor.git
cd deepseek-balance-monitor

# 安装依赖
pip install -r requirements.txt

# 运行
python main.py
```

## 使用说明

1. **添加账号**：启动后在主窗口点击"添加"，填入 API Key 和备注名
2. **查看余额**：程序自动查询所有账号余额
3. **切换到悬浮窗**：点击"最小化到悬浮窗"或直接关闭主窗口
4. **回到主窗口**：双击悬浮窗或右键打开"显示主窗口"
5. **设置**：可修改刷新间隔、主题颜色、波纹动画颜色

## 支持的 Provider

| Provider | API 地址 |
|----------|---------|
| DeepSeek | `https://api.deepseek.com` |
| SiliconFlow | `https://api.siliconflow.cn` |
| Moonshot | `https://api.moonshot.cn` |
| OpenRouter | `https://openrouter.ai/api` |
| 智谱 AI (ZhipuAI) | `https://open.bigmodel.cn/api/llm` |

## 打包构建

```bash
pip install pyinstaller
pyinstaller --windowed --icon=deepseek-balance-monitor.ico --name "DeepSeekBalanceMonitor v1.1" main.py
```

## 技术栈

- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) — UI 框架
- [Pillow](https://python-pillow.org/) — 图像处理
- [pystray](https://github.com/moses-palmer/pystray) — 系统托盘
- [requests](https://requests.readthedocs.io/) — HTTP 请求

## 许可证

[MIT](LICENSE)
