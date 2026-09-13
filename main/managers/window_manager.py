from __future__ import annotations

import logging
from typing import Callable, Optional

from config import AppConfig
from floating_window import FloatingWindow
from main_window import MainWindow
from scheduler import BalanceResult


"""主窗口 ↔ 悬浮窗生命周期与余额 UI 更新（ISSUE-ARC-01，原 App 内联逻辑收编）。

线程模型（AGENTS.md §6.1）：本类方法默认在 Tk 主线程调用；后台线程
（IPC 监听、调度器回调）入口（handle_show_signal / post_balance_update）
内部经 after(0) 调度回主线程。

悬浮窗刷新依赖调度器的 last_results 与最近更新时间，经访问器注入，
避免持有 App 引用；调度器未就绪时刷新降级为空显示（修复原实现
加载期最小化会触碰 None.scheduler 的潜在崩溃）。
"""

logger = logging.getLogger(__name__)


class WindowManager:
    """双窗体系的创建、切换与余额刷新。"""

    def __init__(
        self,
        config_provider: Callable[[], AppConfig],
        get_last_results: Callable[[], dict],
        get_refresh_now: Callable[[], Optional[Callable]],
        get_history: Callable[[], object],
        on_exit: Callable[[], None],
        event_bus=None,
    ):
        self._config_provider = config_provider
        self._get_last_results = get_last_results
        self._get_refresh_now = get_refresh_now
        self._get_history = get_history
        self._on_exit = on_exit
        self._event_bus = event_bus  # ISSUE-THM-05：图表窗订阅主题变更用
        self.main_window: MainWindow | None = None
        self.floating_window: FloatingWindow | None = None
        self._pending_show = False
        # 最近一次余额更新时间（UI 展示状态，原 App._last_update_time 收编）
        self._last_update_time: float = 0.0

    def get_last_update_time(self) -> float:
        return self._last_update_time

    # ---- 主窗口 ----

    def create_main_window(
        self,
        event_bus,
        on_switch_to_floating: Callable,
        on_view_curve: Callable,
        on_view_usage: Callable,
        version_title: str,
        on_apply_theme: Callable | None = None,  # ISSUE-THM-06 后由 settings_changed 事件承担
        on_open_theme_editor: Callable | None = None,
    ) -> MainWindow:
        """创建主窗口并接线（原 App.run 前半段）。"""
        self.main_window = MainWindow(
            self._config_provider(),
            event_bus=event_bus,
            on_switch_to_floating=on_switch_to_floating,
            on_apply_theme=on_apply_theme,
            on_view_curve=on_view_curve,
            on_view_usage=on_view_usage,
            on_open_theme_editor=on_open_theme_editor,
        )
        self.main_window.title(version_title)
        return self.main_window

    def rebind_loaded_config(self, proxy_token_provider: Callable[[], str]) -> None:
        """后台加载完成后换绑窗口的 config 引用并重建列表（原 _on_loaded 段）。"""
        if not self._main_alive():
            return
        self.main_window._config = self._config_provider()
        self.main_window._rebuild_account_list()
        # ISSUE-ARC-02：刷新/设置已改事件订阅，加载后无需换绑
        # ISSUE-SEC-04：注入 token 提供者，供设置面板展示 token hash
        self.main_window.set_proxy_token_provider(proxy_token_provider)

    def set_status(self, text: str) -> None:
        if self._main_alive():
            self.main_window.set_status(text)

    def show_main(self) -> None:
        """从悬浮窗回到主窗口（原 _show_main）：销毁悬浮窗、保存位置、展示主窗。"""
        if self.floating_window:
            if self.floating_window.winfo_exists():
                self._config_provider().window = self.floating_window.get_position()
                self._save_config()
            self.floating_window.destroy()
            self.floating_window = None

        if self._main_alive():
            self.main_window.deiconify()
            self.main_window.lift()
            self.main_window.focus()
            self.main_window.after(200, self.main_window.start_focus_monitor)

    def post_show_main(self) -> None:
        """托盘/热键线程回调入口：after(0) 回主线程展示主窗。"""
        if self._main_alive():
            self.main_window.after(0, self.show_main)

    def handle_show_signal(self) -> None:
        """IPC show 信号处理（可在监听线程调用）。"""
        if self._main_alive():
            self.main_window.after(0, self.show_main)
        else:
            self._pending_show = True

    def consume_pending_show(self) -> bool:
        """读取并清除 pending_show（主窗创建后由 App 检查一次）。"""
        pending = self._pending_show
        self._pending_show = False
        return pending

    def toggle(self) -> None:
        """热键切换主窗/悬浮窗（原 _toggle_window）。"""
        if self._main_alive():
            if self.main_window.state() == "withdrawn":
                self.main_window.after(0, self.show_main)
            else:
                self.main_window.after(0, self.minimize_to_floating)

    def minimize_to_floating(self) -> None:
        """主窗最小化到悬浮窗（原 _on_minimize_to_floating_safe）。"""
        if self._main_alive():
            self.main_window._on_minimize_to_floating()

    # ---- 悬浮窗 ----

    def show_floating(self) -> None:
        """切换到悬浮窗（原 _show_floating）：复用或重建。"""
        if self.floating_window and self.floating_window.winfo_exists():
            self.floating_window.deiconify()
            self.floating_window.lift()
            self.floating_window.focus()
            self.refresh_floating()
            return

        refresh_now = self._get_refresh_now()
        self.floating_window = FloatingWindow(
            on_restore=self.show_main,
            on_refresh=refresh_now if refresh_now is not None else (lambda: None),
            on_exit=self._on_exit,
        )
        self.floating_window.protocol("WM_DELETE_WINDOW", self._on_floating_close)
        # 原 _init_floating_position：恢复上次悬浮窗位置
        self.floating_window.set_position(self._config_provider().window)
        self.refresh_floating()

    def _on_floating_close(self) -> None:
        if self.floating_window and self.floating_window.winfo_exists():
            self._config_provider().window = self.floating_window.get_position()
        self._on_exit()

    def refresh_floating(self) -> None:
        """用最新余额刷新悬浮窗拼接字符串（原 _refresh_floating）。"""
        if not self._floating_alive():
            return

        config = self._config_provider()
        active_uids = {acc.uid for acc in config.accounts}
        results = self._get_last_results()
        active_parts = []
        other_parts = []
        available_count = 0
        for uid, r in results.items():
            if r.info.status.value == "ok" and r.info.is_available:
                available_count += 1
                display = r.info.total_display
                if uid in active_uids:
                    active_parts.append(display)
                else:
                    other_parts.append(display)

        all_parts = active_parts + other_parts
        total_display = " | ".join(all_parts) if all_parts else "暂无可用余额"
        status = f"更新于 {self._format_time(self._last_update_time)}"
        self.floating_window.update_balance(total_display, available_count, status)

    def save_floating_position(self) -> None:
        """把悬浮窗当前位置写回 config（原 _save_window_position，不落盘）。"""
        if self._floating_alive():
            self._config_provider().window = self.floating_window.get_position()

    # ---- 余额更新 ----

    def post_balance_update(self, result: BalanceResult) -> None:
        """调度器回调入口（后台线程）：post 回主线程更新 UI。"""
        if self._main_alive():
            self.main_window.after(0, self.update_balance, result)

    def update_balance(self, result: BalanceResult) -> None:
        """主线程更新：主窗行余额 + 悬浮窗 + 状态栏时间（原 _update_ui）。"""
        if self.main_window:
            self.main_window.update_account_balance(result)
        self._last_update_time = result.timestamp
        self.refresh_floating()
        if self.main_window:
            self.main_window.set_status(f"上次更新: {self._format_time(self._last_update_time)}")

    def open_curve_window(self, account) -> None:
        """打开单账户余额趋势图（原 App._on_view_curve）。

        PFM-02 门：用量历史未加载完成时警告并忽略。
        """
        if self._get_history() is None:
            logger.warning("用量历史尚未加载完成，无法打开趋势图")
            return
        if self._main_alive():
            from usage_curve_window import BalanceCurveWindow
            BalanceCurveWindow(
                self.main_window,
                account_label=account.label,
                api_key=account.api_key,
                uid=account.uid,
                history=self._get_history(),
                event_bus=self._event_bus,
            )

    def open_usage_window(self) -> None:
        """打开用量概览（原 App._on_view_usage）。"""
        if self._get_history() is None:
            logger.warning("用量历史尚未加载完成，无法打开用量概览")
            return
        if self._main_alive():
            from usage_bar_window import UsageBarWindow
            UsageBarWindow(
                self.main_window,
                history=self._get_history(),
                accounts=self._config_provider().accounts,
                event_bus=self._event_bus,
            )

    # ---- 退出 ----

    def destroy_for_exit(self) -> None:
        """App._quit 的窗口销毁段（保持原顺序与容错）。"""
        try:
            if self.main_window:
                self.main_window.prepare_exit()
                self.main_window.destroy()
            if self.floating_window and self.floating_window.winfo_exists():
                self.floating_window.destroy()
        except Exception as e:
            from error_logger import log_exception
            log_exception("WindowManager.destroy_for_exit", e)

    # ---- 内部工具 ----

    def _main_alive(self) -> bool:
        return bool(self.main_window and self.main_window.winfo_exists())

    def _floating_alive(self) -> bool:
        return bool(self.floating_window and self.floating_window.winfo_exists())

    def _save_config(self) -> None:
        from config import save_config
        save_config(self._config_provider())

    @staticmethod
    def _format_time(ts: float) -> str:
        from datetime import datetime
        return datetime.fromtimestamp(ts).strftime("%H:%M:%S")
