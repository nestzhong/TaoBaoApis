'''
Description: 
Date: 2026-04-04 15:32:48
LastEditTime: 2026-04-06 19:10:56
FilePath: \TaobaoApis\taobao_apis.py
'''
import json
import os
import re
import time

import requests

from utils.taobao_utils import generate_sign, trans_cookies, generate_device_id


BUYER_HEADERS = {
    "accept": "application/json",
    "accept-language": "en,zh-CN;q=0.9,zh;q=0.8,zh-TW;q=0.7,ja;q=0.6",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}


class TaobaoApis:
    def __init__(self, cookies, device_id):
        self.login_url = 'https://h5api.m.taobao.com/h5/mtop.taobao.login.token.get.h5/2.0/'
        self.upload_media_url = 'https://stream-upload.taobao.com/api/upload.api'
        self.refresh_token_url = 'https://h5api.m.goofish.com/h5/mtop.taobao.idlemessage.pc.loginuser.get/1.0/'
        self.item_detail_url = 'https://h5api.m.goofish.com/h5/mtop.taobao.idle.pc.detail/1.0/'
        self.reset_login_info_url = 'https://passport.goofish.com/newlogin/hasLogin.do'
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.cookies.update(cookies)
        self.device_id = device_id
        self.cookies = {}
        self._token_refreshed = False

    def _ensure_token(self):
        if self._token_refreshed:
            return True
        res = self.get_token()
        if res.get("ret", [""])[0] == "SUCCESS::调用成功":
            self._token_refreshed = True
            return True
        return False

    def _sign_data(self, data):
        token = self.session.cookies['_m_h5_tk'].split('_')[0]
        t = str(int(time.time() * 1000))
        data_str = json.dumps(data, separators=(',', ':'))
        sign = generate_sign(t, token, data_str)
        return t, sign, data_str

    def _parse_jsonp(self, text):
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        text = re.sub(r'^[\w]+\(', '', text)
        text = text.rstrip(')')
        return json.loads(text)

    def _mtop_request(self, api, version, data, data_in_url=True, referer=None, ttid="600000@taobao_android_10.7.0", extra_params=None):
        t, sign, data_str = self._sign_data(data)
        url = f'https://h5api.m.taobao.com/h5/mtop.{api}/{version}/'

        headers = dict(BUYER_HEADERS)
        headers["Origin"] = "https://main.m.taobao.com"
        if referer:
            headers["Referer"] = referer

        params = {
            "jsv": "2.6.1",
            "appKey": "12574478",
            "t": t,
            "sign": sign,
            "api": api,
            "v": version,
            "type": "jsonp",
            "dataType": "jsonp",
            "callback": "mtopjsonp1",
            "H5Request": "true",
            "preventFallback": "true",
        }
        if ttid:
            params["ttid"] = ttid
        if extra_params:
            params.update(extra_params)
        if params.get("type", "").startswith("original"):
            params.pop("callback", None)

        if data_in_url:
            params["data"] = data_str
            response = self.session.get(url, params=params, headers=headers, verify=False)
        else:
            response = self.session.post(url, params=params, data={"data": data_str}, headers=headers, verify=False)

        return self._parse_jsonp(response.text)

    def search_products(self, keyword, page_no=1, page_size=20, sort=None):
        params_obj = {"q": keyword, "page": page_no, "n": str(page_size)}
        defaults = {
            "appId": "29859", "style": "wf", "m": "h5",
            "isBeta": "false", "needTabs": "true",
            "schemaType": "auction", "channelSrp": "",
            "tab": "all", "sversion": "21.7", "vm": "nw",
            "sugg": "_4_1", "newSearch": "false",
            "search_action": "initiative", "searchDoorFrom": "srp",
            "homePageVersion": "v7", "searchElderHomeOpen": "false",
            "prepositionVersion": "v2", "areaCode": "CN",
            "client_os": "Android", "device": "HMA-AL00",
            "network": "wifi", "gpsEnabled": "false",
            "from": "", "hasPreposeFilter": "false",
            "isEnterSrpSearch": "true", "grayHair": "false",
            "brand": "HUAWEI", "info": "wifi", "index": "4",
            "elderHome": "false", "subtype": "", "rainbow": "",
            "debug_rerankNewOpenCard": "false", "tagSearchKeyword": None,
            "sort": "_coefp", "filterTag": "", "prop": "", "item_id": "",
        }
        defaults.update(params_obj)
        if sort:
            defaults["sort"] = sort
        data = {
            "appId": "29859",
            "params": json.dumps(defaults, ensure_ascii=False, separators=(',', ':')),
        }
        return self._mtop_request(
            "relationrecommend.WirelessRecommend.recommend", "2.0", data,
            data_in_url=True, referer="https://s.m.taobao.com/",
        )

    def parse_search_results(self, response):
        data = response.get("data", {})
        items = data.get("itemsArray", [])
        result = {
            "total_results": data.get("totalResults", 0),
            "page": data.get("page", 1),
            "page_size": data.get("pageSize", 20),
            "total_page": data.get("totalPage", 1),
            "items": [],
        }
        for item in items:
            shop_info = item.get("shopInfo", {})
            shop_list = shop_info.get("shopInfoList", []) if isinstance(shop_info, dict) else []
            price_show = item.get("priceShow", {})
            parsed = {
                "item_id": item.get("item_id"),
                "title": item.get("title", ""),
                "price": price_show.get("price", "") if isinstance(price_show, dict) else item.get("price", ""),
                "price_unit": price_show.get("unit", "¥") if isinstance(price_show, dict) else "¥",
                "pic_url": item.get("pic_path", ""),
                "shop_name": shop_list[0] if shop_list else "",
                "is_b2c": item.get("isB2c") == "1",
                "is_p4p": item.get("isP4p") == "true",
                "nidlong": item.get("nidlong", ""),
                "mi_id": item.get("mi_id", ""),
                "sales_count": item.get("sameCount", ""),
                "location": item.get("localPrice", {}).get("location", "") if isinstance(item.get("localPrice"), dict) else "",
            }
            result["items"].append(parsed)
        return result

    def get_cart_list(self):
        ex_params = {"mergeCombo": "true", "version": "1.1.1", "globalSell": "1", "dataformat": "dataformat_ultron_h5"}
        data = {
            "isPage": True, "extStatus": 0, "netType": 0,
            "exParams": json.dumps(ex_params, separators=(',', ':')),
            "dataformat": "dataformat_ultron_h5",
        }
        return self._mtop_request(
            "trade.query.bag", "5.0", data, data_in_url=False,
            referer="https://main.m.taobao.com/cart/index.html",
            ttid="h5", extra_params={"type": "originaljson", "isSec": "0", "ecode": "1", "AntiFlood": "true", "AntiCreep": "true"},
        )

    def add_to_cart(self, item_id, sku_id=None, quantity=1):
        data = {"itemId": str(item_id), "quantity": quantity, "dataformat": "dataformat_ultron_h5"}
        if sku_id:
            data["skuId"] = str(sku_id)
        return self._mtop_request(
            "trade.cart.add", "1.0", data, data_in_url=False,
            referer="https://main.m.taobao.com/", ttid="h5",
            extra_params={"isSec": "0", "ecode": "1"},
        )

    def get_order_list(self, page_no=1, page_size=10, status=None):
        tab_code = status or "all"
        condition = json.dumps({"directRouteToTm2Scene": "1"}, separators=(',', ':'))
        data = {
            "tabCode": tab_code, "page": page_no, "OrderType": "OrderList",
            "appName": "tborder", "appVersion": "3.0",
            "condition": condition,
            "__needlessClearProtocol__": True,
        }
        return self._mtop_request(
            "taobao.order.queryboughtlistv2", "1.0", data, data_in_url=False,
            referer="https://buyertrade.taobao.com/",
            extra_params={
                "type": "originaljson", "valueType": "original",
                "ecode": "1", "timeout": "8000", "needLogin": "true",
                "needRetry": "true", "isHttps": "1",
                "preventFallback": "true",
                "__customTag__": "boughtList_all_OrderList",
            },
        )

    def parse_order_list_results(self, response):
        data = response.get("data", {})
        order_data = data.get("data", {})
        orders = []
        for key, val in order_data.items():
            if key.startswith("Main_"):
                fields = val.get("fields", {})
                if isinstance(fields, str):
                    try:
                        fields = json.loads(fields)
                    except (json.JSONDecodeError, TypeError):
                        continue
                order_id = fields.get("orderId", "")
                seller_key = f"sellerInfo_{key[5:]}"
                seller_info = order_data.get(seller_key, {})
                seller_fields = seller_info.get("fields", {})
                if isinstance(seller_fields, str):
                    try:
                        seller_fields = json.loads(seller_fields)
                    except (json.JSONDecodeError, TypeError):
                        seller_fields = {}
                seller_data = seller_fields.get("seller", {})
                status_text = ""
                status_obj = seller_fields.get("status", {})
                if isinstance(status_obj, dict):
                    status_text = status_obj.get("text", "")
                items = []
                for item_key, item_val in order_data.items():
                    if item_key.startswith(f"item_{order_id}"):
                        item_fields = item_val.get("fields", {})
                        if isinstance(item_fields, str):
                            try:
                                item_fields = json.loads(item_fields)
                            except (json.JSONDecodeError, TypeError):
                                continue
                        item_info = item_fields.get("item", {})
                        price_info = item_info.get("priceInfo", {})
                        items.append({
                            "order_id": item_fields.get("basicInfo", {}).get("orderId", ""),
                            "order_line_id": item_fields.get("basicInfo", {}).get("orderLineId", ""),
                            "title": item_info.get("title", ""),
                            "pic": item_info.get("pic", ""),
                            "price": price_info.get("actualTotalFee", ""),
                            "original_price": price_info.get("promotion", ""),
                            "quantity": item_info.get("quantity", 1),
                            "sku": item_info.get("skuText", ""),
                        })
                order = {
                    "order_id": order_id,
                    "item_id": fields.get("itemId", ""),
                    "status_code": fields.get("orderStatus", ""),
                    "status_text": status_text,
                    "seller_id": fields.get("sellerId", ""),
                    "seller_name": seller_data.get("shopName", ""),
                    "seller_shop_url": seller_data.get("url", "") or seller_fields.get("url", ""),
                    "items": items,
                }
                orders.append(order)
        return {
            "total": len(orders),
            "orders": orders,
        }

    def get_order_detail(self, order_id):
        page = 1
        while page <= 5:
            res = self.get_order_list(page_no=page, page_size=20)
            if res.get("ret", [""])[0] != "SUCCESS::调用成功":
                break
            parsed = self.parse_order_list_results(res)
            for order in parsed["orders"]:
                if order["order_id"] == str(order_id):
                    return {"ret": ["SUCCESS::调用成功"], "data": order}
            boughtlist = res.get("data", {}).get("data", {}).get("boughtlist", {})
            has_more = boughtlist.get("fields", {}).get("hasMore", False)
            if isinstance(has_more, str):
                has_more = has_more == "true"
            if not has_more:
                break
            page += 1
        return {"ret": ["FAIL::订单不存在"], "data": {}}

    def get_token(self):
        headers = {
            "accept": "*/*",
            "accept-language": "en,zh-CN;q=0.9,zh;q=0.8,zh-TW;q=0.7,ja;q=0.6",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "referer": "https://market.m.taobao.com/",
            "sec-ch-ua": "\"Chromium\";v=\"146\", \"Not-A.Brand\";v=\"24\", \"Google Chrome\";v=\"146\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "script",
            "sec-fetch-mode": "no-cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        }
        params = {
            "jsv": "2.7.0",
            "appKey": "12574478",
            "t": int(time.time()) * 1000,
            "sign": "43e3268d639f0f8b275569b25d9089e8",
            "api": "mtop.taobao.login.token.get.h5",
            "v": "2.0",
            "preventFallback": "true",
            "type": "jsonp",
            "dataType": "jsonp",
            "callback": "mtopjsonp3",
        }
        data_val = '{"domain":"cntaobao","deviceId":"' + self.device_id + '","locale":"zh_CN","imAppKey":"3ce2dacdc7c0c43ad7bc7f9bc7d7a1b8"}'
        params["data"] = data_val
        token = self.session.cookies['_m_h5_tk'].split('_')[0]
        sign = generate_sign(params['t'], token, data_val)
        params['sign'] = sign
        response = self.session.get(self.login_url, params=params, headers=headers, verify=False)
        for response_cookie_key in response.cookies.get_dict().keys():
            if response_cookie_key in self.session.cookies.get_dict().keys():
                for key in self.session.cookies:
                    if key.name == response_cookie_key and key.domain == '' and key.path == '/':
                        self.session.cookies.clear(domain=key.domain, path=key.path, name=key.name)
                        break
        res_text = response.text
        res_text = re.findall(r' mtopjsonp3\((.*)\)', res_text)[0]
        res_json = json.loads(res_text)
        if 'ret' in res_json and '令牌过期' in res_json['ret'][0]:
            return self.get_token()
        return res_json

    # 类似于 https://detail.tmall.com/item.htm?id=806319949537&mi_id=0000vtiP2t7OiKuXSFJ6Os3CycYK4LfNyLsSkxffiJKUvKY&pvid=e2456346-6c21-490b-8792-abbcafc52e3a&scm=1007.40986.467924.0&skuId=5652727063890&spm=a21bo.jianhua%2Fa.201876.d12.78632a89Xn5WRG&utparam=%7B%22item_ctr%22%3A0.05020460486412048%2C%22x_object_type%22%3A%22item%22%2C%22matchType%22%3A%22nann_base%22%2C%22item_price%22%3A%222.5%22%2C%22item_cvr%22%3A0.043365806341171265%2C%22umpCalled%22%3Atrue%2C%22pc_ctr%22%3A0.009324726648628712%2C%22pc_scene%22%3A%2220001%22%2C%22userId%22%3A3888777108%2C%22ab_info%22%3A%2230986%23467924%230_30986%23528214%2358507_30986%23527806%2358418_30986%23537217%2360408_30986%23521582%2357267_30986%23543870%2358189_30986%23533297%2359487_30986%23528945%2357910_30986%23530923%2359037_30986%23532805%2359017_30986%23528109%2358485_30986%23537488%2360469_30986%23537987%2360586_30986%23538037%2360595%22%2C%22tpp_buckets%22%3A%2230986%23467924%230_30986%23528214%2358507_30986%23527806%2358418_30986%23537217%2360408_30986%23521582%2357267_30986%23543870%2358189_30986%23533297%2359487_30986%23528945%2357910_30986%23530923%2359037_30986%23532805%2359017_30986%23528109%2358485_30986%23537488%2360469_30986%23537987%2360586_30986%23538037%2360595%22%2C%22aplus_abtest%22%3A%2215c0e693256f7b7c9626be50c2718cbe%22%2C%22isLogin%22%3Atrue%2C%22abid%22%3A%22528214_527806_537217_521582_543870_533297_528945_530923_532805_528109_537488_537987_538037%22%2C%22pc_pvid%22%3A%22e2456346-6c21-490b-8792-abbcafc52e3a%22%2C%22isWeekLogin%22%3Afalse%2C%22pc_alg_score%22%3A0.0932632202314%2C%22rn%22%3A11%2C%22item_ecpm%22%3A0%2C%22ump_price%22%3A%222.5%22%2C%22isXClose%22%3Afalse%2C%22x_object_id%22%3A806319949537%7D&xxc=home_recommend
    def get_goods_uid_encrypt_uid(self, goods_url):
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "en",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "priority": "u=0, i",
            "referer": "https://www.taobao.com/",
            "sec-ch-ua": "\"Chromium\";v=\"146\", \"Not-A.Brand\";v=\"24\", \"Google Chrome\";v=\"146\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        }
        response = self.session.get(goods_url, headers=headers, verify=False)
        res_text = response.text
        uid = re.findall(r'"userId":"(.*?)"', res_text)[0]
        encrypt_uid = re.findall(r'data-encryptuid="(.*?)"', res_text)[0]
        return {
            'uid': uid,
            'encrypt_uid': encrypt_uid
        }

    def upload_media(self, media_path):
        headers = {
            "Accept": "*/*",
            "Accept-Language": "en,zh-CN;q=0.9,zh;q=0.8,zh-TW;q=0.7,ja;q=0.6",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Origin": "https://market.m.taobao.com",
            "Pragma": "no-cache",
            "Referer": "https://market.m.taobao.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            "sec-ch-ua": "\"Chromium\";v=\"146\", \"Not-A.Brand\";v=\"24\", \"Google Chrome\";v=\"146\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\""
        }
        params = {
            "appkey": "ampmedia",
            "folderId": "0",
            "_input_charset": "utf-8",
            "useGtrSessionFilter": "false"
        }
        with open(media_path, 'rb') as f:
            media_name = os.path.basename(media_path)
            files = {
                "name": (None, media_name, None),
                "ua": (None, headers['User-Agent'], None),
                "file": (media_name, f, "image/png")
            }
            response = self.session.post(self.upload_media_url, headers=headers, params=params, files=files, verify=False)
            res_json = response.json()
            return res_json

if __name__ == '__main__':
    cookies_str = r'...'
    cookies = trans_cookies(cookies_str)
    taobao = TaobaoApis(cookies, generate_device_id(cookies['unb']))

    # 商品搜索（MTOP 接口，需 TSDK 完整初始化流以绕过风控）
    # res = taobao.search_products("手机", page_no=1, page_size=10)

    # 获取购物车列表 ✓ 已验证通过
    # res = taobao.get_cart_list()

    # 加购物车（MTOP 接口，需验证）
    # res = taobao.add_to_cart("12345678901", sku_id="1234567890123")

    # 订单列表（MTOP 接口，需验证）
    # res = taobao.get_order_list(page_no=1, page_size=10)

    # 订单详情（MTOP 接口，需验证）
    # res = taobao.get_order_detail("1234567890123456")

    # 获取 Token
    # res = taobao.get_token()

    # 商品详情（页面解析）
    # res = taobao.get_goods_uid_encrypt_uid("https://detail.tmall.com/item.htm?id=xxxxx")

    # 上传媒体
    # res = taobao.upload_media(r"D:\Desktop\1.png")

    # print(json.dumps(res, indent=4, ensure_ascii=False))