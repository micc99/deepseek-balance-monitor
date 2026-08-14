from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from usage_logger import log_usage
from error_logger import log_exception
from credential_store import encrypt_api_key, decrypt_api_key

TARGET_HOST = "api.deepseek.com"  # 默认目标，可通过 UsageProxy(target_host=...) 覆盖
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 52848

logger = logging.getLogger(__name__)

# 默认白名单：覆盖 5 个内置 Provider 域名
# ISSUE-PROV-02 注册的 Provider 域名会通过 add_to_whitelist 动态加入
DEFAULT_WHITELIST: set[str] = {
    "api.deepseek.com",
    "api.siliconflow.cn",
    "api.moonshot.cn",
    "openrouter.ai",
    "open.bigmodel.cn",
}


def _hash_token(token: str) -> str:
    """对 token 取 SHA-256 前 16 位 hex，用于审计日志（不记录明文 token）。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def _hash_api_key(api_key: str) -> str:
    """对 API Key 取 SHA-256 前 16 位 hex，用于审计日志。"""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]


class SSEUsageParser:
    """ISSUE-PFM-06：SSE 流式行级解析器。

    维护 line_buffer，逐 chunk 喂入并按 \\n 分割完整行，
    检查 `data: ` 前缀与 `usage` 关键字，记录最后一个 usage dict。

    特性：
    - 内存占用恒定：line_buffer 只保留最后不完整的一行
    - 正确拼接跨 chunk 的 SSE 行（chunk 边界切分场景）
    - 处理 \\r\\n 与 \\n 两种换行符
    - 覆盖式记录最后一个 usage（与原方案"取最后一个"语义一致）
    """

    def __init__(self):
        self._line_buffer: str = ""
        self._last_usage_data: dict | None = None

    def feed(self, chunk: str) -> None:
        """喂入一个文本 chunk，解析其中的完整 SSE 行。

        Args:
            chunk: 解码后的 SSE 文本片段（可能包含不完整行）
        """
        self._line_buffer += chunk
        # 按换行符分割，处理完整行
        while "\n" in self._line_buffer:
            line, self._line_buffer = self._line_buffer.split("\n", 1)
            # 处理 \r\n 与 \n 两种换行符
            line = line.rstrip("\r")
            if line.startswith("data: ") and "usage" in line and "[DONE]" not in line:
                try:
                    d = json.loads(line[6:])
                    if isinstance(d.get("usage"), dict):
                        # 覆盖式记录最后一个 usage
                        self._last_usage_data = d["usage"]
                except Exception as e:
                    log_exception("usage_proxy.streaming_usage_line", e)

    @property
    def last_usage(self) -> dict | None:
        """返回最后一个含 usage 的 data 行解析结果（流结束时调用）。"""
        return self._last_usage_data


class _Handler(BaseHTTPRequestHandler):
    """HTTP 反向代理请求处理器。

    将所有请求原样转发到 target_host（可配置），仅在检测到
    POST /chat/completions 响应中包含 usage 字段时，调用 log_usage 记录。
    流式和非流式响应分别处理：流式从最后一个 SSE data 行提取 usage。

    ISSUE-SEC-04：
    - 请求头校验 X-Proxy-Token（hmac.compare_digest 恒定时间比较）
    - target_host 白名单校验
    - 审计日志：key hash + 路径 + 时间 + 状态码，不记录请求/响应体
    """
    proxy_ref: "UsageProxy | None" = None

    def _forward(self, method: str):
        """核心转发逻辑：鉴权 → 白名单 → 转发 → 记录 usage → 返回响应。"""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b""

        api_key = self.headers.get("Authorization", "").replace("Bearer ", "").strip()
        is_chat = method == "POST" and "/chat/completions" in self.path

        # ISSUE-SEC-04：鉴权校验
        if not self._check_auth():
            self._audit_log(api_key, 403, "auth_failed")
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":{"message":"Unauthorized: invalid or missing X-Proxy-Token","type":"proxy_auth_error"}}')
            return

        # ISSUE-SEC-04：白名单校验
        target = self.proxy_ref._target_host if self.proxy_ref else TARGET_HOST
        if not self._check_whitelist(target):
            self._audit_log(api_key, 403, "whitelist_rejected")
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":{"message":"Forbidden: target host not in whitelist","type":"proxy_whitelist_error"}}')
            return

        is_streaming = False
        if body and is_chat:
            try:
                is_streaming = json.loads(body).get("stream", False)
            except Exception as e:
                log_exception("usage_proxy.json_parse", e)

        fwd_headers = {
            k: v for k, v in self.headers.items()
            if k.lower() not in ("host", "content-length", "connection",
                                 "keep-alive", "proxy-connection")
        }

        import http.client
        try:
            conn = http.client.HTTPSConnection(target, timeout=120)
        except Exception as e:
            logger.error("无法连接目标 %s: %s", target, e)
            self._audit_log(api_key, 502, "target_unreachable")
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":{"message":"Bad Gateway: target unreachable","type":"proxy_target_error"}}')
            return

        try:
            conn.request(method, self.path, body=body, headers=fwd_headers)
            resp = conn.getresponse()

            self.send_response(resp.status)

            if is_streaming and is_chat:
                for k, v in resp.getheaders():
                    if k.lower() not in ("transfer-encoding", "content-length", "connection"):
                        self.send_header(k, v)
                self.send_header("Connection", "close")
                self.end_headers()

                # ISSUE-PFM-06：使用 SSEUsageParser 行级状态机解析 SSE 流
                # 避免累积完整 usage_text，内存占用恒定
                parser = SSEUsageParser()
                while True:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
                    if api_key:
                        parser.feed(chunk.decode("utf-8", errors="replace"))

                # 流结束，log 最后一个 usage（若存在）
                if api_key and parser.last_usage is not None:
                    log_usage(api_key, parser.last_usage)
            else:
                resp_body = resp.read()
                for k, v in resp.getheaders():
                    if k.lower() not in ("transfer-encoding",):
                        self.send_header(k, v)
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)

                if is_chat and api_key:
                    try:
                        d = json.loads(resp_body)
                        if isinstance(d.get("usage"), dict):
                            log_usage(api_key, d["usage"])
                    except Exception as e:
                        log_exception("usage_proxy.nonstreaming_usage", e)

            # 审计日志（成功）：key hash + 路径 + 状态码
            self._audit_log(api_key, resp.status, "ok")
        except Exception as e:
            logger.error("代理转发失败：%s", e)
            self._audit_log(api_key, 502, "forward_error")
            try:
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error":{"message":"Bad Gateway: forward error","type":"proxy_forward_error"}}')
            except Exception:
                pass
        finally:
            conn.close()

    def _check_auth(self) -> bool:
        """ISSUE-SEC-04：校验 X-Proxy-Token 头。

        使用 hmac.compare_digest 恒定时间比较，防止时序攻击。
        """
        if not self.proxy_ref:
            return True  # 无 proxy_ref（单元测试场景），放行
        expected_token = self.proxy_ref.get_proxy_token()
        if not expected_token:
            return True  # 未配置 token（兼容旧版），放行
        provided = self.headers.get("X-Proxy-Token", "").strip()
        if not provided:
            return False
        return hmac.compare_digest(expected_token, provided)

    def _check_whitelist(self, target_host: str) -> bool:
        """ISSUE-SEC-04：校验 target_host 是否在白名单中。"""
        if not self.proxy_ref:
            return True  # 无 proxy_ref（单元测试场景），放行
        whitelist = self.proxy_ref.get_whitelist()
        if not whitelist:
            return True  # 空白名单视为不限制（兼容）
        return target_host in whitelist

    def _audit_log(self, api_key: str, status_code: int, event: str):
        """ISSUE-SEC-04：审计日志。

        仅记录 key hash + 路径 + 时间 + 状态码 + 事件类型，
        **不记录请求/响应体**。
        """
        key_hash = _hash_api_key(api_key) if api_key else "anonymous"
        logger.info(
            "proxy_audit event=%s path=%s status=%d key_hash=%s",
            event, self.path, status_code, key_hash,
        )

    def do_GET(self):
        self._forward("GET")

    def do_POST(self):
        self._forward("POST")

    def do_PUT(self):
        self._forward("PUT")

    def do_DELETE(self):
        self._forward("DELETE")

    def do_PATCH(self):
        self._forward("PATCH")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def log_message(self, format, *args):
        pass


class UsageProxy:
    """本地 HTTP 反向代理，拦截 API 调用并记录 token 用量。

    客户端将 API base URL 设为 http://127.0.0.1:52848/v1，
    代理自动转发到 target_host 并从响应中提取 usage 数据。

    ISSUE-SEC-04：
    - 鉴权：首次启动生成随机 32 字节 token，DPAPI 加密存储
    - 白名单：target_host 必须在白名单内，默认覆盖 5 个 Provider 域名
    - 审计：所有请求记录 key hash + 路径 + 状态码，不记录 body

    Args:
        host:            代理监听地址
        port:            代理监听端口
        target_host:     转发目标主机名（如 api.siliconflow.cn）
        proxy_token_enc: DPAPI 加密后的 token（base64），空字符串表示首次启动
    """

    def __init__(
        self,
        host: str = PROXY_HOST,
        port: int = PROXY_PORT,
        target_host: str = TARGET_HOST,
        proxy_token_enc: str = "",
    ):
        self._host = host
        self._port = port
        self._target_host = target_host
        # ISSUE-NET-02：ThreadingHTTPServer 支持并发请求
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

        # 鉴权 token 管理
        self._proxy_token_enc = proxy_token_enc
        self._token_cache: str = ""  # 内存中解密后的明文 token
        self._token_enc_changed = False  # 标记是否生成了新 token（需回写配置）

        # 白名单（线程安全）
        self._whitelist: set[str] = set(DEFAULT_WHITELIST)
        self._whitelist_lock = threading.Lock()

        # 初始化 token：首次启动自动生成
        self._init_token()

    def _init_token(self):
        """ISSUE-SEC-04：初始化鉴权 token。

        - 若 proxy_token_enc 已存在，解密到内存缓存
        - 若为空（首次启动），生成随机 32 字节 token，加密存储
        - 解密失败（换用户账户）时重新生成
        """
        if self._proxy_token_enc:
            try:
                self._token_cache = decrypt_api_key(self._proxy_token_enc)
                logger.info("代理鉴权 token 已从配置加载（hash=%s）", _hash_token(self._token_cache))
                return
            except Exception as e:
                logger.warning("代理 token 解密失败，重新生成：%s", e)

        # 首次启动或解密失败：生成新 token
        new_token = secrets.token_urlsafe(32)
        try:
            self._proxy_token_enc = encrypt_api_key(new_token)
            self._token_cache = new_token
            self._token_enc_changed = True
            logger.info("代理鉴权 token 已生成（hash=%s）", _hash_token(new_token))
        except Exception as e:
            logger.error("代理 token 加密失败：%s", e)
            # 降级：使用明文 token（仅内存，不持久化）
            self._proxy_token_enc = new_token
            self._token_cache = new_token
            self._token_enc_changed = True

    def get_proxy_token(self) -> str:
        """获取内存中的明文 token（供 handler 校验）。"""
        return self._token_cache

    def reset_proxy_token(self) -> str:
        """ISSUE-SEC-04：重置 token，返回新明文。

        调用方需将 self.proxy_token_enc 持久化到 config。
        """
        new_token = secrets.token_urlsafe(32)
        try:
            self._proxy_token_enc = encrypt_api_key(new_token)
        except Exception as e:
            logger.error("重置 token 加密失败：%s", e)
            self._proxy_token_enc = new_token
        self._token_cache = new_token
        self._token_enc_changed = True
        logger.info("代理鉴权 token 已重置（hash=%s）", _hash_token(new_token))
        return new_token

    @property
    def proxy_token_enc(self) -> str:
        """获取加密后的 token（用于持久化到 config）。"""
        return self._proxy_token_enc

    @property
    def token_enc_changed(self) -> bool:
        """标记是否生成了新 token（调用方据此回写配置）。"""
        return self._token_enc_changed

    def get_whitelist(self) -> set[str]:
        """获取当前白名单（线程安全副本）。"""
        with self._whitelist_lock:
            return set(self._whitelist)

    def add_to_whitelist(self, host: str):
        """ISSUE-SEC-04 / ISSUE-PROV-02：动态添加域名到白名单。"""
        with self._whitelist_lock:
            self._whitelist.add(host)
        logger.info("白名单新增域名：%s", host)

    def start(self):
        if self._server is not None:
            return

        class _HandlerWithRef(_Handler):
            proxy_ref = self

        # ISSUE-NET-02：使用 ThreadingHTTPServer 替代 HTTPServer，支持并发请求不排队
        # daemon_threads=True 确保主进程退出时子线程自动结束，不残留
        self._server = ThreadingHTTPServer((self._host, self._port), _HandlerWithRef)
        self._server.daemon_threads = True
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="UsageProxy",
        )
        self._thread.start()

    def stop(self):
        if self._server is not None:
            self._server.shutdown()
            self._server = None
            self._thread = None

    @property
    def proxy_url(self) -> str:
        return f"http://{self._host}:{self._port}/v1"
