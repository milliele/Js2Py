import logging

from ..base import *

logger = logging.getLogger('Console')


@Js
def console():
    pass


@Js
def log():
    payload = ' '.join(map(lambda x: x.value, arguments.to_list()))
    logger.log(0, payload)


@Js
def debug():
    payload = ' '.join(map(lambda x: x.value, arguments.to_list()))
    logger.debug(payload)


@Js
def info():
    payload = ' '.join(map(lambda x: x.value, arguments.to_list()))
    logger.info(payload)


@Js
def warn():
    payload = ' '.join(map(lambda x: x.value, arguments.to_list()))
    logger.warning(payload)


@Js
def error():
    payload = ' '.join(map(lambda x: x.value, arguments.to_list()))
    logger.error(payload)


console.put('log', log)
console.put('debug', debug)
console.put('info', info)
console.put('warn', warn)
console.put('error', error)
