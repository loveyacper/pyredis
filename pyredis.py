import re
import sys
import errno
import socket
import signal


class RedisClient:
    '''TODO document for RedisClient'''
    def __init__(self):
        self.socket = None
        self.recvbytes = 0
        self.recvbuf= bytearray(0)
        self.handler= {':' : self.intHandler, '+' : self.infoHandler, '-' : self.errHandler, '*' : self.mbulkHandler, '$' : self.paramlenHandler}
        self.reset()

    def getpeername(self):
        ''' for command line prompt '''
        if not self.isConnect():
            return "(not connected)"
        else:
            return self.socket.getpeername()

    def intHandler(self, data, length):
        m = re.match(r":(\d+?)\r\n", data)
        if m != None:
            self.params.append(m.group(1))
            self.consume(3 + len(m.group(1)))

        return m != None

    def infoHandler(self, data, length):
        m = re.match(r"\+(.*?)\r\n", data)
        if m != None:
            self.params.append(m.group(1))
            self.consume(3 + len(m.group(1)))

        return m != None

    def errHandler(self, data, length):
        m = re.match(r"\-(.*?)\r\n", data)
        if m != None:
            self.params.append(m.group(1))
            self.consume(3 + len(m.group(1)))

        return m != None

    def mbulkHandler(self, data, length):
        if self.mbulk != 0:
            raise RuntimeError("error protocol")

        m = re.match(r"\*(\d+?)\r\n", data)
        if m != None:
            self.mbulk = int(m.group(1))
            if self.mbulk <= 0:
                print("(empty list or set)")
                self.reset()

            self.consume(3 + len(m.group(1)))

        return m != None

    def paramlenHandler(self, data, length):
        m = re.match(r"\$(\d+?)\r\n", data)
        if m != None:
            self.paramLen = int(m.group(1))
            self.consume(3 + len(m.group(1)))

            if self.paramLen <= 0:
                raise RuntimeError("wrong param len, should be positive")
        else:
            # How to match negative number?
            m = re.match(r"\$\-(\d+?)\r\n", data)
            if m != None:
                print("(nil)")
                self.reset()
                self.consume(4 + len(m.group(1)))

        return m != None

    def paramHandler(self, data, length):
        m = re.match(r"(\w+?)\r\n", data)

        if m != None:
            if self.paramLen != len(m.group(1)):
                raise RuntimeError("error param length")

            self.params.append(m.group(1))
            self.consume(2 + len(m.group(1)))
            self.paramLen = 0

        return m != None

    def onDisconnect(self):
        try:
            self.socket.shutdown(socket.SHUT_WR)
            self.socket.close()
        except socket.error as serr:
            pass

        self.socket = None

    def reset(self):
        '''called after a complete protocol received'''
        self.mbulk = 0
        self.paramLen = 0
        self.params = []

    def isConnect(self):
        return self.socket != None

    def connect(self, ip, port):
        if self.socket != None:
            return;

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            self.socket.connect((ip, port))
        except socket.error as serr:
            if serr.errno == errno.ECONNREFUSED or serr.errno == errno.ENETUNREACH or serr.errno == errno.ETIMEDOUT:
                self.onDisconnect()
                return
            else:
                raise
                
        self.socket.setblocking(False)

    def send(self, msg):
        total = 0
        while total < len(msg):
            sent = self.socket.send(msg[total:])
            if sent <= 0:
                self.onDisconnect()
                return -1;

            total += sent;

        return total

    # private
    def recv(self):
        if len(self.recvbuf) < self.recvbytes + 32:
            self.recvbuf.extend('\0' * (self.recvbytes + 32 - len(self.recvbuf)))

        recved = 0
        try:
            mv = memoryview(self.recvbuf)
            recved = self.socket.recv_into(mv[self.recvbytes:], len(self.recvbuf) - self.recvbytes)
        except socket.error as serr:
            if serr.errno == errno.EAGAIN:
                return 0
            else:
                raise

        if recved > 0:
            self.recvbytes += recved
        else:
            recved = -1
            self.onDisconnect()

        return recved

    # private
    def data(self):
        if self.recvbytes == 0:
            return ("", 0)

        return (self.recvbuf, self.recvbytes)

    # private
    def consume(self, len):
        if self.recvbytes < len:
            raise RuntimeError("error consume")

        self.recvbytes -= len
        del self.recvbuf[:len]

    def update(self):
        data, length = self.data()
        if length <= 0:
            return False

        if self.paramLen == 0:
            handler = self.handler.get(chr(data[0]))
            if not handler:
                raise RuntimeError("error protocol")

            if not handler(data, length):
                return False
        else:
            # process param string
            self.paramHandler(data, length)

        if len(self.params) == 0 and self.paramLen == 0 and self.mbulk == 0:
            return True

        if len(self.params) > 0 and self.mbulk <= len(self.params):
            if len(self.params) > 1:
                for index, item in enumerate(self.params):
                    print(str(index + 1) + ")" + item)
            else:
                for item in self.params:
                    print(item)

            self.reset()
            return True

        return False

def parseOption(argv):
    ip = '127.0.0.1'
    port = 6379

    parsePort = False
    parseHost = False
    for arg in argv:
        if arg == "-h":
            parseHost = True
            parsePort = False
        elif arg == "-p":
            parseHost = False
            parsePort = True
        elif parseHost:
            parseHost = False
            ip = arg
        elif parsePort:
            parsePort = False
            port = int(arg)

    return (ip, port)


def signalHandler(signal, frame):
    print("\r\n")
    sys.exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signalHandler)

    ip, port = parseOption(sys.argv)

    # connect to server
    sock = RedisClient()
    sock.connect(ip, port)

    while True:

        if not sock.isConnect():
            sock.connect(ip, port)

        request = raw_input(str(sock.getpeername()) + "> ")

        # check if exit
        request = request.lower()
        if request == "quit" or request == "exit":
            sys.exit(0)

        if not sock.isConnect():
            continue

        # use inline protocol
        sock.send(request + "\r\n")

        while not sock.update():
            ret = sock.recv()
            if ret < 0:
                print("not connected\n")
                break

