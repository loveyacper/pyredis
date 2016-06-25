
import socket
import select

class Acceptor:
    ''' acceptor '''
    def __init__(self, loop, port, ip = 'localhost'):
        self.__sock = socket.socket()
        self.__loop = loop
        from handler import NewConnectionCallback
        self.__newConnectionCallback = NewConnectionCallback()

        self.bind(ip, port)

        from ioloop import IOLoop
        loop.register(self, IOLoop.READ_EVENT)

    def setNewConnCallback(self, callback):
        self.__newConnectionCallback = callback

    def bind(self, ip, port):
        self.__sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.__sock.bind((ip, port))
        self.__sock.listen(1024)
        self.__sock.setblocking(False)

    def fileno(self):
        return self.__sock.fileno()

    def onError(self):
        self.__loop.stop()

    def onWritable(self):
        raise RuntimeError("acceptor should not writeable")

    def onReadable(self):
        newsock = self.__sock.accept()

        from connection import Connection
        conn = Connection(loop = self.__loop, socket = newsock[0], remote = newsock[1])
        self.__newConnectionCallback(conn) # register msg callback and on connect callback for conn

        from ioloop import IOLoop
        self.__loop.register(conn, IOLoop.READ_EVENT | IOLoop.WRITE_EVENT)

        conn.onConnect()

        return True
