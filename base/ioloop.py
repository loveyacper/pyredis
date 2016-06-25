from configurable import Configurable
from scheduler import SchedulerEx

import logging
import select

class IOLoop(Configurable):
    READ_EVENT = 1
    WRITE_EVENT = 2
    ERROR_EVENT = 4

    _instance = None

    def __init__(self):
        if IOLoop._instance is None:
            IOLoop._instance = self
        else:
            raise RuntimeError("dup IOLoop")

        logging.debug("IOLoop __init__")

        self._handlers = {}
        self._fired = {}
        self._pollInterval = 1
        self._stop = False
        self._sched = SchedulerEx(delayfunc = self.poll)

    @staticmethod 
    def current():
        return IOLoop._instance

    @classmethod
    def base(cls):
        return IOLoop

    @classmethod
    def instance(cls):
        if hasattr(select, "epoll"):
            from platform.epoll import EpollIOLoop
            return EpollIOLoop 

        if hasattr(select, "kqueue"):
            from platform.kqueue import KqueueIOLoop 
            return KqueueIOLoop

        from platform.selector import SelectIOLoop 
        return SelectIOLoop

    def fileno(self):
        return self._impl.fileno()

    def close(self):
        self._impl.close()

    def stop(self):
        self._stop = True

    def setPollInterval(self, interval = 1):
        self._pollInterval = interval

    def start(self):
        while not self._stop:
            self.poll(self._pollInterval)

    def schedule(self, interval, actionfunc, *args):
        return self._sched.enter(delay = interval, action = actionfunc);
        #return self._sched.enter(delay = interval, action = actionfunc, argument = (*args));

    def call_at(self, abstime, actionfunc):
        return self._sched.enterabs(time = abstime, action = actionfunc);

    def call_later(self, timeout, actionfunc):
        return self._sched.enter(delay = timeout, action = actionfunc);

    def call_next_tick(self, actionfunc):
        return self._sched.enter(delay = 0, action = actionfunc);

    # bug remove, TODO
    def remove_timeout(self, eventid):
        self._sched.cancel(eventid)

    def register(self, obj, event):
        fd = obj.fileno()
        if fd in self._handlers:
            raise RuntimeError("IOLoop already contain " + str(fd))


        logging.debug("register %s event %s", str(fd), str(event))
        self._handlers[fd] = obj
        self._impl.register(fd, event)

    def modify(self, obj, event):
        fd = obj.fileno()
        if fd not in self._handlers:
            raise RuntimeError("modify IOLoop not contain " + str(fd))

        self._handlers[fd] = obj
        self._impl.modify(fd, event)

    def unregister(self, fd):
        if not self._handlers.get(fd):
            raise RuntimeError("unregister IOLoop not contain " + str(fd))

        logging.debug("unregister %s", str(fd))

        del self._handlers[fd]
        self._impl.unregister(fd)

    def poll(self, timeout = 0):
        ''' can be called in other loop by poll(0)'''
        diff = self._sched.run(False)
        if diff > 0:
            timeout = diff if diff < timeout else timeout
        #if timeout < 0.001:
        #    timeout = 0.001

        #logging.debug("poll for %s", str(timeout))
        evpairs = self._impl.poll(timeout)

        if evpairs:
            self._fired.update(evpairs)
        else:
            pass

        while self._fired:
            fd, event = self._fired.popitem()
            try:
                handler = self._handlers.get(fd)

                if event & IOLoop.READ_EVENT:
                    if handler:
                        if not handler.onReadable():
                            logging.debug("onReadable error for " + str(fd))
                            handler.onError()
                            self.unregister(fd)
                    else:
                        logging.debug(str(fd) + " can not find its handler")
                    pass

                if event & IOLoop.WRITE_EVENT:
                    if handler:
                        if not handler.onWritable():
                            logging.debug("onWritable error for " + str(fd))
                            handler.onError()
                            self.unregister(fd)
                    else:
                        logging.debug(str(fd) + " can not find its handler")
                    pass

                if event & IOLoop.ERROR_EVENT:
                    logging.debug(str(fd) + " fired event ERROR_EVENT")
                    if handler:
                        handler.onError()

                    self.unregister(fd)

            except Exception as err: 
                logging.error(str(err))

