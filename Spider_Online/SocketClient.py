import threading
import multiprocessing
import time

import pymongo

from Spider_Online.SpiderClient import Client
from Spider_Online.logger import get_logger
from socketIO_client import SocketIO
from Spider_Online.util import verify_re_content
from Spider_Online.config import MONGO_DB, MONGO_URL, QRCODE_COLLECTION, TAOBAO_COLLECTION

# 服务器
# socketIO = SocketIO('193.112.75.62', 3000, wait_for_connection=False)

# 本地
socketIO = SocketIO('192.168.2.133', 3000, wait_for_connection=False)

client = pymongo.MongoClient(MONGO_URL)
db = client[MONGO_DB]

logger = get_logger('taobao', 'log/socket.log')


def connect():
    """
    client七个状态:
    10001:  开始连接
    10002:  连接成功
    10003:  二维码发送
    10004:  二维码扫码成功
    10005:  开始爬虫
    10006:  爬虫结果成功
    10007:  爬虫失败
    :return: result
    """
    try:
        # 建立连接
        socketIO.emit('10001')
        socketIO.on('20000', receive)
        # socketIO.on('on', on_connect_response)
        # 第一次请求，不停的put二维码
        # while True:
        #     # 新启一个线程
        #     socketIO.on('msg', put_qrcode)
        #
        #     time.sleep(25)
        #     return
        # socketIO.on('msg', crawl_data)
        socketIO.wait()
    except ConnectionError:
        logger.debug('服务器关闭')


def receive(*args):
    logger.debug('已连接')
    print(args)
    signal = args[0].get('status')
    socketid = args[0].get('socketid')
    print(socketid)
    uuid = args[0].get('uuid')
    print(uuid)
    # logger.debug(socketid, )
    if signal == '20001':
        logger.debug('20001')
        # socketIO.emit('10002')
        pass
    elif signal == '20002':
        pass
    # 获取二维码（调起爬虫进程）
    elif signal == '20003':
        logger.debug('20003')
        process = Client(socketid, uuid)
        process.start()
    # 从库里查找二维码返回
    elif signal == '20004':
        logger.debug('20004')
        # data = db.qrcode.find({'socketid': socketid})[0]
        # logger.debug('已发送二维码url')
        # socketIO.emit('10004', data)
        pass
    # 查号
    elif signal == '20005':
        logger.debug('20005')
        # 从库里面抛出查号信息
        # result = db.result.find({'socketid': socketid})[0]
        # if result:
        # data = {
        #     'status': '10006',
        #     'socketid': socketid,
        #     'data': result
        # }
        # socketIO.emit('10006', result)
        # else:
        #     data = {
        #         'status': '10007',
        #         'socketid': socketid,
        #         'data': 'failure'
        #     }
        #     socketIO.emit('10007', data)
        pass


connect()
