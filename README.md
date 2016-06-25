# pyredis
A redis client based on tornado future and coroutine

### totally asynchronous, looks like await/async

```python
# the @coroutine looks like async keyword
@coroutine
def sample_redis_client(port = 6379):
    from redisc.redisclient import MsgHandler, getConn, get, set

    # get connection, may from pool, may async connect to redis, whatever
    redis = yield getConn(port = port)

    # set the protocol parser
    redis.setMsgCallback(MsgHandler())

    # get remote slogon from redis, yield looks like await keyword
    slogan = yield get(redis, "slogan")

    # you can get multiple keys from redis concurrently!!!
    name, age = yield [get(redis, "name"), get(redis, "age")]
    print("got from redis : name " + str(name) + ", and age " + str(age))
```

### TODO
These code is just draft, too much work todo.

inspiration from facebook folly future library, and tornado source code
