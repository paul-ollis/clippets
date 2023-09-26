"""Higher level asynio task management."""
from __future__ import annotations

import asyncio
import sys
import traceback

tasks: dict[asyncio.Task, None] = {}
monitor_task: asyncio.Task | None = None


async def watchdog():
    """Detect failures of other tasks."""
    while tasks:
        to_be_dropped = set()
        for task in tasks:
            # print('Check', task, task.done(), file=sys.__stdout__)
            if not task.done():
                continue

            to_be_dropped.add(task)
            exc = None if task.cancelled() else task.exception()
            if exc:
                traceback.print_exception(exc, file=sys.__stderr__)
                task.print_stack(file=sys.__stderr__)
                sys.exit(str(exc))

        for task in to_be_dropped:
            tasks.pop(task)

        # print('Check complete', file=sys.__stdout__)
        await asyncio.sleep(0.1)


def create_task(coro, *, name=None, context=None) -> asyncio.Task:
    """Create a task and add to the set of monitored tasks."""
    global monitor_task

    task = asyncio.create_task(coro, name=name, context=context)
    tasks[task] = None

    if monitor_task is None:
        monitor_task = asyncio.create_task(watchdog())

    return task
