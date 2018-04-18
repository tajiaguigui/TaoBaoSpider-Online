import threading
import time

import re

import multiprocessing
import pymongo

from Spider_Online.config import MONGO_DB, MONGO_URL, QRCODE_COLLECTION, TAOBAO_COLLECTION

client = pymongo.MongoClient(MONGO_URL)
db = client[MONGO_DB]

import requests
from lxml import etree

from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.keys import Keys

from Spider_Online.util import page2html, verify_re_content, doesReElementExist, calculating_time
from Spider_Online.logger import get_logger

logger = get_logger('taobao', 'log/spider.log')


class Client(multiprocessing.Process):
    def __init__(self, socketid, uuid):
        """
        初始化
        :param socketid:
        :param uuid:
        """
        multiprocessing.Process.__init__(self)
        self.processID = self.pid  # 爬虫进程
        # 客户端唯一标识
        self.socketid = socketid  # 爬虫任务名
        # 用户唯一标识
        self.uuid = uuid
        self.driver = webdriver.Firefox()
        self.verify_switch = True
        self.flag = True  # 爬虫标志

        # 线程控制
        self.threads = []

        # 淘龄开关
        self.onoff = True

        # 用户信息
        self.userid = None  # 用户id
        self.username = ""  # 昵称
        self.userValue = '买家'  # 身价
        self.age = 28  # 年龄
        self.gender = "男"  # 性别
        self.credit = 0  # 信用
        self.authenticate = "已认证"  # 认证(有无认证)
        self.huaBei = "已开通"  # 花呗(有无开通)
        # 更新时间
        self.updateTime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))

        # 积分等级
        self.tmallPoint = 0  # 天猫积分
        self.memberLevel = '普通会员'  # 会员等级
        self.creditRating = ''  # 信誉评级

        self.cookie = {}  # 用户cookie
        self.pageSize = 20  # 单页订单数
        self.pageNum = 2  # 当前页
        self.prePageNo = 1  # 上一页

        # 订单相关(购物数据)
        self.totalNumber = 0  # 所有订单数
        self.waitPayNum = 0  # 待付款数
        self.waitSendNum = 0  # 待发货数
        self.waitConfirmNum = 0  # 待收货数
        self.waitRateNum = 0  # 待评价数
        self.orderData = []  # 订单信息

        # 浏览足迹
        self.footNum = 0

        # 喜好相关
        self.shopSum = 0  # 收藏店铺数
        self.shopInfo = []  # 店铺信息
        self.commoditySum = 0  # 收藏宝贝数
        self.commodityInfo = []  # 收藏宝贝信息

        # 买家信誉明细(评价)
        self.buyerGrandCredit = 0  # 买家累计信用
        self.praiseNum = 0  # 好评
        self.averageNum = 0  # 中评
        self.badReviewNum = 0  # 差评
        self.praiseRate = ''  # 好评率
        self.commentSum = 0  # 评论总数

        self.fileCache = None  # 缓存

        # 淘龄相关
        self.TaoAge = 0  # 淘龄
        self.registerTime = ''  # 开号日期
        self.squander = 0  # 挥霍
        self.casualtyDays = 0  # 散财天数
        self.occupyCity = 0  # 占领城市

    def get_cookie(self):
        """
        获取账号cookie
        :return: cookies
        """
        cookies = self.driver.get_cookies()
        for item in cookies:
            # logger.debug(cookie)
            self.cookie[item['name']] = item['value']
        self.driver.quit()
        return cookies

    def get_qrcode(self):
        """
        获取QRCode 170秒刷一次（覆盖入库信息）
        :return:
        """
        self.driver.get('https://login.taobao.com/member/login.jhtml')
        html = page2html(self.driver.page_source)
        time.sleep(1)
        qrcode_img = html.xpath('//div[@id="J_QRCodeImg"]/img/@src')
        logger.debug(qrcode_img)
        qrcode_img = str(qrcode_img[0])
        print(self.uuid)
        qrcode_data = {
            'socketid': self.socketid,
            'uuid': self.uuid,
            'qrcode': qrcode_img
        }
        self.save_to_mongo(qrcode_data, QRCODE_COLLECTION)
        return qrcode_img

    def login(self):
        """
        验证登录是否成功
        控制爬虫流程
        :return:
        """
        while self.verify_switch:
            self.verify_login()
            timer = time.time()
            while True:
                logger.debug('正在验证。。。')
                if int(timer - time.time()) > 180:
                    logger.debug('爬虫进程等待扫码超时，已退出')
                    self.driver.quit()
                    return
                time.sleep(3)
                try:
                    if verify_re_content(r'待收货', self.driver.page_source):
                        logger.debug('验证成功,开始爬取数据')
                        index = etree.HTML(self.driver.page_source)
                        self.userid = index.xpath('//span[@class="member-nick-info"]/strong/text()')
                        if self.userid:
                            self.userid = self.userid[0]
                            print(self.userid)
                        # 获取cookies
                        cookies = self.driver.get_cookies()
                        time.sleep(10)
                        for item in cookies:
                            # print(cookie)
                            self.cookie[item['name']] = item['value']
                        # 任务改成并行
                        self.browse_foot()  # 获取足迹
                        self.get_comment()  # 获取收藏
                        self.get_info()  # 获取个人信息
                        self.get_order()  # 获取订单信息
                        self.get_like_data()  # 获取喜好信息
                        # for t in self.threads:
                        #     t.start()
                        #     t.join()
                        self.save_to_mongo(self.data2json(), TAOBAO_COLLECTION)
                        # self.driver.quit()
                        self.verify_switch = False
                        break
                    verify = int(time.time() - timer)
                    if verify > 170:
                        break
                except TypeError as e:
                    logger.debug(e)

    # 浏览器爬取足迹
    def browse_foot(self):
        # is_login = driver.find_element_by_id('q')
        logger.debug('开始爬取足迹')
        foot_url = 'https://www.taobao.com/markets/footmark/tbfoot'
        self.driver.get(foot_url)
        time.sleep(2)
        refresh_num = 0
        while True:
            try:
                if doesReElementExist(r'今天', self.driver.page_source):
                    logger.debug('refresh successful')
                    break
                self.driver.get(foot_url)
                refresh_num += 1
                logger.debug('refresh failure')
                time.sleep(2)
                if refresh_num > 5:
                    # 浏览足迹为空
                    self.footNum = 0
                    self.driver.quit()
                    return
            except Exception:
                logger.debug("Exception not found")
                time.sleep(3)

        for i in range(13):
            self.driver.execute_script('window.scrollTo(0, document.body.scrollHeight)')
            ActionChains(self.driver).key_down(Keys.DOWN).perform()
            time.sleep(1)
        time.sleep(2)
        html = etree.HTML(self.driver.page_source)
        # items = html.xpath("//div[@class='item-box J_goods']")
        title = html.xpath("//div[@class='item-box J_goods']//div[@class='title']/text()")
        self.footNum = len(title)
        for i in title:
            logger.debug(str(i).split()[0])
        # driver.execute_script("window.scrollTo(0,document.body.scrollHeight)")
        logger.debug('下拉到底部success')
        self.driver.quit()

    # 验证是否登录成功
    def verify_login(self):
        if verify_re_content(r'待收货', self.driver.page_source):
            self.verify_switch = False
            return
        # 否则重新获取QRode
        else:
            self.get_qrcode()  # 第一次
            self.verify_switch = True
            return

    # 获取用户信息
    def get_info(self):
        user_url = 'https://member1.taobao.com/member/fresh/account_security.htm'
        # resp = requests.get(url=user_url, cookies=self.get_cookies())
        resp = requests.get(url=user_url)
        html = etree.HTML(resp.content)
        try:
            # 用户认证
            self.authenticate = \
                html.xpath('//*[@id="main-content"]/dl/dd[3]/ul/li[1]/div[1]/span/text()')
            if self.authenticate:
                self.authenticate = self.authenticate[0]
            else:
                self.authenticate = u'已认证'
            if self.authenticate == u"已完成":
                self.authenticate = u'已认证'
                logger.debug(self.authenticate)
            user = html.xpath('//*[@id="main-content"]/dl/dd[1]/ul/li[1]/span[2]/text()')
            logger.debug(user)
            info_url = 'https://i.taobao.com/user/baseInfoSet.htm'
            resp = requests.get(url=info_url, cookies=self.cookie)
            self.fileCache = resp.text
            html = etree.HTML(resp.content)
            name = html.xpath('//*[@id="J_uniqueName-mask"]/@value')
            if len(name) >= 1:
                self.username = name[0]

            pattern = re.compile(r'selected="selected".*?>(.*?)</option>')
            result = re.findall(pattern, resp.text)
            if result:
                logger.debug(result[0])
                # self.age = 2018 - int(result[0])
            logger.debug('获取用户信息成功')
        except IndexError as e:
            logger.debug('获取用户信息数组下标越界', e)
            self.flag = False

    # 获取所有订单
    def get_order(self):
        # form_data = 'pageNum=2&pageSize=15&prePageNo=1'
        logger.debug('开始获取所有订单')
        order_url = 'https://buyertrade.taobao.com/trade/itemlist/asyncBought.htm'
        form_data = {
            'pageNum': self.pageNum,
            'pageSize': self.pageSize,
            'prePageNo': self.prePageNo,
        }
        Header = {
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'accept-encoding': 'gzip, deflate, br',
            'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'content - length': '33',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': 'https://buyertrade.taobao.com',
            'referer': 'https://buyertrade.taobao.com/trade/itemlist/list_bought_items.htm',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36',
            'x-requested-with': 'XMLHttpRequest',
        }
        try:
            response = requests.post(url=order_url, headers=Header, cookies=self.cookie, data=form_data)
            if response.status_code == 200:
                if response:
                    data = response.json()
                    if data:
                        if data.get('error') == "":
                            self.pageNum = int(data.get('page').get('currentPage')) + 1
                            self.totalNumber = data.get('page').get('totalNumber')
                            tabs = data.get('tabs')
                            if tabs[1].get('count'):
                                self.waitPayNum = tabs[1].get('count')
                            if tabs[2].get('count'):
                                self.waitSendNum = tabs[2].get('count')
                            if tabs[3].get('count'):
                                self.waitConfirmNum = tabs[3].get('count')
                            self.waitRateNum = tabs[4].get('count') if tabs[4].get('count') else self.waitRateNum

                            orders = data.get('mainOrders')
                            for order in orders:
                                # 进一步解析订单内容
                                shopName = order.get('seller').get('shopName')
                                shopUrl = order.get('seller').get('shopUrl')
                                payInfo = order.get('payInfo').get('actualFee')
                                statusInfo = order.get('statusInfo').get('text')
                                Item = {}
                                for item in order.get('subOrders'):
                                    itemTitle = item.get('itemInfo').get('title')
                                    itemUrl = item.get('itemInfo').get('itemUrl')
                                    itemPic = item.get('itemInfo').get('pic')
                                    price = item.get('priceInfo').get('realTotal')
                                    Item = {
                                        'itemTitle': itemTitle,
                                        'itemUrl': itemUrl,
                                        'itemPic': itemPic,
                                        'price': price,
                                    }
                                Order = {
                                    'shopName': shopName,
                                    'shopUrl': shopUrl,
                                    'payInfo': payInfo,
                                    'statusInfo': statusInfo,
                                    'item': Item,
                                }
                                self.orderData.append(Order)
                        else:
                            logger.debug('解析订单Error')
                            raise Exception
                    else:
                        logger.debug('订单记录空')
            try:
                if self.onoff:
                    self.pageNum = int(data.get('page').get('totalPage'))
                    self.prePageNo = self.pageNum - 1
                    form_data = {
                        'pageNum': self.pageNum,
                        'pageSize': self.pageSize,
                        'prePageNo': self.prePageNo,
                    }
                    response = requests.post(url=order_url, headers=Header, cookies=self.cookie,
                                             data=form_data)
                    if response.status_code == 200:
                        if response:
                            data = response.json()
                            if data.get('error') == "":
                                order = data.get('mainOrders')
                                item = order[len(order) - 1]
                                createDay = item.get('orderInfo').get('createDay')
                                logger.debug(createDay)
                                self.registerTime = createDay
                                self.TaoAge = calculating_time(createDay)
                                self.casualtyDays = calculating_time(createDay)
                                logger.debug('获取淘龄结束')
            except Exception as e:
                logger.debug('获取淘龄信息Error', e)
        except Exception as e:
            logger.debug('获取所有订单Error', e)
            self.flag = False
        logger.debug(self.totalNumber)

    # 获取用户喜好数据（收藏）
    def get_like_data(self):
        logger.debug('开始抓取用户喜好数据')
        for row in range(0, 100):
            row = row * 6
            now = int(time.time() * 1000)
            collect_shop_url = 'https://shoucang.taobao.com/nodejs/shop_collect_list_chunk.htm?ifAllTag=0&tab=0&categoryCount=0&tagName=&type=0&categoryName=&needNav=false&startRow={row}&t={time}'.format(
                row=row, time=now)
            response = requests.get(url=collect_shop_url, cookies=self.cookie)
            try:
                if re.search('\S', response.content.decode()):
                    html = etree.HTML(response.content.decode())
                    collect_shopname = html.xpath('//a[@class="shop-name-link"]/@title')
                    collect_shopurl = html.xpath('//a[@class="shop-name-link"]/@href')
                    collect_shoppic = html.xpath('//div[@class="logo J_ShopClassTri"]/a/img/@src')
                    for i in range(0, len(collect_shopname)):
                        collect_shop = {
                            '店铺名': collect_shopname[i],
                            '店铺地址': collect_shopurl[i],
                            '店铺logo': collect_shoppic[i],
                        }
                        self.shopInfo.append(collect_shop)

                    # print(collect_shopname)
                    self.shopSum += len(collect_shopname)
                else:
                    # logger.debug('shop_sum', self.shopSum)
                    break
            except UnicodeDecodeError as e:
                logger.debug('获取用户收藏店铺 编码格式错误', e)
                self.flag = False
                return
        for row in range(0, 100):
            row = row * 30
            now = int(time.time() * 1000)
            collect_commodity_url = 'https://shoucang.taobao.com/nodejs/item_collect_chunk.htm?ifAllTag=0&tab=0&tagId=&categoryCount=0&type=0&tagName=&categoryName=&needNav=false&startRow={row}&t={time}'.format(
                row=row, time=now)
            response = requests.get(url=collect_commodity_url, cookies=self.cookie)
            try:
                if re.search('\S', response.content.decode()):
                    html = etree.HTML(response.content.decode())
                    collect_commodity_name = html.xpath('//li/div[2]/a/text()')
                    collect_commodity_pic = html.xpath('//img[@class="img-controller-img"]/@src')
                    collect_commodity_url = html.xpath('//a[@class="img-controller-img-link"]/@href')
                    # collect_commodity_price = html.xpath('//div[@class="g_price"]/strong/text()')
                    try:
                        for i in range(0, len(collect_commodity_name)):
                            collect_commodity = {
                                '宝贝名': collect_commodity_name[i],
                                '宝贝图片': collect_commodity_pic[i],
                                '宝贝地址': collect_commodity_url[i],
                                # '宝贝价格': collect_commodity_price[i],
                            }
                            self.commodityInfo.append(collect_commodity)
                        logger.debug(collect_commodity_name)
                    except IndexError as e:
                        logger.debug('下标越界', e)
                    self.commoditySum += len(collect_commodity_name)
                else:
                    # logger.debug('commodity_sum', self.commoditySum)
                    break
            except UnicodeDecodeError as e:
                logger.debug('获取用户收藏宝贝 编码格式错误', e)
                self.flag = False
                return
        dict = {
            '收藏的宝贝': self.commoditySum,
            '收藏的店铺': self.shopSum,
        }
        logger.debug('获取用户喜好数据结束')
        logger.debug(dict)
        return dict

    # 获取好中差评数
    def get_comment(self):
        logger.debug('开始获取好中差评数')
        try:
            comment_url = 'https://rate.taobao.com/myRate.htm'
            resp = requests.get(url=comment_url, cookies=self.cookie)
            html = etree.HTML(resp.content)
            xinyong = html.xpath('//*[@id="new-rate-content"]/div[1]/div[2]/h4[2]/a[1]/text()')
            comment = html.xpath('//*[@id="new-rate-content"]/div[1]/div[2]/p/strong/text()')
            hao_num = html.xpath('//*[@id="new-rate-content"]/div[1]/div[2]/table[2]/tbody/tr[1]/td[6]/text()')
            zhong_num = html.xpath('//*[@id="new-rate-content"]/div[1]/div[2]/table[2]/tbody/tr[2]/td[6]/text()')
            cha_num = html.xpath('//*[@id="new-rate-content"]/div[1]/div[2]/table[2]/tbody/tr[3]/td[6]/text()')
            sum = html.xpath('//*[@id="new-rate-content"]/div[1]/div[2]/table[2]/tbody/tr[4]/td[6]/text()')
            self.buyerGrandCredit = int(xinyong[0])
            self.praiseRate = comment[0]
            self.praiseNum = int(hao_num[0])
            self.averageNum = int(zhong_num[0])
            self.badReviewNum = int(cha_num[0])
            self.commentSum = int(sum[0])
            logger.debug('获取评价成功')
        except IndexError as e:
            logger.debug('获取好中差评数 数组下标越界', e)
            self.flag = False

    def data2json(self):
        data = {
            'status': 'success',
            'socketid': self.socketid,
            'uuid': self.uuid,
            'userid': self.userid,
            'data': {
                'user_info': {
                    '身价': self.userValue,
                    '昵称': self.username,
                    '性别': self.gender,
                    '年龄': self.age,
                    '信用': self.credit,
                    '认证': self.authenticate,
                    '花呗': self.huaBei,
                    '更新时间': self.updateTime,
                },
                'user_like': {
                    '收藏的宝贝': self.commoditySum,
                    '收藏的宝贝信息': self.commodityInfo,
                    '收藏的店铺': self.shopSum,
                    '收藏的店铺信息': self.shopInfo,
                },
                'user_foot': {
                    '浏览足迹': self.footNum,
                },
                'order_info': {
                    '所有订单数': self.totalNumber,
                    '待付款数': self.waitPayNum,
                    '待发货数': self.waitSendNum,
                    '待收货数': self.waitConfirmNum,
                    '待评价数': self.waitRateNum,
                    '订单记录': self.orderData,
                },
                'user_comment': {
                    '买家信用': self.buyerGrandCredit,
                    '好评率': self.praiseRate,
                    '好评': self.praiseNum,
                    '中评': self.averageNum,
                    '差评': self.badReviewNum,
                    '总计': self.commentSum,
                },
                'amoy_age': {
                    '淘龄': self.TaoAge,
                    '开号': self.registerTime,
                    '挥霍': self.squander,
                    '笔数': self.totalNumber,
                    '散财天数': self.casualtyDays,
                    '点赞总数': 0,
                    '占领城市': self.occupyCity,
                },
            },
        }
        logger.debug(data)
        return data

    def save_to_mongo(self, result, collection):
        """

        :param result: 需要入库的数据
        :param collection: 需要入到哪张表
        :return: 入库结果
        """
        try:
            if db[collection].insert(result):
                logger.debug('存储到MongoDB成功', result)
        except Exception:
            logger.debug('存储到MongoDB失败')

    def run(self):
        self.login()

#
# c = Client('sadafaehuhiuhb', '128798798adkjhk7788')
# c.start()
