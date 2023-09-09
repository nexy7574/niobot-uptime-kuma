"""
This module is designed to ease sending uptime pings to a self-hosted uptime kuma monitor.

- [Uptime Kuma](https://github.com/louislam/uptime-kuma)
"""
import collections

import asyncio
import time

import httpx
import logging
import typing as t
import importlib.metadata

import niobot

try:
    import h2
    http2 = True
except ImportError:
    http2 = False


class KumaMonitor:
    """
    Represents a monitor on an UptimeKuma instance.
    This class only works with the `push` monitor type.

    !!! warning "Low-volume latency reporting"
        If `include_latency` is `True`, and your client does not receive many RoomMessage events, you will likely
        see the same average ping being pushed to your monitor. This is to be expected.

    :param client: The NioBot client to use.
    :param push_url: The target monitor URL to push to
    :param interval: The interval to push on. Defaults to 60 seconds.
    :param session: The httpx session to use. Will create one with sane defaults if not provided.
    :param friendly_name: A friendly name for this monitor to appear in logs. Defaults to "url[netloc]/url[path]"
    :param status_getter: A function that will return either True (up) or False (down). By default, uses a function
    that will always return True.
    :param msg_getter: A function that will return a custom message to push with. By default, uses a function that
    will always return "OK".
    :param include_latency: Whether to include the average event latency in the push to display on the graph.
    """

    DEFAULT_USER_AGENT = "niobot-uptime-kuma (%s, https://github.com/nexy7574/niobot-uptime-kuma); %s" % (
        importlib.metadata.version("niobot-uptime-kuma"),
        "python-httpx/{}".format(httpx.__version__)
    )

    def __init__(
            self,
            client: niobot.NioBot,
            push_url: str,
            interval: t.Union[float, int] = 60.0,
            *,
            session: httpx.AsyncClient = None,
            friendly_name: str = None,
            status_getter: t.Callable[["KumaMonitor"], bool] = None,
            msg_getter: t.Callable[["KumaMonitor"], t.Optional[str]] = None,
            include_latency: bool = True
    ):
        if not friendly_name:
            url = httpx.URL(push_url)
            friendly_name = "%s%s" % (url.netloc.decode(), url.path)
        self.name = friendly_name
        self.push_url: str = push_url
        self.__interval = float(interval)
        self.client = client
        self.http = session or httpx.AsyncClient(
            headers={
                "User-Agent": self.DEFAULT_USER_AGENT
            },
            http2=http2
        )
        self.log = logging.getLogger("niobot.uptimekuma.%s" % self.name)

        self._last_push = None
        self.status_getter = status_getter or self._status_getter
        self.msg_getter = msg_getter or self._msg_getter
        self.include_latency = include_latency

        self._history = collections.deque(maxlen=100)
        self._task: t.Optional[asyncio.Task] = None

        self.client.add_event_listener("message", self._message_listener)

    def __del__(self):
        self.client.remove_event_listener(self._message_listener)

    def _message_listener(self, message: niobot.RoomMessageText):
        self._history.append(self.client.latency(message))

    @property
    def average_latency(self) -> float:
        """Returns the average latency in milliseconds over the last 100 messages"""
        return round((sum(self._history) / len(self._history)), 2)

    @staticmethod
    def _status_getter(_):
        # Dummy function that always returns True
        return True

    @staticmethod
    def _msg_getter(_):
        # Dummy function that always returns "OK"
        return "OK"

    @property
    def last_push(self) -> t.Optional[float]:
        """Returns the last autopush unix timestamp. Can be None if the first push has not yet finished."""
        return self._last_push

    @property
    def next_push(self) -> t.Optional[float]:
        """Returns the next autopush unix timestamp. Will be None if the first push has not finished."""
        if self.last_push is None:
            return
        return self.last_push + self.interval

    @property
    def interval(self) -> float:
        """Returns the current autopush interval in seconds."""
        return self.__interval

    async def push(self) -> httpx.Response:
        """
        Pushes current data to the monitor.

        !!! danger "Getters must not raise exceptions"
            If the status getter or message getter (if used) raise an exception, the push will not be sent. Instead,
            the error will propagate to the caller.

        :return: The `httpx.Response` object.
        """
        status = self.status_getter(self)
        msg = self.msg_getter(self)
        params = {
            "status": "up" if status else "down",
            "msg": msg or None
        }
        if self.include_latency:
            params["ping"] = self.average_latency
        self.log.debug("Pushing to %r with params %r." % (self.push_url, params))
        resp = await self.http.get(self.push_url, params=params)
        if resp.status_code == 200:
            self._last_push = time.time()
        self.log.debug("Pushed to %r with status %r." % (self.push_url, resp.status_code))
        self.client.dispatch("kuma_push", self, resp)
        return resp

    async def main_loop(self) -> None:
        while True:
            self.log.debug("Sending an auto push to %r." % self.push_url)
            self.client.dispatch("kuma_autopush_start", self)
            try:
                response = await self.push()
                self.client.dispatch("kuma_autopush_end", self, response)
            except Exception as e:
                self.client.dispatch("kuma_autopush_error", self, e)
            finally:
                await asyncio.sleep(self.interval)

    def start(self) -> asyncio.Task:
        """
        Starts the monitor's main loop.
        :return: The created task.
        """
        task = asyncio.create_task(self.main_loop())
        self._task = task
        return task

    def stop(self) -> None:
        """
        Stops the monitor's main loop.
        """
        if self._task:
            self._task.cancel()
            self._task = None
