from base.ioloop import IOLoop
from base.connector import Connector

if __name__ == "__main__":
    '''run in parent dir: python -m test.connect test/connect.py'''
    from base.handler import  MessageCallback, OnConnectCallback, NewConnectionCallback

    class MsgHandler(MessageCallback):
        def __call__(self, conn, mv):
            conn.send("pong")
            return MessageCallback.__call__(self, conn, mv)

    class ConnectHandler(OnConnectCallback):
        def __call__(self, conn):
            OnConnectCallback.__call__(self, conn)
            conn.send("ping")

    class NewConnHandler(NewConnectionCallback):
        def __call__(self, conn):
            NewConnectionCallback.__call__(self, conn)
            conn.setMsgCallback(MsgHandler())
            conn.setOnConnectCallback(ConnectHandler())

    loop = IOLoop()
    connector = Connector(loop = loop)
    connector.setNewConnCallback(NewConnHandler())
    connector.connect(port = 16379)
    print("start")

    loop.start()
