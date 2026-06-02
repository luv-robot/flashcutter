from dataclasses import dataclass
from queue import Queue
from threading import Thread
from typing import Callable, Optional
import traceback


@dataclass
class QueuedTask:
    task_id: int
    runner: Callable[[int], None]


class TaskQueue:
    def __init__(self) -> None:
        self._queue: Queue[QueuedTask] = Queue()
        self._worker: Optional[Thread] = None
        self.last_error: Optional[str] = None

    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._worker = Thread(target=self._run, name="flashcutter-task-queue", daemon=True)
        self._worker.start()

    def enqueue(self, task_id: int, runner: Callable[[int], None]) -> None:
        self.start()
        self._queue.put(QueuedTask(task_id=task_id, runner=runner))

    def pending_count(self) -> int:
        return self._queue.qsize()

    def _run(self) -> None:
        while True:
            queued_task = self._queue.get()
            try:
                try:
                    queued_task.runner(queued_task.task_id)
                except Exception:
                    self.last_error = traceback.format_exc()
                    print(self.last_error, flush=True)
            finally:
                self._queue.task_done()


task_queue = TaskQueue()
