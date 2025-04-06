from typing import Callable


class Loop:
    __args: tuple
    __kwargs: dict
    __stop: bool = False

    @property
    def args(self):
        return self.__args

    @property
    def kwargs(self):
        return self.__kwargs

    def __init__(self, fn: Callable):
        self.__generator = fn(self)

    def __next__(self):
        if self.__stop:
            raise StopIteration

        return self

    def __call__(self, *args, **kwargs):
        self.run(*args, **kwargs)

    def run(self, *args, **kwargs):
        self.__args = args
        self.__kwargs = kwargs

        try:
            next(self.__generator)
        except StopIteration:
            self.__stop = True
