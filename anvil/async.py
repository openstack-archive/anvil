# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2015 Yahoo! Inc. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import sys
import threading

from concurrent import futures

import six
from six.moves import queue as compat_queue
from six.moves import range as compat_range

from anvil import log as logging

LOG = logging.getLogger(__name__)

_TOMBSTONE = object()


def _chained_worker(ident, shared_death, queue, futs):
    while not shared_death.is_set():
        w = queue.get()
        if w is _TOMBSTONE:
            queue.put(w)
            for fut in futs:
                fut.cancel()
            break
        else:
            func, fut = w
            if fut.set_running_or_notify_cancel():
                try:
                    result = func()
                except BaseException:
                    LOG.exception("Worker %s dying...", ident)
                    exc_type, exc_val, exc_tb = sys.exc_info()
                    if six.PY2:
                        fut.set_exception_info(exc_val, exc_tb)
                    else:
                        fut.set_exception(exc_val)
                    # Stop all other workers from doing any more work...
                    shared_death.set()
                    for fut in futs:
                        fut.cancel()
                else:
                    fut.set_result(result)


class ChainedWorkerExecutor(object):
    def __init__(self, max_workers):
        self._workers = []
        self._max_workers = int(max_workers)
        self._queue = compat_queue.Queue()
        self._death = threading.Event()

    def run(self, funcs):
        if self._workers:
            raise RuntimeError("Can not start another run with %s"
                               " existing workers" % (len(self._workers)))
        self._queue = compat_queue.Queue()
        self._death.clear()
        futs = []
        for i in compat_range(0, self._max_workers):
            w = threading.Thread(target=_chained_worker,
                                 args=(i + 1, self._death,
                                       self._queue, futs))
            w.daemon = True
            w.start()
            self._workers.append(w)
        for func in funcs:
            fut = futures.Future()
            futs.append(fut)
            self._queue.put((func, fut))
        return futs

    def wait(self):
        self._queue.put(_TOMBSTONE)
        while self._workers:
            w = self._workers.pop()
            w.join()
