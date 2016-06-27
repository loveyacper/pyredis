
from base.ioloop import IOLoop
from base.connector import Connector
from base.connection import Connection
from protocol import Protocol

from base.handler import  MessageCallback, NewConnectionCallback
from base.gen import _null_future

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

# flat the arguments passed to redis
def _flat(nest): 
    try: 
        for sublist in nest: 
            if isinstance(sublist, str): 
                yield sublist
            else:
                for elem in _flat(sublist):
                    yield elem 
    except TypeError: 
        yield nest

def async_request(conn, cmd, *params):
    req = '''${0}\r\n{1}\r\n'''.format(len(cmd), cmd)
    bulks = 1
    for pa in _flat(params):
        req += '''${0}\r\n{1}\r\n'''.format(len(pa), pa)
        bulks += 1

    mbulk = '''*{0}\r\n'''.format(bulks)

    if not conn.send(mbulk + req):
        return _null_future
    else:
        '''
        "multi" "exec" "watch" "unwatch" "discard"
        '''
        if cmd == "exec":
            # redis server only return multi bulks result, whatever how many commands in queue
            return conn.newFuture()
        else:
            if conn._multi:
                if cmd != "multi" and cmd != "discard" and cmd != "watch" and cmd != "unwatch":
                    pass

            return conn.newFuture()

# the redis command
'''  just some sample commands '''
def get(conn, key):
    return async_request(conn, "get", key)
Connection.get = get

def set(conn, key, value):
    return async_request(conn, "set", key, value)
Connection.set = set

def delete(conn, key):
    return async_request(conn, "del", key)
Connection.delete = delete

def hmget(conn, key, args):
    return async_request(conn, "hmget", key, args)
Connection.hmget = hmget

def keys(conn, pattern):
    return async_request(conn, "keys", pattern)
Connection.keys = keys

'''  multi commands with queued by server '''
'''  TODO support pipeline option '''
def multi(conn, pipeline = True):
    if conn._multi:
        print("already in multi state")
        return _null_future

    conn._multi = True
    return async_request(conn, "multi")
Connection.multi = multi

def discard(conn):
    conn._multi = False
    return async_request(conn, "discard")
Connection.discard = discard


def execute(conn):
    return async_request(conn, "exec")
Connection.execute = execute


def watch(conn):
    if conn._multi:
        print("WATCH inside MULTI is not allowed")
        return _null_future

    return async_request(conn, "watch")
Connection.watch = watch

def unwatch(conn):
    return async_request(conn, "unwatch")
Connection.unwatch = unwatch



class RedisPool:
    @staticmethod
    def current():
        return RedisPool._instance

    _instance = None

    def __init__(self):
        if RedisPool._instance is not None:
            raise RuntimeError("already hash RedisPool")
        else:
            RedisPool._instance = self

        from collections import defaultdict
        from sets import Set
        self._freepool = defaultdict(Set)
        self._busypool = defaultdict(Set)


    def getConn(self, port, ip = "127.0.0.1"):
        key = str((ip, port))
        if key in self._freepool:
            clist = self._freepool[key]
            conn = self._freepool[key].pop()
            self._busypool[key].add(conn)

            from base.gen import maybe_future
            return maybe_future(conn)
        else:
            ctor = Connector(loop = IOLoop.current())
            ctor.setNewConnCallback(NewConnHandler())
            return ctor.connect(ip = ip, port = port)

    def addBusyConn(self, conn):
        try:
            self._freepool[conn.peerAddr].remove(conn)
        except KeyError:
            pass

        self._busypool[conn.peerAddr].add(conn)

    def freeConn(self, conn):
        self._busypool[conn.peerAddr].remove(conn)
        self._freepool[conn.peerAddr].add(conn)

class NewConnHandler(NewConnectionCallback):
    def __call__(self, conn):
        NewConnectionCallback.__call__(self, conn)
        conn.setMsgCallback(MsgHandler())
        RedisPool.current().addBusyConn(conn)
        # for redis multi
        conn._multi = False
