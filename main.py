#!/usr/bin/env python

import signal
import sys

from base.ioloop import IOLoop
from redisc.redisclient import RedisClientPool


def signalHandler(signal, frame):
    print("\r\nExiting\r\n")
    sys.exit(0)

loop = None

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signalHandler)

    import logging
    import logging.config

    mylog = logging.getLogger("redis_client")
    try:
        logging.config.fileConfig('conf/logging.conf')
    except Exception as e: 
        logging.basicConfig(filename='redis_client.log', level=logging.DEBUG, format='[%(asctime)s]%(levelname)s: %(message)s')

    from base.gen import coroutine

    ''' main loop '''
    loop = IOLoop()

    @coroutine
    def sample_redis_client(port = 6379):
        redis = yield RedisClientPool.getConn(port = port)
        from redisc.redisclient import MsgHandler
        redis.setMsgCallback(MsgHandler())
        print("async connect success!!!" + str(redis))

        name, age = yield [RedisClientPool.get(redis, "name"), RedisClientPool.get(redis, "age")]
        print("got name " + str(name) + ", and age " + str(age))

        yield RedisClientPool.set(redis, "slogan", "fuck you maozedong")
        slogan = yield RedisClientPool.get(redis, "slogan")
        print("got slogan" + str(slogan))

    # start main loop
    sample_redis_client()
    mylog.debug("start")

    loop.start()
