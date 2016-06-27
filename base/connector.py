import logging
import socket
import os

from future import Future, is_future

class ConnectError(Exception):
    def __init__(self, err = ""):
        self._err = err

    def __str__(self):
        return self._err

    def __repr__(self):
        return "ConnectError:" + self._err


class Connector:
    ''' Tcp connector'''
    NONE = 0
    CONNECTING = 1
    CONNECTED = 2

    def __init__(self, loop):
        self.__sock = None
        self.__peeraddr = None
        self.__state = Connector.NONE

        self.__loop = loop
        self.__future = None

        from handler import NewConnectionCallback
        self.__newConnectionCallback = NewConnectionCallback()

    def setNewConnCallback(self, callback):
        self.__newConnectionCallback = callback

    def fileno(self):
        return self.__sock.fileno()

    def connect(self, port, ip = '127.0.0.1'):
        '''Nonblocking connect to remote address'''
        if self.__future is not None:
            raise RuntimeError("already connecting")

        if self.__state != Connector.NONE:
            raise RuntimeError("already connected")
            
        self.__sock = socket.socket()
        self.__sock.setblocking(False)
        self.__peeraddr = (ip, port)
        self.__future = Future()

        try: 
            self.__sock.connect(self.__peeraddr)
        except socket.error as serr: 
            if serr.errno != os.errno.EINPROGRESS and serr.errno != os.errno.EWOULDBLOCK:
                logging.exception("connect error is not EINPROGRESS: %s", str(serr.errno))
                self.__future.set_exception(ConnectError(str(serr.errno)))
                self.close()
                return self.__future
            else:
                self.__state = Connector.CONNECTING
        else:
            self.__state = Connector.CONNECTED
            logging.info("connect immediately success %s", str(self.fileno()))
            self._onSuccess()
            return self.__future

        from ioloop import IOLoop
            
        self.__loop.register(self, IOLoop.WRITE_EVENT)
        return self.__future

    def close(self):
        if self.__sock is None:
            return

        try:
            self.__sock.shutdown(socket.SHUT_WR)
            self.__sock.close()
            self.__sock = None
        except socket.error as serr:
            pass

        self.__state = Connector.NONE

    def onError(self):
        self.__future.set_exception(ConnectError())
        self.close()

    def onReadable(self):
        raise RuntimeError("connector should not readable")

    def onWritable(self):
        err = self.__sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR) 
        if err != 0: 
            logging.error("Connector onWritable error %s", os.strerror(err))
            self.__future.set_exception(ConnectError())
            self.close()
            return False

        self._onSuccess()

        return True

    def _onSuccess(self):
        self.__state = Connector.CONNECTED

        from connection import Connection
        conn = Connection(loop = self.__loop, socket = self.__sock, remote = self.__peeraddr)
        self.__newConnectionCallback(conn)

        from ioloop import IOLoop
        self.__loop.modify(conn, IOLoop.READ_EVENT | IOLoop.WRITE_EVENT)

        conn.onConnect()

        self.__sock = None
        self.__future.set_result(conn)
