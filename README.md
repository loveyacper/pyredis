# pyredis
A redis client based on tornado coroutine

### totally asynchronous, looks like await/async

```python

from redisc.redisclient import RedisPool
pool = RedisPool()

# the @coroutine looks like keyword async
@coroutine
def example(port = 6379):

    # get connection, may from pool, may async connect to redis, whatever
    redis = yield pool.getConn(port = port)
    print("async connect return success, connection: " + str(redis))

    # get slogan from redis, yield looks like keyword await
    slogan = yield redis.get(redis, "slogan")

    # you can get multiple keys from redis concurrently!!!
    name, age = yield [redis.get(redis, "name"), redis.get(redis, "age")]
    print("got from redis : name " + str(name) + ", and age " + str(age))

    pool.freeConn(redis)
```

### TODO
These code is just draft, too much work todo.

inspiration by facebook folly future library, and tornado source code
