from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional


"""应用级事件总线：模块间解耦的发布/订阅中枢。

ISSUE-ARC-02：MainWindow 原通过 6 个 setter 注入回调（set_refresh_callback 等），
App 加载阶段与加载完成后需反复换绑，耦合度高。改用事件总线后：
- UI 组件只 publish（"发生了什么"），不关心谁消费
- App 在 _wire_events 中一次性订阅，按 _loaded 状态门分派
- 新功能（THM-05 主题重着色、ARC-06 Provider 注册广播）只加订阅方，不改发布方

线程模型（硬约束，见 AGENTS.md §6.1）：
- publish 在调用方线程同步执行 handler（本模块不做线程跳转）
- 后台线程（scheduler/proxy/托盘）publish 后，UI 侧订阅方必须通过
  widget.after(0, ...) 把 UI 操作调度回 Tk 主线程，没有例外
- subscribe/unsubscribe/publish 均线程安全；handler 快照后在锁外调用，
  handler 内再次 publish/subscribe 不会死锁、不会影响本轮派发

隐私约定：DEBUG 日志只记录事件名/来源/负载键名，不记录负载值
（负载可能含账户备注等用户数据，避免进入日志文件）。
"""

logger = logging.getLogger(__name__)

# ISSUE-ARC-02：全局事件名常量。发布方与订阅方共同引用，禁止裸字符串。
EVENT_REFRESH_REQUESTED = "refresh_requested"
EVENT_SETTINGS_CHANGED = "settings_changed"
EVENT_ACCOUNT_ADDED = "account_added"
EVENT_ACCOUNT_DELETED = "account_deleted"
EVENT_ACCOUNT_UPDATED = "account_updated"
EVENT_BALANCE_UPDATED = "balance_updated"
EVENT_THEME_CHANGED = "theme_changed"
EVENT_PROVIDER_REGISTERED = "provider_registered"


@dataclass
class Event:
    """事件对象：名称 + 来源 + 负载（ISSUE-ARC-02 AC3）。

    Attributes:
        name:      事件名，取 EVENT_* 常量
        source:    发布方标识（如 "main_window" / "scheduler" / "theme_manager"）
        payload:   负载字典，键名可进 DEBUG 日志，值不进日志
        timestamp: 发布时刻（time.time()）
    """
    name: str
    source: str = ""
    payload: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


Handler = Callable[[Event], None]


class EventBus:
    """线程安全的同步事件总线。

    用法：
        bus.subscribe(EVENT_REFRESH_REQUESTED, self._on_refresh)
        bus.publish(EVENT_REFRESH_REQUESTED, source="main_window")

    subscribe 返回反订阅闭包，便于窗口销毁时清理：
        unsubscribe = bus.subscribe(EVENT_THEME_CHANGED, self._on_theme)
        ...
        unsubscribe()
    """

    def __init__(self):
        self._handlers: dict[str, list[Handler]] = {}
        self._lock = threading.RLock()

    def subscribe(self, event: str, handler: Handler) -> Callable[[], None]:
        """订阅事件，返回反订阅函数。

        同一 (event, handler) 重复订阅会去重（幂等），避免重复派发。
        """
        with self._lock:
            handlers = self._handlers.setdefault(event, [])
            if handler not in handlers:
                handlers.append(handler)
        return lambda: self.unsubscribe(event, handler)

    def unsubscribe(self, event: str, handler: Handler):
        """取消订阅。未订阅过则为静默 no-op。"""
        with self._lock:
            handlers = self._handlers.get(event)
            if handlers is None:
                return
            try:
                handlers.remove(handler)
            except ValueError:
                pass
            if not handlers:
                # 空列表回收，避免长期运行下字典膨胀
                del self._handlers[event]

    def publish(
        self,
        event: str,
        payload: Optional[dict] = None,
        source: str = "",
    ) -> Event:
        """发布事件：同步、快照式派发给所有订阅者（锁外调用）。

        - 单个 handler 抛异常不影响其他 handler，异常记录后继续派发
        - handler 内新增的订阅不在本轮生效（快照语义），下轮生效
        - 无订阅者时静默返回（事件允许先发后订的场景：balance_updated）
        """
        evt = Event(name=event, source=source, payload=payload or {})
        logger.debug(
            "事件发布: name=%s source=%s payload_keys=%s",
            evt.name, evt.source, sorted(evt.payload.keys()),
        )
        with self._lock:
            handlers = list(self._handlers.get(event, ()))
        for handler in handlers:
            try:
                handler(evt)
            except Exception as e:
                # 异常隔离：一个订阅方出错不能中断整轮派发
                logger.exception("事件 handler 执行失败: name=%s handler=%r: %s", event, handler, e)
        return evt

    def has_subscribers(self, event: str) -> bool:
        """查询某事件当前是否有订阅者（主要用于测试与诊断）。"""
        with self._lock:
            return bool(self._handlers.get(event))
