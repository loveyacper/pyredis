#!/usr/bin/env python

import time
import heapq
from collections import namedtuple

__all__ = ["SchedulerEx"]

CountEvent = namedtuple('Event', 'time, delay, count, action, argument')

class SchedulerEx:
    def __init__(self, timefunc = time.time, delayfunc = time.sleep):
        self._queue = []
        self.timefunc = timefunc
        self.delayfunc = delayfunc

    def enterabs(self, time, delay, count = 1, action = None, argument = ()):
        if count == 0:
            raise RuntimeError("timer count == 0")

        event = CountEvent(time, delay, count, action, argument)
        heapq.heappush(self._queue, event)

        return event # The ID

    def enter(self, delay, count = 1, action = None, argument = ()):
        time = self.timefunc() + delay
        return self.enterabs(time, delay, count, action, argument)

    def cancel(self, event):
        print(str(self._queue))
        self._queue.remove(event)
        heapq.heapify(self._queue)

    def empty(self):
        return not self._queue

    def run(self, blocking = True):
        q = self._queue
        delayfunc = self.delayfunc
        timefunc = self.timefunc

        pop = heapq.heappop
        while q:
            time, delay, count, action, argument = checked_event = q[0]
            now = timefunc()
            if now < time:
                if blocking:
                    delayfunc(time - now)
                else:
                    return time - now
            else:
                event = pop(q)
                assert event is checked_event

                if action is not None:
                    action(*argument)

                count = event.count
                if count > 0:
                    count = count - 1

                if count != 0:
                    nevent = CountEvent(time = event.time + delay, delay = event.delay, count = count, action = event.action, argument = event.argument)
                    heapq.heappush(q, nevent) 
                else:
                    pass # remove event

        return 0

if __name__ == "__main__":
    s = SchedulerEx()
    def print_time(a='default'): 
        print("From print_time", time.time(), a) 
                    
    def print_some_times():
        print(time.time())

    s.enter(delay = 0.01, count = 5, action = print_time)
    s.enter(delay = 0.1, count = 1, action = print_time, argument = ('positional',))
    s.run()

    print_some_times()
