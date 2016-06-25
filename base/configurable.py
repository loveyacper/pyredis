class Configurable(object):
    def __new__(cls, *arg, **kwargs):
        base = cls.base()
        impl = None
        if cls is base:
            impl = cls.instance()
        else:
            impl = cls
     
        return super(Configurable, cls).__new__(impl, *arg, **kwargs)

    @classmethod
    def base(cls):
        raise NotImplementedError()

    @classmethod
    def instance(cls):
        raise NotImplementedError()
