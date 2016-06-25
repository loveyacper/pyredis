"""``tornado.gen`` is a generator-based interface to make it easier to
work in an asynchronous environment.  Code using the ``gen`` module
is technically asynchronous, but it is written as a single generator
instead of a collection of separate functions.

    class GenAsyncHandler(RequestHandler):
        @gen.coroutine
        def get(self):
            http_client = AsyncHTTPClient()
            response = yield http_client.fetch("http://example.com")
            do_something_with_response(response)
            self.render("template.html")

You can also yield a list or dict of ``Futures``, which will be
started at the same time and run in parallel; a list or dict of results will
be returned when they are all finished:

    @gen.coroutine
    def get(self):
        http_client = AsyncHTTPClient()
        response1, response2 = yield [http_client.fetch(url1),
                                      http_client.fetch(url2)]
        response_dict = yield dict(response3=http_client.fetch(url3),
                                   response4=http_client.fetch(url4))
        response3 = response_dict['response3']
        response4 = response_dict['response4']

"""
import collections
import functools
import os
import sys
import logging

from types import GeneratorType

from future import Future, TracebackFuture, is_future, chain_future
from ioloop import IOLoop
#from tornado.concurrent import Future, TracebackFuture, is_future, chain_future
#from tornado import stack_context


class KeyReuseError(Exception):
    pass

class UnknownKeyError(Exception):
    pass

class LeakedCallbackError(Exception):
    pass

class BadYieldError(Exception):
    pass

class ReturnValueIgnoredError(Exception):
    pass

class TimeoutError(Exception):
    """Exception raised by ``with_timeout``."""


def _value_from_stopiteration(e):
    try:
        # StopIteration has a value attribute beginning in py33.
        # So does our Return class.
        return e.value
    except AttributeError:
        pass
    try:
        # Cython backports coroutine functionality by putting the value in
        # e.args[0].
        return e.args[0]
    except (AttributeError, IndexError):
        return None

def coroutine(func, replace_cb = True):
    """Decorator for asynchronous generators.

    Any generator that yields objects from this module must be wrapped in this decorator.

    Coroutines may "return" by raising the special exception Return(value).

    Functions with this decorator return a Future.  Additionally,
    they may be called with a ``callback`` keyword argument, which
    will be invoked with the future's result when it resolves.  If the
    coroutine fails, the callback will not be run and an exception
    will be raised into the surrounding `.StackContext`.  The
    ``callback`` argument is not visible inside the decorated
    function; it is handled by the decorator itself.

    .. warning::

       When exceptions occur inside a coroutine, the exception
       information will be stored in the `.Future` object. You must
       examine the result of the `.Future` object, or the exception
       may go unnoticed by your code. This means yielding the function
       if called from another coroutine, using something like
       `.IOLoop.run_sync` for top-level calls, or passing the `.Future`
       to `.IOLoop.add_future`.

    """
    return _make_coroutine_wrapper(func, replace_cb)


def _make_coroutine_wrapper(func, replace_cb = True):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        future = TracebackFuture()
            
        if replace_cb and 'callback' in kwargs:
            # when the future is done, ie, coroutine is over, then exec callback on ioloop
            callback = kwargs.pop('callback')

            def callback_on_ioloop(fut):
                IOLoop.current().call_next_tick(lambda fut : callback(fut.result()))

            future.add_done_callback(callback_on_ioloop)

        try:
            # call func directly, if this func is generator, then result type is generator
            result = func(*args, **kwargs)
        except (Return, StopIteration) as e:
            print("except Return or StopIteration")
            result = _value_from_stopiteration(e)
        except Exception:
            print("except Exception")
            future.set_exc_info(sys.exc_info())
            return future
        else:
            if isinstance(result, GeneratorType):
                # now coroutine is suspended
                print("try priming coroutine")
                try:
                    yielded = next(result) # priming the generator, and got its first yield expression result
                except (StopIteration, Return) as e: # if got Return or the generator is over
                    print("got StopIteration or Return")
                    future.set_result(_value_from_stopiteration(e)) # generator is over
                except Exception: # other exception, error happened
                    print("got Exception")
                    future.set_exc_info(sys.exc_info()) # generator is over
                else:
                    print("enter Runner")
                    Runner(result, future, yielded) #  still running...
                try:
                    return future
                finally:
                    future = None
        future.set_result(result) # call future callbacks sync
        return future

    return wrapper


class Return(Exception):
    """Special exception to return a value from a `coroutine`.

    If this exception is raised, its value argument is used as the
    result of the coroutine::

        @gen.coroutine
        def fetch_json(url):
            response = yield AsyncHTTPClient().fetch(url)
            raise gen.Return(json_decode(response.body))

    it is never necessary to raise gen.Return().  The return statement can be used instead.
    """
    def __init__(self, value=None):
        super(Return, self).__init__()
        self.value = value
        # Cython recognizes subclasses of StopIteration with a .args tuple.
        self.args = (value,)


class WaitIterator(object):
    """Provides an iterator to yield the results of futures as they finish.
    similar to facebook  coolect futures, via multi function to implement
    Yielding a set of futures like this:

    ``results = yield [future1, future2]``

    pauses the coroutine until both ``future1`` and ``future2`` 
    return, and then restarts the coroutine with the results of both
    futures. If either future is an exception, the expression will
    raise that exception and all the results will be lost.

    !collectAny,  as_complete
    If you need to get the result of each future as soon as possible,
    or if you need the result of some futures even if others produce
    errors, you can use ``WaitIterator``::

      wait_iterator = gen.WaitIterator(future1, future2)
      while not wait_iterator.done():
          try:
              result = yield wait_iterator.next()
          except Exception as e:
              print("Error {} from {}".format(e, wait_iterator.current_future))
          else:
              print("Result {} received from {} at {}".format(
                  result, wait_iterator.current_future,
                  wait_iterator.current_index))

    Because results are returned as soon as they are available the
    output from the iterator *will not be in the same order as the
    input arguments*. If you need to know which future produced the
    current result, you can use the attributes
    ``WaitIterator.current_future``, or ``WaitIterator.current_index``
    to get the index of the future from the input list. (if keyword
    arguments were used in the construction of the `WaitIterator`,
    ``current_index`` will use the corresponding keyword).
    """
    def __init__(self, *args, **kwargs):
        if args and kwargs:
            raise ValueError("You must provide args or kwargs, not both")

        if kwargs:
            self._unfinished = dict((f, k) for (k, f) in kwargs.items())
            futures = list(kwargs.values())
        else:
            self._unfinished = dict((f, i) for (i, f) in enumerate(args))
            futures = args

        self._finished = collections.deque()
        self.current_index = self.current_future = None
        self._running_future = None

        for f in futures:
            f.add_done_callback(self._done_callback)

    def done(self):
        """Returns True if this iterator has no more results."""
        if self._finished or self._unfinished:
            return False
        # Clear the 'current' values when iteration is done.
        self.current_index = self.current_future = None
        return True

    def next(self):
        """Returns a `.Future` that will yield the next available result.

        Note that this `.Future` will not be the same object as any of
        the inputs.
        """
        self._running_future = TracebackFuture()

        if self._finished:
            self._return_result(self._finished.popleft())

        return self._running_future

    def _done_callback(self, donefuture):
        if self._running_future and not self._running_future.done():
            self._return_result(donefuture)
        else:
            self._finished.append(donefuture)

    def _return_result(self, done):
        """Called set the returned future's state that of the future
        we yielded, and set the current future for the iterator.
        """
        chain_future(done, self._running_future)

        self.current_future = done
        self.current_index = self._unfinished.pop(done)



def Task(func, *args, **kwargs):
    """Adapts a callback-based asynchronous function for use in coroutines.

    Takes a function (and optional additional arguments) and runs it with
    those arguments plus a ``callback`` keyword argument.  The argument passed
    to the callback is returned as the result of the yield expression.
    """
    future = Future()

    def handle_exception(typ, value, tb):
        if future.done():
            return False
        future.set_exc_info((typ, value, tb))
        return True

    def set_result(result):
        if future.done():
            return
        future.set_result(result)
    with stack_context.ExceptionStackContext(handle_exception):
        func(*args, callback=_argument_adapter(set_result), **kwargs)
    return future



def multi(children, uiet_exceptions=()):
    """Runs multiple asynchronous operations in parallel.

    ``children`` may either be a list or a dict whose values are
    yieldable objects. ``multi()`` returns a new yieldable
    object that resolves to a parallel structure containing their
    results. If ``children`` is a list, the result is a list of
    results in the same order; if it is a dict, the result is a dict
    with the same keys.

    That is, ``results = yield multi(list_of_futures)`` is equivalent
    to::

        results = []
        for future in list_of_futures:
            results.append(yield future)

    If any children raise exceptions, ``multi()`` will raise the first
    one. All others will be logged, unless they are of types
    contained in the ``quiet_exceptions`` argument.

    If any of the inputs are `YieldPoints <YieldPoint>`, the returned
    yieldable object is a `YieldPoint`. Otherwise, returns a `.Future`.
    This means that the result of `multi` can be used in a native
    coroutine if and only if all of its children can be.

    In a ``yield``-based coroutine, it is not normally necessary to
    call this function directly, since the coroutine runner will
    do it automatically when a list or dict is yielded. However,
    it is necessary in ``await``-based coroutines, or to pass
    the ``quiet_exceptions`` argument.

    This function is available under the names ``multi()`` and ``Multi()``
    for historical reasons.

    .. versionchanged:: 4.2
       If multiple yieldables fail, any exceptions after the first
       (which is raised) will be logged. Added the ``quiet_exceptions``
       argument to suppress this logging for selected exception types.

    .. versionchanged:: 4.3
       Replaced the class ``Multi`` and the function ``multi_future``
       with a unified function ``multi``. Added support for yieldables
       other than `YieldPoint` and `.Future`.

    """
    return multi_future(children)

Multi = multi


def multi_future(children, quiet_exceptions=()):
    """Wait for multiple asynchronous futures in parallel.  like collectAll"""
    if isinstance(children, dict):
        keys = list(children.keys())
        children = children.values()
    else:
        keys = None
    children = list(map(convert_yielded, children))
    assert all(is_future(i) for i in children)
    unfinished_children = set(children)

    future = Future() # it's a collectAll future
    if not children:
        future.set_result({} if keys is not None else [])

    def callback(f_child):
        unfinished_children.remove(f_child)
        if not unfinished_children: 
            # all child futures are done!
            result_list = []
            for f in children:
                try:
                    result_list.append(f.result())
                except Exception as e:
                    if future.done():
                        if not isinstance(e, quiet_exceptions):
                            logging.error("Multiple exceptions in yield list")
                    else:
                        future.set_exc_info(sys.exc_info())
            if not future.done():
                if keys is not None:
                    future.set_result(dict(zip(keys, result_list)))
                else:
                    future.set_result(result_list)

    listening = set()
    for child in children:
        if child not in listening:
            listening.add(child)
            child.add_done_callback(callback) # when child future is done, tell parent future
    return future


def maybe_future(x):
    """Converts ``x`` into a `.Future`.
    the facebook makeFuture, create a fullfilled future
    If ``x`` is already a `.Future`, it is simply returned; otherwise
    it is wrapped in a new `.Future`.  This is suitable for use as
    ``result = yield gen.maybe_future(f())`` when you don't know whether
    ``f()`` returns a `.Future` or not.
    """
    if is_future(x):
        return x
    else:
        fut = Future()
        fut.set_result(x)
        return fut


def with_timeout(abstimeout, future, io_loop=None, quiet_exceptions=()):
    """Wraps a `.Future` in a timeout.

    Raises `TimeoutError` if the input future does not complete before
    ``timeout``, which may be specified in any form allowed by
    `.IOLoop.add_timeout` (i.e. a `datetime.timedelta` or an absolute time
    relative to `.IOLoop.time`)

    If the wrapped `.Future` fails after it has timed out, the exception
    will be logged unless it is of a type contained in ``quiet_exceptions``
    (which may be an exception type or a sequence of types).

    Currently only supports Futures, not other `YieldPoint` classes.
    """
    result = Future()
    chain_future(future, result)
    if io_loop is None:
        io_loop = IOLoop.current()

    def error_callback(future):
        try:
            future.result()
        except Exception as e:
            if not isinstance(e, quiet_exceptions):
                logging.error("Exception in Future %r after timeout",
                              future, exc_info=True)

    def timeout_callback():
        result.set_exception(TimeoutError("Timeout"))
        # In case the wrapped future goes on to fail, log it.
        future.add_done_callback(error_callback)

    timeout_handle = io_loop.call_at(abstimeout, timeout_callback)
    if isinstance(future, Future):
        # We know this future will resolve on the IOLoop, so we don't
        # need the extra thread-safety of IOLoop.add_future 
        future.add_done_callback(
            lambda future: io_loop.remove_timeout(timeout_handle))
    else:
        # concurrent.futures.Futures may resolve on any thread, so we
        # need to route them back to the IOLoop.

        def cancel_on_ioloop(fut):
            IOLoop.current().call_next_tick(lambda fut : IOLoop.current().remove_timeout(timeout_handle))

        future.add_done_callback(cancel_on_ioloop)

    return result


def sleep(duration):
    """Return a `.Future` that resolves after the given number of seconds.

    When used with ``yield`` in a coroutine, this is a non-blocking
    analogue to `time.sleep` (which should not be used in coroutines
    because it is blocking)::

        yield gen.sleep(0.5)

    Note that calling this function on its own does nothing; you must
    wait on the `.Future` it returns (usually by yielding it).
    """
    f = Future()
    IOLoop.current().call_later(duration, lambda: f.set_result(None))
    return f


_null_future = Future()
_null_future.set_result(None)

moment = Future()
moment.set_result(None)
moment.__doc__ = \
    """A special object which may be yielded to allow the IOLoop to run for
one iteration.

This is not needed in normal use but it can be helpful in long-running
coroutines that are likely to yield Futures that are ready instantly.

Usage: ``yield gen.moment``
"""

class Runner(object):
    """Internal implementation of `tornado.gen.engine`.
    Maintains information about pending callbacks and their results.
    The results of the generator are stored in `result_future`
    """
    def __init__(self, gen, result_future, first_yielded):
        self.gen = gen
        self.result_future = result_future
        self.future = _null_future
        self.running = False
        self.finished = False # is coroutine over?
        self.had_exception = False
        self.io_loop = IOLoop.current()
        # For efficiency, we do not create a stack context until we
        # reach a YieldPoint (stack contexts are required for the historical
        # semantics of YieldPoints, but not for Futures).  When we have
        # done so, this field will be set and must be called at the end
        # of the coroutine.
        if self.handle_yield(first_yielded):
            self.run()
        else:
            pass # future is not ready

    def run(self):
        """Starts or resumes the generator, running until it reaches a
        yield point that is not ready.
        """
        if self.running or self.finished:
            return
        try:
            self.running = True
            while True:
                if not self.future.done():
                    return

                future = self.future # the current future by yield
                self.future = None

                try:
                    exc_info = None

                    try:
                        value = future.result()
                    except Exception:
                        self.had_exception = True
                        exc_info = sys.exc_info()

                    if exc_info is not None:
                        yielded = self.gen.throw(*exc_info)
                        exc_info = None
                    else:
                        # switch to generator
                        yielded = self.gen.send(value) # fine, send value to generator and schedule it

                except (StopIteration, Return) as e:
                    #  coroutine is over
                    self.finished = True
                    self.future = _null_future
                    self.result_future.set_result(_value_from_stopiteration(e))
                    self.result_future = None
                    return
                except Exception: # because gen.throw(), etc
                    self.finished = True
                    self.future = _null_future
                    self.result_future.set_exc_info(sys.exc_info())
                    print("exception " + str(sys.exc_info()))
                    self.result_future = None
                    return
                # when coroutine yield here, go on handle new future by yield returned
                if not self.handle_yield(yielded):
                    return # yielded future is not ready, return to ioloop, when future is done, run() will be called
        finally:
            self.running = False

    def handle_yield(self, yielded):
        # arg: a future returned by yield
        try:
            self.future = convert_yielded(yielded)
        except BadYieldError:
            print("BadYieldError")
            self.future = TracebackFuture()
            self.future.set_exc_info(sys.exc_info())

        if not self.future.done() or self.future is moment:
            # if future is not done, then schedule run on future
            print("not done future, add_future")
            def call_on_ioloop(fut): 
                IOLoop.current().call_next_tick(lambda : self.run())

            self.future.add_done_callback(call_on_ioloop)
            #self.io_loop.add_future(self.future, lambda f: self.run())
            return False

        print("future is done")
        return True #  future is done, run() and send to generator

    def handle_exception(self, typ, value, tb):
        if not self.running and not self.finished:
            self.future = TracebackFuture()
            self.future.set_exc_info((typ, value, tb))
            self.run()
            return True
        else:
            return False

Arguments = collections.namedtuple('Arguments', ['args', 'kwargs'])


def _argument_adapter(callback):
    """Returns a function that when invoked runs ``callback`` with one arg.

    If the function returned by this function is called with exactly
    one argument, that argument is passed to ``callback``.  Otherwise
    the args tuple and kwargs dict are wrapped in an `Arguments` object.
    """
    def wrapper(*args, **kwargs):
        if kwargs or len(args) > 1:
            callback(Arguments(args, kwargs))
        elif args:
            callback(args[0])
        else:
            callback(None)
    return wrapper

def convert_yielded(yielded):
    """Convert a yielded object into a Future """
    # Lists and dicts containing YieldPoints were handled earlier.
    if isinstance(yielded, (list, dict)):
        return multi(yielded)
    elif is_future(yielded):
        return yielded
    else:
        print("yielded unknown object %r" % (yielded, ))
        raise BadYieldError("yielded unknown object %r" % (yielded,))

