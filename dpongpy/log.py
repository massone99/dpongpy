import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dpongpy")


class Loggable:
    @classmethod
    def log(cls, template, *args, **kwargs):
        level = kwargs.get("level", logging.DEBUG)
        logger.log(level, f"[{cls.__name__}]{template}", *args)

    @classmethod
    def error(cls, template, *args, **kwargs):
        type = kwargs.get("type", RuntimeError)
        return type(f"[{cls.__name__}]{template}" % args)
