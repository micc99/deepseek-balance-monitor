"""ISSUE-ARC-01：App 职责单一化管理器包。

App 类拆分为编排器 + 8 个 Manager（PRD 7.5 / 迁移线 Phase B 脚手架）：
- LifecycleManager    单实例锁 + IPC 唤醒监听
- TrayManager         系统托盘
- HotkeyManager       全局热键
- ThemeCoordinator    主题子系统接线（ThemeCoordinator，底层为 main/theme_manager.py 的 ThemeManager）
- AutostartManager    开机自启 .lnk
- WindowManager       主窗口 ↔ 悬浮窗与余额 UI 更新
- SchedulerManager    调度器生命周期 + 余额快照
- ProxyManager        本地用量代理

约定：Manager 构造函数通过依赖注入接收依赖（config_provider 等访问器
或具体对象），不持有 App 引用；非主线程的 UI 触达一律经 WindowManager
的 after(0) 调度（线程硬约束见 AGENTS.md §6.1）。
"""
