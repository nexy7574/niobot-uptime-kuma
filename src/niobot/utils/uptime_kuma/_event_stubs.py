import typing
if typing.TYPE_CHECKING:
    from httpx import Response
    from .monitor import KumaMonitor


async def kuma_push(monitor: "KumaMonitor", response: "Response"):
    """
    Dispatched when `KumaMonitor.push` completes successfully.

    :param monitor: The monitor instance
    :param response: The http response
    """


async def kuma_autopush_start(monitor: "KumaMonitor"):
    """
    Dispatched when the monitor's loop begins an autopush.

    :param monitor: The monitor instance
    """


async def kuma_autopush_end(monitor: "KumaMonitor", response: "Response"):
    """
    Dispatched when the monitor's loop completes an autopush.

    :param monitor: The monitor instance
    :param response: The http response from push()
    """


async def kuma_autopush_error(monitor: "KumaMonitor", error: Exception):
    """
    Dispatched when the monitor's loop encounters an error while autopushing.

    :param monitor: The monitor instance
    :param error: The exception raised
    """
