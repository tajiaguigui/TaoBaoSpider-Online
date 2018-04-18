import datetime
import re

import time
from lxml import etree
from selenium.common.exceptions import NoSuchElementException


def page2html(page):
    html = etree.HTML(page)
    return html


def verify_re_content(pattern, html):
    result = re.search(pattern, html, re.S)
    if result:
        return True
    else:
        return False


def doesWebElementExist(driver, selector, type):
    try:
        if type == 1:
            driver.find_element_by_id(selector)
            return True
        if type == 2:
            driver.find_element_by_class_name(selector)
            print('找到class')
            return True
        if type == 3:
            driver.find_element_by_css_selector(selector)
            return True
    except NoSuchElementException:
        return False


def doesReElementExist(pattern, html):
    result = re.search(pattern, html, re.S)
    if result:
        return True
    else:
        return False


def calculating_time(date):
    now = time.strftime('%Y-%m-%d', time.localtime(time.time()))
    d1 = datetime.datetime.strptime(date, '%Y-%m-%d')
    d2 = datetime.datetime.strptime(now, '%Y-%m-%d')
    delta = d2 - d1
    return delta.days
