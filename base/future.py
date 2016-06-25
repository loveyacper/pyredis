#!/usr/bin/env python
#
# Copyright 2012 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging

class ReturnValueIgnoredError(Exception):
    pass

class Future(object):
    """Placeholder for an asynchronous result.

    A ``Future`` encapsulates the result of an asynchronous
    operation.  In synchronous applications ``Futures`` are used
    to wait for the result from a thread or process pool;
    """
    def __init__(self):
        self._done = False
        self._result = None
        self._exc_info = None

        self._callbacks = []

    def done(self):
        return self._done

    def result(self):
        """If the operation succeeded, return its result.  If it failed,
        re-raise its exception.  """
        if self._result is not None:
            return self._result
        if self._exc_info is not None:
            raise_exc_info(self._exc_info)
        self._check_done()
        return self._result

    def exception(self):
        """If the operation raised an exception, return the `Exception`
        object.  Otherwise returns None.  """
        if self._exc_info is not None:
            return self._exc_info[1]
        else:
            self._check_done()
            return None

    def add_done_callback(self, fn):
        """Attaches the given callback to the `Future`.

        It will be invoked with the `Future` as its argument when the Future
        has finished running and its result is available.  In Tornado
        consider using `.IOLoop.add_future` instead of calling
        `add_done_callback` directly.
        """
        if self.done():
            fn(self)
        else:
            self._callbacks.append(fn)

    def set_result(self, result):
        """Sets the result of a Future """
        self._result = result
        self._set_done()

    def set_exception(self, exception):
        """Sets the exception of a Future."""
        self.set_exc_info(
            (exception.__class__,
             exception,
             getattr(exception, '__traceback__', None)))

    def exc_info(self):
        """Returns a tuple in the same format as `sys.exc_info` or None.  """
        return self._exc_info

    def set_exc_info(self, exc_info):
        """Sets the exception information of a Future """
        self._exc_info = exc_info

        try:
            self._set_done()
        finally:
            pass

        self._exc_info = exc_info

    def _check_done(self):
        if not self._done:
            raise Exception("DummyFuture does not support blocking for results")

    def _set_done(self):
        if self._done:
            raise Exception("Future is already done")

        self._done = True
        for cb in self._callbacks:
            try:
                cb(self)
            except Exception:
                logging.exception('Exception in callback %r for %r',
                                  cb, self)
        self._callbacks = None


TracebackFuture = Future

def is_future(x):
    return isinstance(x, Future)


def chain_future(a, b):
    """Chain two futures together so that when a completes, so does b """
    def copy(future):
        assert future is a
        if b.done():
            return
        if (isinstance(a, TracebackFuture) and
                isinstance(b, TracebackFuture) and
                a.exc_info() is not None):
            b.set_exc_info(a.exc_info())
        elif a.exception() is not None:
            b.set_exception(a.exception())
        else:
            b.set_result(a.result())

    a.add_done_callback(copy)
