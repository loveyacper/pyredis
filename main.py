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
        from redisc.redisclient import getConn, get, set

        redis = yield getConn(port = port)
        print("async connect success!!!" + str(redis))

        name, age = yield [get(redis, "name"), get(redis, "age")]
        print("got name " + str(name) + ", and age " + str(age))

        yield set(redis, "slogan", "fuck you maozedong")
        slogan = yield get(redis, "slogan")
        print("got slogan" + str(slogan))

    # start main loop
    sample_redis_client()
    mylog.debug("start")

    loop.start()
