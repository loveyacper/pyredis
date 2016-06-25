from base.ioloop import IOLoop
from base.acceptor import Acceptor

if __name__ == "__main__":
    '''run in parent dir: python -m test.accept test/accept.py'''
    from base.handler import  MessageCallback, OnConnectCallback, NewConnectionCallback

    class MsgHandler(MessageCallback):
        def __call__(self, conn, mv):
            conn.send("pong")
            return MessageCallback.__call__(self, conn, mv)

    class ConnectHandler(OnConnectCallback):
        def __call__(self, conn):
            OnConnectCallback.__call__(self, conn)
            print("on connect, send ping")
            conn.send("ping")

    class NewConnHandler(NewConnectionCallback):
        def __call__(self, conn):
            NewConnectionCallback.__call__(self, conn)
            conn.setMsgCallback(MsgHandler())
            conn.setOnConnectCallback(ConnectHandler())

    loop = IOLoop()
    acceptor = Acceptor(port = 16379, loop = loop)
    acceptor.setNewConnCallback(NewConnHandler())
    print("start")

    loop.start()
