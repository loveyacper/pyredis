import logging

class MessageCallback:
    def __call__(self, conn, mv):
        return len(mv)

class OnConnectCallback:
    def __call__(self, conn):
        logging.debug("OnConnectCallback %s", str(conn))

class OnDisConnectCallback:
    def __call__(self, conn):
        logging.debug("OnDisConnectCallback %s", str(conn))

class NewConnectionCallback:
    def __call__(self, conn):
        logging.debug("NewConnectionCallback %s", str(conn))
        conn.setMsgCallback(MessageCallback())
        conn.setOnConnectCallback(OnConnectCallback())

