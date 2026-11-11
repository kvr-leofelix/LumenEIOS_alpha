import asyncio
import json
import logging
from contextvars import ContextVar, Token
from typing import Awaitable, Callable, Optional

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str, int, int], None]
_progress: ContextVar[Optional[ProgressCallback]] = ContextVar("lumeneios_progress", default=None)


def report_progress(step: str, label: str, done: int, total: int) -> None:
    callback = _progress.get()
    if callback is not None:
        callback(step, label, done, total)


def use_progress(callback: ProgressCallback) -> Token:
    return _progress.set(callback)


def reset_progress(token: Token) -> None:
    _progress.reset(token)


def stream_job(work: Callable[[], Awaitable[object]]) -> StreamingResponse:
    """Run work and emit each real progress report as a server-sent event."""
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def callback(step: str, label: str, done: int, total: int) -> None:
        event = {"kind": "progress", "step": step, "label": label, "done": done, "total": total}
        try:
            on_loop = asyncio.get_running_loop() is loop
        except RuntimeError:
            on_loop = False
        if on_loop:
            queue.put_nowait(event)
        else:
            loop.call_soon_threadsafe(queue.put_nowait, event)

    async def run() -> None:
        token = use_progress(callback)
        try:
            result = await work()
            await asyncio.sleep(0)
            await queue.put({"kind": "complete", "result": result})
        except HTTPException as exc:
            message = exc.detail if isinstance(exc.detail, str) else "The request failed."
            await asyncio.sleep(0)
            await queue.put({"kind": "error", "status": exc.status_code, "message": message})
        except Exception:
            logger.exception("Background job failed")
            await asyncio.sleep(0)
            await queue.put({"kind": "error", "status": 500, "message": "The process failed."})
        finally:
            reset_progress(token)
            await queue.put(None)

    task = asyncio.create_task(run())

    async def events():
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
