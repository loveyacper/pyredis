#!/usr/bin/env python

import signal
import sys

from base.ioloop import IOLoop
from redisc.redisclient import RedisPool


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

    from redisc.redisclient import RedisPool
    pool = RedisPool()

    # async
    @coroutine
    def example1(port = 6379):

        redis = yield pool.getConn(port = port) # await
        print("async connect success!!!" + str(redis))

        name, age = yield [redis.get("name"), redis.get("age")]
        print("got name " + str(name) + ", and age " + str(age))

        yield redis.set("slogan", "we'll rock you")
        slogan = yield redis.get("slogan")
        print("got slogan" + str(slogan))

        pool.freeConn(redis)
        loop.call_later(2, example2)

    @coroutine
    def example2(port = 6379):
        redis = yield pool.getConn(port = port)

        multi = yield redis.multi()
        print("multi result " + str(multi))
        yield redis.multi()

        res = yield redis.get("name")
        print("expect queued " + str(res))

        res = yield redis.set("slogan", "we'll rock you2")
        print("expect queued " + str(res))

        #res = yield redis.discard()
        #print("expect OK" + str(res))

        results = yield redis.execute()
        print("multi results " + str(results))

        pool.freeConn(redis)

    # start main loop
    example1()
    mylog.debug("start")

    loop.start()

