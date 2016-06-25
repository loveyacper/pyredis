#!/usr/bin/env python
import re
import logging

class Protocol:
    def __init__(self):
        self.reset()
        self._handlers = {':' : self.intHandler, '+' : self.infoHandler, '-' : self.errHandler, '*' : self.parseMultiBulks, '$' : self.parseMultiBulk}

    def reset(self):
        self._multibulk = -1
        self._paramLen = -1
        self._params = []
        self._consumed = 0

    def ready(self):
        #return len(self._params) >= self._multibulk

        if len(self._params) >= self._multibulk:
            return len(self._params) > 0 or self._multibulk != -1

        #return False

    def intHandler(self, data):
        m = re.match(r":(\d+?)\r\n", data[self._consumed:])
        if m != None:
            self._params.append(m.group(1))
            self._consumed += 3 + len(m.group(1))
            return self.parse(data)

        return m != None

    def infoHandler(self, data ):
        m = re.match(r"\+(.*?)\r\n", data[self._consumed:])
        if m != None:
            self._params.append(m.group(1))
            self._consumed += 3 + len(m.group(1))
            return self.parse(data)

        return m != None

    def errHandler(self, data):
        m = re.match(r"\-(.*?)\r\n", data[self._consumed:])
        if m != None:
            self._params.append(m.group(1))
            self._consumed += 3 + len(m.group(1))
            return self.parse(data)

        return m != None

    def consumed(self): 
        return self._consumed

    def params(self): 
        return self._params

    def debug(self): 
        if not self.ready():
            return

        #print("debug result:")
        for pa in self.params():
            #print(pa)
            logging.info(pa)

    def parse(self, data):
        if self.ready():
            return True

        if not isinstance(data, str):
            data = data.tobytes()

        if self._consumed > len(data):
            raise RuntimeError("error consumed")

        if self._consumed + 1 >= len(data):
            return False # wait more data

        if self._paramLen != -1:
            handler = self.parseMultiBulk
        else:
            handler = self._handlers.get(data[self._consumed])
        if not handler:
            logging.error("consumed %d", self._consumed)
            #logging.error("error protocol %s", data[self._consumed:])
            raise RuntimeError("error protocol")

        return handler(data)
        #else:
            #return self.parseMultiBulk(data)

    def parseMultiBulks(self, data):
        if self._multibulk != -1 or self._parseMultiBulkLen(data):
            return self.parse(data)

        return False

    def _parseMultiBulkLen(self, data):

        m = re.match(r"\*(-?\d+?)\r\n", (data[self._consumed:]))
        if m != None:
            if int(m.group(1)) == -1:
                self._multibulk = 0
                #self._params.append("") # "(empty list or set)"
            else:
                self._multibulk = int(m.group(1))

            self._consumed += 3 + len(m.group(1))
            return True
        else:
            return False

    def parseMultiBulk(self, data):

        while self._parseBulk(data):
            if self._multibulk != -1 and self._multibulk <= len(self._params):
                return self.parse(data)
            if self._multibulk == -1:
                return self.parse(data)

        return  len(self._params) > 0

    def _parseBulk(self, data):

        if self._paramLen == -1:
            m = re.match(r"\$(-?\d+?)\r\n", data[self._consumed:])
            if m != None:
                # special process $-1\r\n   == nil
                if int(m.group(1)) == -1:
                    self._paramLen = 0
                else:
                    self._paramLen = int(m.group(1))

                self._consumed += 3 + len(m.group(1))
            else:
                return False

        if self._paramLen == 0:
            self._params.append("") # (nil)
            self._paramLen = -1
            return self.parse(data)

        # pass param string
        m = re.match(r"(.+?)\r\n", data[self._consumed:])
        if m != None:
            if self._paramLen != len(m.group(1)):
                raise RuntimeError("error param length")

            self._params.append(m.group(1))
            self._consumed += 2 + len(m.group(1))
            self._paramLen = -1
                
            return self.parse(data)
        else:
            return False


if __name__ == "__main__":
    parser = Protocol()
    req = "*2\r\n$3\r\nset\r\n$4\r\nname\r\n:15\r\n$-1\r\n*-1\r\n"
    #req = "*2\r\n$-1\r\n$2\r\n11\r\n-ERR no such key\r\n"
    #req = "*-1\r\n*2\r\n+29\r\n+cd\r\n$-1\r\n"
    #req = "$-1\r\n"
    mv = memoryview(req)
    '''
    parser.parse(mv)
    offset = parser.consumed()
    print("try debug")
    parser.debug()
    parser.reset()

    print("========")

    parser.parse(mv[offset:])
    parser.debug()

    '''
    offset = 0
    for i in range(len(mv)):
        parser.parse(mv[offset:i + 1])
        if parser.ready():
            offset += parser.consumed()
            parser.debug()
            parser.reset()
    parser.debug()
