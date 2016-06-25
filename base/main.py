#!/usr/bin/env python

from ioloop import IOLoop
from acceptor import Acceptor
from connector import Connector

if __name__ == "__main__":
    from handler import  MessageCallback, OnConnectCallback, NewConnectionCallback

    class MsgHandler(MessageCallback):
        def __call__(self, conn, mv):
            #print("recv " + str(mv))
            conn.send("*1\r\n$4\r\npong\r\n")
            return MessageCallback.__call__(self, conn, mv)

    class ConnectHandler(OnConnectCallback):
        def __call__(self, conn):
            OnConnectCallback.__call__(self, conn)
            #print("on connect, send ping")
            #conn.send("*3\r\n$3\r\nset\r\n$3\r\nage\r\n$3\r\n711\r\n")

    class NewConnHandler(NewConnectionCallback):
        def __call__(self, conn):
            NewConnectionCallback.__call__(self, conn)
            conn.setMsgCallback(MsgHandler())
            conn.setOnConnectCallback(ConnectHandler())

    def print_time(a='default'): 
        import time
        print("From print_time", time.time(), a) 

    loop = IOLoop()
    loop._sched.enter(delay = 0.4, count = 10, action = print_time)
    acceptor = Acceptor(port = 6379, loop = loop)
    acceptor.setNewConnCallback(NewConnHandler())
    #connector = Connector(loop = loop)
    #connector.setNewConnCallback(NewConnHandler())
    #connector.connect(port = 6379)
    print("start")

    loop.start()
