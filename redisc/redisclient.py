
from base.ioloop import IOLoop
from base.connector import Connector
from protocol import Protocol

from base.handler import  MessageCallback

class MsgHandler(MessageCallback):
    def __init__(self):
        self.parser = Protocol()

    def __call__(self, conn, mv):
        parser = self.parser
        parser.parse(mv)
        consumed = 0
        if parser.ready():
            parser.debug()
            params = parser.params()

            conn.resolveAndPopFuture(list(params))

            consumed = parser.consumed()
            parser.reset()

        else:
            mylog.debug("not complete protocol recv, please wait")

        return consumed


class RedisClientPool:
    def __init__(self):
        pass

    @staticmethod
    def getConn(port, ip = "127.0.0.1"):
        ''' TODO connection pool '''
        ctor = Connector(loop = IOLoop.current())
        return ctor.connect(ip = ip, port = port)

    @staticmethod
    def _flat(nest): 
        try: 
            for sublist in nest: 
                if isinstance(sublist, str): 
                    yield sublist
                else:
                    for elem in flat(sublist):
                        yield elem 
        except TypeError: 
            yield nest

    @staticmethod
    def async_request(conn, params):
        req = ""
        bulks = 0
        for pa in RedisClientPool._flat(params):
            req += '''${0}\r\n{1}\r\n'''.format(len(pa), pa)
            bulks += 1

        mbulk = '''*{0}\r\n'''.format(bulks)

        #print("send req \n" + mbulk + req)

        if not conn.send(mbulk + req):
            return base.gen._null_future
        else:
            return conn.newFuture()

    # the redis command
    @staticmethod
    def get(conn, key):
        return RedisClientPool.async_request(conn, ("get", key))

    @staticmethod
    def set(conn, key, value):
        return RedisClientPool.async_request(conn, ("set", key, value))

    @staticmethod
    def hmget(conn, key, args):
        return RedisClientPool.async_request(conn, ("hmget", key, args))

    @staticmethod
    def keys(conn, pattern):
        return RedisClientPool.async_request(conn, ("keys", pattern))

