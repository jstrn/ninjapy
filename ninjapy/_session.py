import socket
import time
from typing import Optional

from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection


def _build_socket_options() -> list[tuple[int, int, int]]:
    """Enable TCP keepalive so dead paths are detected sooner."""
    socket_options = list(HTTPConnection.default_socket_options)
    socket_options.append((socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1))

    if hasattr(socket, "TCP_KEEPIDLE"):
        socket_options.extend(
            [
                (socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30),
                (socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10),
                (socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3),
            ]
        )
    elif hasattr(socket, "TCP_KEEPALIVE"):
        socket_options.append((socket.IPPROTO_TCP, socket.TCP_KEEPALIVE, 30))

    return socket_options


class ExpiringHTTPAdapter(HTTPAdapter):
    """Recycle pooled connections periodically to avoid stale idle sockets."""

    def __init__(
        self,
        *args: object,
        pool_max_age: Optional[float] = 60.0,
        **kwargs: object,
    ) -> None:
        self.pool_max_age = pool_max_age
        self._last_pool_refresh = time.monotonic()
        self._socket_options = _build_socket_options()
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args: object, **kwargs: object) -> None:
        kwargs.setdefault("socket_options", self._socket_options)
        super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args: object, **kwargs: object):  # type: ignore[override]
        kwargs.setdefault("socket_options", self._socket_options)
        return super().proxy_manager_for(*args, **kwargs)

    def send(self, request, *args, **kwargs):  # type: ignore[override]
        self._refresh_pools_if_needed()
        return super().send(request, *args, **kwargs)

    def _refresh_pools_if_needed(self) -> None:
        if self.pool_max_age is None or self.pool_max_age <= 0:
            self.close()
            self._last_pool_refresh = time.monotonic()
            return

        now = time.monotonic()
        if now - self._last_pool_refresh >= self.pool_max_age:
            self.close()
            self._last_pool_refresh = now
