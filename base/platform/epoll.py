import select
from base.ioloop import IOLoop

class EpollIOLoop(IOLoop):
    def __init__(self):
        super(EpollIOLoop, self).__init__()
        import  logging
        logging.info("INIT platform EpollIOLoop")
        self._impl = select.epoll()
        IOLoop.READ_EVENT = select.EPOLLIN
        IOLoop.WRITE_EVENT = select.EPOLLOUT
        IOLoop.ERROR_EVENT = select.EPOLLERR
