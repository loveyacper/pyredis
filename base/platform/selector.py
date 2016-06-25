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
"""Select-based IOLoop implementation.
Used as a fallback for systems that don't support epoll or kqueue.
"""

import select
from base.ioloop import IOLoop

class _Select(object):
    """select()-based IOLoop implementation for non-Linux systems"""
    def __init__(self):
        self.read_fds = set()
        self.write_fds = set()
        self.error_fds = set()
        self.fd_sets = (self.read_fds, self.write_fds, self.error_fds)

    def close(self):
        pass

    def register(self, fd, events):
        if fd in self.read_fds or fd in self.write_fds or fd in self.error_fds:
            raise IOError("fd %s already registered" % fd)
        if events & IOLoop.READ_EVENT:
            self.read_fds.add(fd)
        if events & IOLoop.WRITE_EVENT:
            self.write_fds.add(fd)
        if events & IOLoop.ERROR_EVENT:
            self.error_fds.add(fd)
            # Closed connections are reported as errors by epoll and kqueue,
            # but as zero-byte reads by select, so when errors are requested
            # we need to listen for both read and error.
            # self.read_fds.add(fd)

    def modify(self, fd, events):
        self.unregister(fd)
        self.register(fd, events)

    def unregister(self, fd):
        self.read_fds.discard(fd)
        self.write_fds.discard(fd)
        self.error_fds.discard(fd)

    def poll(self, timeout):
        readable, writeable, errors = select.select(
            self.read_fds, self.write_fds, self.error_fds, timeout)
        events = {}
        for fd in readable:
            events[fd] = events.get(fd, 0) | IOLoop.READ_EVENT
        for fd in writeable:
            events[fd] = events.get(fd, 0) | IOLoop.WRITE_EVENT
        for fd in errors:
            events[fd] = events.get(fd, 0) | IOLoop.ERROR_EVENT
        return events.items()


class SelectIOLoop(IOLoop):
    def __init__(self):
        super(SelectIOLoop, self).__init__()
        import  logging
        logging.info("INIT platform SelectIOLoop")
        self._impl = _Select()
