# coding:utf-8
from logging.handlers import *
import colorlog  # 控制台日志输入颜色
import time
import os
import properties
import types
import sys


class LocalTimedRotatingFileHandler(TimedRotatingFileHandler):

    def __init__(self, filename, when = 'h', interval = 1, backupCount = 0, encoding = None,
                 delay = False, utc = False, atTime = None):
        TimedRotatingFileHandler.__init__(self, filename, when, interval, backupCount, encoding, delay, utc, atTime)

    def getFilesToDelete(self):
        dirName, baseName = os.path.split(self.baseFilename)
        fileNames = os.listdir(dirName)
        result = []
        fileMeta = os.path.splitext(baseName)
        prefix = fileMeta[0] + '-'
        plen = len(prefix)
        for fileName in fileNames:
            if fileName[:plen] == prefix:
                suffix = fileName[plen:-len(fileMeta[1])]
                if self.extMatch.match(suffix):
                    result.append(os.path.join(dirName, fileName))
        if len(result) < self.backupCount:
            result = []
        else:
            result.sort()
            result = result[:len(result) - self.backupCount]
        return result

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        # get the time that this sequence started at and make it a TimeTuple
        currentTime = int(time.time())
        dstNow = time.localtime(currentTime)[-1]
        t = self.rolloverAt - self.interval
        if self.utc:
            timeTuple = time.gmtime(t)
        else:
            timeTuple = time.localtime(t)
            dstThen = timeTuple[-1]
            if dstNow != dstThen:
                if dstNow:
                    addend = 3600
                else:
                    addend = -3600
                timeTuple = time.localtime(t + addend)
        # dfn = self.rotation_filename(self.baseFilename + "." +
        #                              time.strftime(self.suffix, timeTuple))
        baseName = os.path.split(self.baseFilename)[1]
        fileMeta = os.path.splitext(baseName)
        dfn = fileMeta[0] + '-' + time.strftime(self.suffix, timeTuple) + fileMeta[1]

        if os.path.exists(dfn):
            os.remove(dfn)
        self.rotate(self.baseFilename, dfn)
        if self.backupCount > 0:
            for s in self.getFilesToDelete():
                os.remove(s)
        if not self.delay:
            self.stream = self._open()
        newRolloverAt = self.computeRollover(currentTime)
        while newRolloverAt <= currentTime:
            newRolloverAt = newRolloverAt + self.interval
        # If DST changes and midnight or weekly rollover, adjust for this.
        if (self.when == 'MIDNIGHT' or self.when.startswith('W')) and not self.utc:
            dstAtRollover = time.localtime(newRolloverAt)[-1]
            if dstNow != dstAtRollover:
                if not dstNow:  # DST kicks in before next rollover, so we need to deduct an hour
                    addend = -3600
                else:  # DST bows out before next rollover, so we need to add an hour
                    addend = 3600
                newRolloverAt += addend
        self.rolloverAt = newRolloverAt


class LoggerFactory:
    logColors = {
        'DEBUG': 'white',
        'INFO': 'white',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red',
    }

    # 读取配置文件log.properties
    prop = properties.parse('../../resources/log.properties')
    config = {}
    for key, value in prop.properties.items():
        if key.find('.') > 0:
            keys = key.split('.')
            if keys[0] == 'appender' and len(keys) > 1:
                if len(keys) == 3:
                    if keys[0] not in config:
                        config[keys[0]] = {}
                    if keys[1] not in config[keys[0]]:
                        config[keys[0]][keys[1]] = {}
                    config[keys[0]][keys[1]][keys[2]] = value
            if keys[0] == 'logger' and len(keys) > 1:
                if keys[0] not in config:
                    config[keys[0]] = {}
                config[keys[0]][key[len(keys[0]) + 1:]] = value
        else:
            config[key] = value

    # 初始化根rootLogger
    defaltLevel = logging.INFO
    if 'rootLogger' in config and config['rootLogger'].upper() in logging._nameToLevel:
        defaltLevel = logging._nameToLevel[config['rootLogger'].upper()]

    rootLogger = logging.getLogger()
    rootLogger.setLevel(defaltLevel)
    for key, handlerCfg in config['appender'].items():
        level = logging.INFO
        if 'level' in handlerCfg and handlerCfg['level'].upper() in logging._nameToLevel:
            level = logging._nameToLevel[handlerCfg['level'].upper()]

        file = './log.txt'
        if 'file' in handlerCfg:
            file = handlerCfg['file']

        maxBytes = 1024 * 1  # 默认文件大小为5M
        if 'maxBytes' in handlerCfg:
            maxBytes = handlerCfg['maxBytes']

        backups = 5  # 默认保留日志文件数
        if 'backups' in handlerCfg:
            backups = handlerCfg['backups']

        formatter = logging.BASIC_FORMAT
        if 'formatter' in handlerCfg:
            formatter = handlerCfg['formatter']

        if handlerCfg['type'] == 'file':
            formatter = logging.Formatter(formatter)

            # 使用RotatingFileHandler类，滚动备份日志
            # handler = RotatingFileHandler(filename = file,
            #                               mode = 'a',
            #                               encoding = 'utf-8',
            #                               maxBytes = maxBytes,
            #                               backupCount = backups)

            handler = LocalTimedRotatingFileHandler(filename = file,
                                                    when = "MIDNIGHT",
                                                    interval = 1,
                                                    backupCount = backups,
                                                    encoding = 'UTF-8')

            handler.set_name(key)
            handler.setLevel(level)
            handler.setFormatter(formatter)
            rootLogger.addHandler(handler)

        elif handlerCfg['type'] == 'console':
            formatter = colorlog.ColoredFormatter('%(log_color)s' + formatter, log_colors = logColors)
            handler = colorlog.StreamHandler()
            handler.set_name(key)
            handler.setLevel(level)
            handler.setFormatter(formatter)
            rootLogger.addHandler(handler)

    pkgLevel = {}
    if 'logger' in config:
        pkgLevel = config['logger']

    @staticmethod
    def getLogger(klass = None):
        _name = None
        if klass is None:
            pass
        elif isinstance(klass, str):
            _name = klass
        elif isinstance(type(klass), object):
            _name = type(klass).__name__

        logger = logging.getLogger(_name)

        if _name:
            level = LoggerFactory.defaltLevel
            lenth = len(_name)
            levelName = None
            for path in LoggerFactory.pkgLevel:
                if _name.startswith(path):
                    if path == _name:
                        levelName = LoggerFactory.pkgLevel[path]
                        break
                    elif _name.startswith(path + '.') and len(path) < lenth:
                        lenth = len(path)
                        levelName = LoggerFactory.pkgLevel[path]

            if levelName and levelName.upper() in logging._nameToLevel:
                level = logging._nameToLevel[levelName.upper()]
            logger.setLevel(level)

        return logger


if __name__ == "__main__":
    log = LoggerFactory.getLogger()
    log.debug("---测试开始----")
    log.info("操作步骤")
    log.warning("----测试结束----")
    log.error("----测试错误----")

    log = LoggerFactory.getLogger('test')
    log.debug("---测试开始----")
    log.info("操作步骤")
    log.warning("----测试结束----")
    log.error("----测试错误----")
