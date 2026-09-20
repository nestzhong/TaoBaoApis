import base64
import json
import asyncio
import threading
import time
from pprint import pprint

from loguru import logger
import websockets
from taobao_apis import TaobaoApis

from utils.taobao_utils import generate_mid, generate_uuid, trans_cookies, generate_device_id, decrypt, \
    get_session_cookies_str
from message import Message, make_text, make_image


class taobaoLive:
    def __init__(self, cookies_str):
        self.base_url = 'wss://wss-cntaobao.dingtalk.com/'
        self.cookies_str = cookies_str
        self.cookies = trans_cookies(cookies_str)
        self.myid = self.cookies['unb']
        self.nk = self.cookies['_nk_']
        self.device_id = generate_device_id(self.myid)
        self.taobao = TaobaoApis(self.cookies, self.device_id)
        self.ws = None

    async def list_all_conversations(self, cid):
        headers = {
            "Cookie": get_session_cookies_str(self.taobao.session),
            "Host": "wss-cntaobao.dingtalk.com",
            "Connection": "Upgrade",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Origin": "https://www.cntaobao.com",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        async with websockets.connect(self.base_url, extra_headers=headers) as websocket:
            asyncio.create_task(self.init(websocket))
            send_mid = generate_mid()
            msg = {
                "lwp": "/r/MessageManager/listUserMessages",
                "headers": {
                    "mid": send_mid
                },
                "body": [
                    f"{cid}@cntaobao",
                    False,
                    9007199254740991,
                    20,
                    False
                ]
            }
            user_message_models = []
            async for message in websocket:
                print(message)
                try:
                    message = json.loads(message)
                    ack = {
                        "code": 200,
                        "headers": {
                            "mid": message["headers"]["mid"] if "mid" in message["headers"] else generate_mid(),
                            "sid": message["headers"]["sid"] if "sid" in message["headers"] else '',
                        }
                    }
                    if 'app-key' in message["headers"]:
                        ack["headers"]["app-key"] = message["headers"]["app-key"]
                    if 'ua' in message["headers"]:
                        ack["headers"]["ua"] = message["headers"]["ua"]
                    if 'dt' in message["headers"]:
                        ack["headers"]["dt"] = message["headers"]["dt"]
                    await websocket.send(json.dumps(ack))
                except Exception as e:
                    pass
                try:
                    if 'lwp' in message and message['lwp'] == "/s/vulcan":
                        await websocket.send(json.dumps(msg))
                    recv_mid = message["headers"]["mid"] if "mid" in message["headers"] else ''
                    if recv_mid == send_mid:
                        logger.info(f"user history message: {message}")
                        has_more = message["body"]["hasMore"] == 1
                        next_cursor = message["body"]["nextCursor"]
                        for user_message in message["body"]["userMessageModels"]:
                            send_user_name = user_message["message"]["extension"]["sender_nick"]
                            send_user_id = user_message["message"]["sender"]["uid"]
                            send_message = None
                            if user_message["message"]["content"]["contentType"] == 1:
                                send_message = user_message["message"]["content"]
                            elif user_message["message"]["content"]["contentType"] == 101:
                                send_message = user_message["message"]["content"]["custom"]["data"]
                                send_message = base64.b64decode(send_message)
                            user_message_models.insert(0, {
                                "send_user_id": send_user_id,
                                "send_user_name": send_user_name,
                                "message": send_message
                            })
                        if has_more:
                            logger.info(f"has more history messages, next cursor: {next_cursor}")
                            send_mid = generate_mid()
                            msg["headers"]["mid"] = send_mid
                            msg["body"][2] = next_cursor
                            await websocket.send(json.dumps(msg))
                        else:
                            return user_message_models
                except Exception as e:
                    return user_message_models

    async def create_chat(self, ws, encrypt_uid):
        msg = {
            "lwp": "/r/SingleChatConversation/create",
            "headers": {
                "mid": generate_mid()
            },
            "body": [
                {
                    "pairFirst": f"{self.myid}@cntaobao",
                    "bizType": "11001",
                    "ctx": {
                        "createConversationCtx": '{"encryptUid":"' + encrypt_uid + '"}',
                        "selfBizDomain": "taobao"
                    }
                }
            ]
        }
        print(json.dumps(msg, indent=4, ensure_ascii=False))
        await ws.send(json.dumps(msg))

    async def send_msg(self, ws, cid, toid, sender_nick, message: Message):
        msg_type = message["type"]
        msg = {
            "lwp": "/r/MessageSend/sendByReceiverScope",
            "headers": {
                "mid": generate_mid()
            },
            "body": [
                {
                    "cid": cid,
                    "uuid": generate_uuid(),
                    "conversationType": 1,
                    "redPointPolicy": 0,
                    "extension": {
                        "senderBizDomain": "taobao",
                        "receiverBizDomain": "taobao",
                        "sender_nick": sender_nick
                    },
                    "content": {
                        "contentType": None,
                    },
                    "ctx": {
                        "senderBizDomain": "taobao",
                        "receiverBizDomain": "taobao"
                    }
                },
                {
                    "actualReceivers": [
                        f"{self.myid}@cntaobao",
                        f"{toid}@cntaobao",
                    ]
                }
            ]
        }
        if msg_type == "text":
            msg["body"][0]["content"]["contentType"] = 1
            msg["body"][0]["content"]["text"] = {
                "extension": {
                    "sender_nick": sender_nick
                },
                "content": message["text"]
            }
        elif msg_type == "image":
            del msg["body"][0]["extension"]["sender_nick"]
            data = {
                "fileId": message["file_id"],
                "size": message["size"],
                "url": message["image_url"],
                "width": message["width"],
                "height": message["height"],
                "isOriginal": 1,
                "suffix": "png"
            }
            msg["body"][0]["content"]["contentType"] = 101
            image_base64 = str(base64.b64encode(json.dumps(data).encode('utf-8')), 'utf-8')
            msg["body"][0]["content"]["custom"] = {}
            msg["body"][0]["content"]["custom"]["type"] = 7
            msg["body"][0]["content"]["custom"]["data"] = image_base64
        elif msg_type == "audio":
            # TODO: handle audio message
            logger.error(f"不支持的消息类型: {msg_type}")
            return
        else:
            logger.error(f"不支持的消息类型: {msg_type}")
            return
        print(json.dumps(msg, indent=4, ensure_ascii=False))
        await ws.send(json.dumps(msg))

    async def init(self, ws):
        data = self.taobao.get_token()
        token = data['data']['result']['accessToken'] if 'data' in data and 'result' in data['data'] and 'accessToken' in data['data']['result'] else ''
        if not token:
            logger.error('获取token失败')
            exit(0)
        msg = {
            "lwp": "/reg",
            "headers": {
                "cache-header": "app-key token ua wv",
                "app-key": "3ce2dacdc7c0c43ad7bc7f9bc7d7a1b8",
                "token": token,
                "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 DingTalk(2.1.5) OS(Windows/10) Browser(Chrome/146.0.0.0) DingWeb/2.1.5 IMPaaS DingWeb/2.1.5",
                "dt": "j",
                "wv": "im:3,au:3,sy:6",
                "sync": "0,0;0;0;",
                "did": self.device_id,
                "mid": generate_mid()
            }
        }
        await ws.send(json.dumps(msg))
        current_time = int(time.time() * 1000)
        msg = {
            "lwp": "/r/SyncStatus/ackDiff",
            "headers": {"mid": generate_mid()},
            "body": [
                {
                    "pipeline": "sync",
                    "tooLong2Tag": "PNM,1",
                    "channel": "sync",
                    "topic": "sync",
                    "highPts": 0,
                    "pts": current_time * 1000,
                    "seq": 0,
                    "timestamp": current_time
                }
            ]
        }
        await ws.send(json.dumps(msg))
        logger.info('init')


    async def heart_beat(self, ws):
        while True:
            msg = {
                "lwp": "/!",
                "headers": {
                    "mid": generate_mid()
                 }
            }
            await ws.send(json.dumps(msg))
            await asyncio.sleep(15)

    def user_alive(self):
        while True:
            time.sleep(600)
            # self.taobao.refresh_token()

    async def main(self):
        headers = {
            "Cookie": get_session_cookies_str(self.taobao.session),
            "Host": "wss-cntaobao.dingtalk.com",
            "Connection": "Upgrade",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Origin": "https://www.cntaobao.com",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        threading.Thread(target=self.user_alive).start()
        async with websockets.connect(self.base_url, extra_headers=headers) as websocket:
            asyncio.create_task(self.init(websocket))
            asyncio.create_task(self.heart_beat(websocket))
            async for message in websocket:
                # logger.info(f"message: {message}")
                message = json.loads(message)
                ack = {
                    "code": 200,
                    "headers": {
                        "mid": message["headers"]["mid"] if "mid" in message["headers"] else generate_mid(),
                        "sid": message["headers"]["sid"] if "sid" in message["headers"] else '',
                    }
                }
                if 'app-key' in message["headers"]:
                    ack["headers"]["app-key"] = message["headers"]["app-key"]
                if 'ua' in message["headers"]:
                    ack["headers"]["ua"] = message["headers"]["ua"]
                if 'dt' in message["headers"]:
                    ack["headers"]["dt"] = message["headers"]["dt"]
                await websocket.send(json.dumps(ack))

                await self.handle_message(message, websocket)

    async def handle_message(self, message, websocket):
        try:
            data = message["body"]["syncPushPackage"]["data"][0]["data"]
            data = json.loads(data)
            logger.info(f"无需解密 message: {data}")
        except Exception as e:
            try:
                data = decrypt(data)
                message = json.loads(data)

                send_user_name = message["1"]["10"]["sender_nick"]
                send_user_id = message["1"]["1"]["1"].split('@')[0]
                send_message = message["1"]["6"]["2"]["1"]

                if send_user_name == f"cntaobao{self.nk}":
                    logger.info(f"这是自己发的消息，忽略 message: {message}")
                    return

                logger.info(f"user: {send_user_name}, 发送给我的信息 message: {send_message}")

                cid = message["1"]["2"]

                # 回复文字
                # reply = f'Hello, {send_user_name}! I am a robot. I am not available now. I will reply to you later.'
                reply = f'{send_user_name} 说了: {send_message}'
                await self.send_msg(websocket, cid, send_user_id, f"cntaobao{self.nk}",  make_text(reply))

                # 回复图片
                # res_json = self.taobao.upload_media(r"D:\Desktop\1.png")
                # image_object = res_json["object"]
                # width, height = map(int, image_object["pix"].split('x'))
                # await self.send_msg(websocket, cid, send_user_id, f"cntaobao{self.nk}", make_image(image_object["fileId"], image_object["url"], image_object["size"], width, height))
            except Exception as e:
                pass


if __name__ == '__main__':
    cookies_str = r'cookie2=12ccac29b433788e7d48d8f3ddc0a394; cna=UT7TIrr7qU0CATpk5PPqsndz; _hvn_lgc_=0; havana_lgc2_0=eyJoaWQiOjkwMjcyOTg1LCJzZyI6ImNiZGJkODY2MjFlOTFjY2Q5MzliYjNkNzQ5MmQxZGQzIiwic2l0ZSI6MCwidG9rZW4iOiIxbjREWFNTbS10dEs5OVRFV3lJWndUZyJ9; lgc=zlf19911123; cancelledSubSites=empty; dnk=zlf19911123; tracknick=zlf19911123; _cc_=V32FPkk%2Fhw%3D%3D; unb=90272985; uc1=cookie16=VFC%2FuZ9az08KUQ56dCrZDlbNdA%3D%3D&existShop=false&cookie15=U%2BGCWk%2F75gdr5Q%3D%3D&cookie14=UoYWNLkX3DiOVA%3D%3D&pas=0&cookie21=Vq8l%2BKCLjhS4UhJVbhgU; uc3=lg2=URm48syIIVrSKA%3D%3D&vt3=F8dD1fb8ieFmwEEQkTM%3D&id2=WvA21eIU1QY%3D&nk2=GcTgxsMvxSD3gzc%3D; csg=7cfd5d56; cookie17=WvA21eIU1QY%3D; skt=46858c16327ce6c4; existShop=MTc4OTM0ODA2Mg%3D%3D; uc4=id4=0%40WDf%2Bpy1gYKZhH78%2BeIlJ4GJXIg%3D%3D&nk4=0%40Gw33nLMkGH3YwL0a3gj43ig9wzL%2Fsw%3D%3D; _l_g_=Ug%3D%3D; sg=359; _nk_=zlf19911123; cookie1=VW9KHevtuAcpaxwG3s%2F1e3L6Or83NoJpB1W4C6HYcpI%3D; sgcookie=E100rJnPQtXoHEMC5EbcGAR9ExD7BTxk5cqtTDhEWtkHVqc8w3BdiSJIlnR0%2FHsSjii1vRHT%2BZquf3rRdSZ3ur4M70iVOzXAxWewjwFOOHcZ6KIgjm9Oe2ZpDNnfobIIiId%2F; _tb_token_=f4b3ebe6913e1; mt_partitioned_detect=1; _m_h5_tk=82f651b1494a80b0e00ca8f28cba2c73_1789880458418; _m_h5_tk_enc=25c65c6fbdc0eeaecd3295597970b8d9; _samesite_flag_=true; havana_lgc_exp=1820974379364; sdkSilent=1789899179364; havana_sdkSilent=1789899179364; _3dtid=GVjKIbjf%2BJkBjZnTnwu9vF%2BGem%2BvQOpnuL9X%2FJWwtettSvE1JbZ9Icx%2FaIj89N1z; isg=BK-vcq6RGYnJHBDAzQOMWkwGPsW5VAN2ULLCC8E8S54lEM8SySSTxq3SkAAuc9vu; sca=87c60165; is-expand-skupanel-skudecision=false; sn=; login=true'
    taobaoLive = taobaoLive(cookies_str)

    # 2 获取全部聊天记录
    # cid = '3888777108.1-2221755722770.1#11001'
    # all_messages = asyncio.run(taobaoLive.list_all_conversations(cid))
    # for message in all_messages:
    #     print(message)

    # 3 常驻进程 用于接收消息和自动回复
    asyncio.run(taobaoLive.main())
