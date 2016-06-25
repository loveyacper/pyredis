# pyredis
A redis client based on tornado future and coroutine

### totally asynchronous, looks like await/async

```python
# the @coroutine looks like async keyword
@coroutine
def sample_redis_client(port = 6379):
    # get connection, may from pool, may async connect to redis, whatever
    redis = yield RedisClientPool.getConn(port = port)

    # set the protocol parser
    from redisc.redisclient import MsgHandler
    redis.setMsgCallback(MsgHandler())

    # get remote slogon from redis, yield looks like await keyword
    slogan = yield RedisClientPool.get(redis, "slogan")

    # you can get multiple keys from redis concurrently!!!
    name, age = yield [RedisClientPool.get(redis, "name"), RedisClientPool.get(redis, "age")]
    print("got from redis : name " + str(name) + ", and age " + str(age))
```

### TODO
These code is just draft, too much work todo.

inspiration from facebook folly future library, and tornado source code
