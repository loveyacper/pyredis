import socket
import os
import logging
from buffer import Buffer
from future import Future, is_future

class Connection:
    ''' Tcp connection '''
    def __init__(self, loop, socket, remote = None):
        self.__sock = socket
        self.__sock.setblocking(False)
        self.__peeraddr = remote

        self.__loop = loop

        self.__recvbuf = Buffer()
        self.__sendbuf = Buffer()
        self.__shouldPollWrite = False

        self.__onConnectCallback = None
        self.__onDisconnectCallback = None

        self.__msgCallback = None
        self.__futures = []

    def __str__(self):
        return "connection from:" + str(self.__peeraddr)

    def setMsgCallback(self, callback):
        self.__msgCallback = callback

    def setOnConnectCallback(self, callback):
        self.__onConnectCallback = callback

    def setOnDisconnectCallback(self, callback):
        self.__onDisconnectCallback = callback

    def fileno(self):
        return self.__sock.fileno()

    def send(self, data):
        '''High level send data interface, deal with EWOULDBLOCK'''
        if self.__sock is None:
            return False

        if self.__shouldPollWrite:
            self.__sendbuf.putData(data)
            return True

        sent = self._rawSend(data)
        if sent < 0:
            return False

        if self.__shouldPollWrite:
            from ioloop import IOLoop
            self.__loop.modify(self, IOLoop.READ_EVENT | IOLoop.WRITE_EVENT)

        return True

    def _rawSend(self, data):
        '''A wrapper for send data on socket'''
        if len(data) == 0:
            return 0

        sent = 0
        try:
            sent = self.__sock.send(data)
            assert sent != 0

            if sent > 0:
                self.__shouldPollWrite = (sent < len(data))

        except (socket.error, IOError, OSError) as e:
            if e.args[0] in _ERRNO_WOULDBLOCK:
                self.__shouldPollWrite = True
                assert sent == -1
                sent = 0
            else:
                logging.error("_rawSend error %s", str(e.args[0]))
                sent = -1

        return sent


    def close(self):
        if self.__sock is None:
            return

        try:
            self.__sock.shutdown(socket.SHUT_WR)
            self.__sock.close()
            self.__sock = None

            if self.__onDisconnectCallback is not None:
                self.__onDisconnectCallback(self)

        except socket.error as serr:
            pass

    def onConnect(self):
        if self.__onConnectCallback is not None:
            self.__onConnectCallback(self)

    def onError(self):
        self.close()

    def onReadable(self):
        while True:
            self.__recvbuf.assureSpace(4 * 1024)
            data, offset = self.__recvbuf.data()

            try:
                mv = memoryview(data)
                recved = self.__sock.recv_into(mv[offset:], self.__recvbuf.capacity() - offset)
            except socket.error as serr:
                if serr.errno == os.errno.EAGAIN:
                    #logging.debug("recv EAGAIN.")
                    return True
                else:
                    logging.error("recv error %s", str(serr.errno))
                    raise

            if recved > 0:
                logging.info("recv %d", recved)
                self.__recvbuf.produce(recved)

                while not self.__recvbuf.empty():
                    data, len = self.__recvbuf.data()
                    mv = memoryview(data[:len])
                    consumed = self.__msgCallback(self, mv)

                    if consumed < 0:
                        self.close()
                    elif consumed == 0:
                        break
                    else:
                        self.__recvbuf.consume(consumed)
            else:
                return False

        raise RuntimeError("never here")

    def onWritable(self):
        from ioloop import IOLoop

        if not self.__shouldPollWrite:
            self.__loop.modify(self, IOLoop.READ_EVENT)
            return True

        if self.__sendbuf.empty():
            self.__shouldPollWrite = False
            self.__loop.modify(self, IOLoop.READ_EVENT)

            return True

        data, len = self.__sendbuf.data()
        mvSendData = memoryview(data[:len])
        sent = self._rawSend(mvSendData)
        if sent < 0:
            return False

        self.__sendbuf.consume(sent)

        if not self.__shouldPollWrite or self.__sendbuf.empty():
            self.__loop.modify(self, IOLoop.READ_EVENT)

        return True

    def newFuture(self):
        # add new future to conn's pending list
        fut = Future()
        self.__futures.append(fut)
        return fut

    def resolveAndPopFuture(self, value):
        fut = self.__futures.pop(0)
        fut.set_result(value)
