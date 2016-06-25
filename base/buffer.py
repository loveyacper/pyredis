import re
import sys
import errno
import socket
import signal

class Buffer:
    def __init__(self):
        self.datalen = 0
        self.buf = bytearray(0)

    @staticmethod
    def __pow2(size):
        s = 1
        while s < size:
            s *= 2

        return s

    def assureSpace(self, size):
        if len(self.buf) < self.datalen + size:
            self.buf.extend('\0' * (Buffer.__pow2(self.datalen + size) - len(self.buf)))

    def produce(self, size):
        if len(self.buf) < self.datalen + size:
            print("buflen " + str(len(self.buf)))
            print("datalen " + str(self.datalen))
            print("size " + str(size))
            raise RuntimeError("error produce")

        self.datalen += size

    def consume(self, size):
        if self.datalen < size:
            raise RuntimeError("error consume")

        self.datalen -= size
        del self.buf[:size]

    def putData(self, data):
        self.assureSpace(len(data))
        mv = memoryview(self.buf)
        mv[self.datalen:self.datalen + len(data)] = data

        self.produce(len(data))

    def data(self):
        return (self.buf, self.datalen)

    def empty(self):
        return self.datalen == 0

    def capacity(self):
        return len(self.buf)

if __name__ == '__main__':
    buf = Buffer()
    buf.putData("abcde")

    data, size = buf.data()
    print(buf.data())
    print(len(data))

    buf.consume(2)
    data, size = buf.data()
    print(buf.data())
    print(len(data))


    print map(lambda e : chr(e), data[0:size])
    #map(lambda e : pass, data)
