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
import select
from base.ioloop import IOLoop

class kqueue:
    """Copy from tornado:A kqueue-based event loop for BSD/Mac systems."""
    def __init__(self):
        self._kq = select.kqueue()

    def fileno(self):
        return self._kq.fileno()

    def close(self):
        self._kq.close()

    def register(self, fd, events):
        self._control(fd, events, select.KQ_EV_ADD)

    def modify(self, fd, events):
        self.unregister(fd)
        self.register(fd, events)

    def unregister(self, fd):
        try:
            self._control(fd, IOLoop.WRITE_EVENT | IOLoop.READ_EVENT, select.KQ_EV_DELETE)
        except Exception as e:
            pass

    def _control(self, fd, events, flags):
        kevents = []
        if events & IOLoop.WRITE_EVENT:
            kevents.append(select.kevent(
                fd, filter=select.KQ_FILTER_WRITE, flags=flags))
        if events & IOLoop.READ_EVENT:
            kevents.append(select.kevent(
                fd, filter=select.KQ_FILTER_READ, flags=flags))
        # Even though control() takes a list, it seems to return EINVAL
        # on Mac OS X (10.6) when there is more than one event in the list.
        for kevent in kevents:
            self._kq.control([kevent], 0)

    def poll(self, timeout):
        kevents = self._kq.control(None, 1000, timeout)

        events = {}
        for kevent in kevents:
            fd = kevent.ident
            if kevent.filter == select.KQ_FILTER_READ:
                events[fd] = events.get(fd, 0) | IOLoop.READ_EVENT
            if kevent.filter == select.KQ_FILTER_WRITE:
                if kevent.flags & select.KQ_EV_EOF:
                    # If an asynchronous connection is refused, kqueue
                    # returns a write event with the EOF flag set.
                    # Turn this into an error for consistency with the
                    # other IOLoop implementations.
                    # Note that for read events, EOF may be returned before
                    # all data has been consumed from the socket buffer,
                    # so we only check for EOF on write events.
                    events[fd] = IOLoop.ERROR_EVENT
                else:
                    events[fd] = events.get(fd, 0) | IOLoop.WRITE_EVENT
            if kevent.flags & select.KQ_EV_ERROR:
                events[fd] = events.get(fd, 0) | IOLoop.ERROR_EVENT

            return events.items()

class KqueueIOLoop(IOLoop):
    """A kqueue-based event loop for BSD/Mac systems."""
    def __init__(self):
        super(KqueueIOLoop, self).__init__()
        import  logging
        logging.info("INIT platform KqueueIOLoop")
        self._impl = kqueue()

