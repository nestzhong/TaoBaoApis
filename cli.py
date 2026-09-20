#!/usr/bin/env python3
"""淘宝命令行工具。

用法:
  python3 cli.py login                              # 登录/重新登录
  python3 cli.py info                               # 查看当前登录信息
  python3 cli.py search <关键词> [--page N] [--sort]  # 搜索商品
  python3 cli.py detail <商品链接>                    # 商品详情（页面解析）
  python3 cli.py orders [--page N] [--status S]      # 历史订单
  python3 cli.py order <订单号>                       # 订单详情
  python3 cli.py cart list                           # 查看购物车
  python3 cli.py cart add <item_id> [--sku SKU_ID] [--qty N]  # 加购物车

输出格式（放在子命令后）:
  --json    JSON 格式输出
  --raw     输出原始 API 响应
"""

import argparse
import json
import re
import sys
import textwrap
import warnings

warnings.filterwarnings("ignore", category=Warning)


def green(s): return f"\033[92m{s}\033[0m"
def yellow(s): return f"\033[93m{s}\033[0m"
def cyan(s): return f"\033[96m{s}\033[0m"
def bold(s): return f"\033[1m{s}\033[0m"
def dim(s): return f"\033[2m{s}\033[0m"


def strip_currency(s):
    return re.sub(r'^[\¥\￥]', '', str(s))


def get_api():
    from taobao_apis import TaobaoApis
    from taobao_login import TaobaoLogin

    auth = TaobaoLogin.auto()
    if not auth.is_login:
        print(yellow("未登录"), file=sys.stderr)
        sys.exit(1)
    return TaobaoApis(auth=auth)


def add_json_raw(subparser):
    subparser.add_argument("--json", action="store_true", help="JSON 格式输出")
    subparser.add_argument("--raw", action="store_true", help="输出原始 API 响应")


def cmd_login(args):
    from taobao_login import TaobaoLogin
    auth = TaobaoLogin.qr_login()
    if auth.is_login:
        print(green(f"登录成功: unb={auth.unb}, nk={auth.nk}"))
    else:
        print(yellow("登录失败"))
        sys.exit(1)


def cmd_info(args):
    from builder.auth import TaobaoAuth
    auth = TaobaoAuth.load()
    print(f"{bold('用户信息')}:")
    print(f"  unb       {cyan(str(auth.unb))}")
    print(f"  _nk_      {cyan(str(auth.nk))}")
    print(f"  已登录    {green('是') if auth.is_login else yellow('否')}")
    print(f"  cookie数  {len(auth.cookie)}")
    print(f"  device_id {dim(auth.device_id or '')}")
    if auth.is_login:
        keys = list(auth.cookie.keys())
        print(f"  cookie列表 {', '.join(keys[:10])}{'...' if len(keys) > 10 else ''}")
    print(f"  持久化路径 {dim(str(auth._storage_path))}")


def cmd_search(args):
    api = get_api()
    res = api.search_products(args.keyword, page_no=args.page, page_size=20, sort=args.sort)

    if args.raw:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    parsed = api.parse_search_results(res)

    if args.json:
        print(json.dumps(parsed, ensure_ascii=False, indent=2, default=str))
        return

    total = parsed["total_results"]
    print(f"{bold('搜索结果')} {dim(f'共 {total} 条，第 {args.page} 页')}")
    print()

    for i, item in enumerate(parsed["items"], 1):
        raw_price = strip_currency(item["price"] or "?")
        unit = item["price_unit"] or "¥"
        shop = item["shop_name"] or "?"
        title = textwrap.shorten(item["title"] or "", width=70, placeholder="...")
        print(f"  {i:2d}. {green(f'{unit}{raw_price}')}  {dim(shop)}")
        print(f"      {title}")
        item_id = item.get("item_id", "")
        print(f"      {dim(f'item_id={item_id}')}")
        print()


def cmd_detail(args):
    api = get_api()
    import requests
    from urllib.parse import urlparse

    raw_url = args.url
    parsed_url = urlparse(raw_url)
    domain = parsed_url.netloc

    session = api.session
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-language": "en",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "referer": "https://www.taobao.com/",
    }
    resp = session.get(raw_url, headers=headers, verify=False, allow_redirects=True)
    api.auth.absorb_response(resp, session=session)
    text = resp.text

    uid = re.findall(r'"userId":"(.*?)"', text)
    encrypt_uid = re.findall(r'data-encryptuid="(.*?)"', text)
    title = re.findall(r'<title>(.*?)</title>', text)

    result = {
        "uid": uid[0] if uid else "",
        "encrypt_uid": encrypt_uid[0] if encrypt_uid else "",
        "title": title[0] if title else "",
    }

    if args.raw:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return

    print(f"{bold('商品详情')}")
    if result["title"]:
        print(f"  标题       {result['title']}")
    print(f"  uid        {cyan(result['uid'] or '未找到')}")
    print(f"  encrypt_uid {cyan(result['encrypt_uid'] or '未找到')}")


def cmd_orders(args):
    api = get_api()
    res = api.get_order_list(page_no=args.page, page_size=10, status=args.status)

    if args.raw:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    parsed = api.parse_order_list_results(res)

    if args.json:
        print(json.dumps(parsed, ensure_ascii=False, indent=2, default=str))
        return

    total = parsed["total"]
    print(f"{bold('订单列表')} {dim(f'共 {total} 条，第 {args.page} 页')}")
    print()

    for i, order in enumerate(parsed["orders"], 1):
        item_count = len(order.get("items", []))
        oid = order.get("order_id", "?")
        status_txt = order.get("status_text", "?")
        seller = order.get("seller_name", "?")
        print(f"  {i:2d}. {green(oid)}  {dim(status_txt)}")
        print(f"      卖家: {seller}")
        print(f"      商品数: {item_count}")
        for item in order.get("items", [])[:3]:
            title = textwrap.shorten(item.get("title", ""), width=60, placeholder="...")
            qty = item.get("quantity", 1)
            price = strip_currency(item.get("price", "?"))
            print(f"        - {title} {dim(f'x{qty}')} {green(f'¥{price}')}")
        print()

    if args.json:
        print(json.dumps(parsed, ensure_ascii=False, indent=2))


def cmd_order(args):
    api = get_api()
    res = api.get_order_detail(args.order_id)

    if args.raw:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    order = res.get("data", {})
    if not order:
        print(yellow("订单不存在"))
        sys.exit(1)

    print(f"{bold('订单详情')} {green(order['order_id'])}")
    print(f"  状态: {order.get('status_text', '?')}")
    print(f"  卖家: {order.get('seller_name', '?')}")
    print()
    for i, item in enumerate(order.get("items", []), 1):
        title = textwrap.shorten(item.get("title", ""), width=60, placeholder="...")
        sku = f" [{item.get('sku', '')}]" if item.get("sku") else ""
        qty = item.get("quantity", 1)
        price = strip_currency(item.get("price", "?"))
        print(f"  {i}. {title}{sku}")
        print(f"     数量 {qty}  ×  {green(f'¥{price}')}")
        print()

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))


def cmd_cart(args):
    api = get_api()

    if args.cart_action == "list":
        res = api.get_cart_list()
        if args.raw:
            print(json.dumps(res, ensure_ascii=False, indent=2))
            return
        if res.get("ret", [""])[0] != "SUCCESS::调用成功":
            print(yellow(f"获取购物车失败: {res.get('ret', ['?'])[0]}"))
            sys.exit(1)
        print(f"{bold('购物车')} {dim('(原始数据，结构复杂)')}")
        print(json.dumps(res, ensure_ascii=False, indent=2))

    elif args.cart_action == "add":
        try:
            res = api.add_to_cart(args.item_id, sku_id=args.sku, quantity=args.qty)
        except NotImplementedError as e:
            print(yellow(str(e)), file=sys.stderr)
            sys.exit(1)
        if args.raw:
            print(json.dumps(res, ensure_ascii=False, indent=2))
            return
        if res.get("ret", [""])[0] == "SUCCESS::调用成功":
            print(green(f"加购成功: {args.item_id}"))
        else:
            print(yellow(f"加购失败: {res.get('ret', ['?'])[0]}"))
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="淘宝命令行工具")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("login", help="登录/重新登录")

    sub.add_parser("info", help="查看当前登录信息")

    p = sub.add_parser("search", help="搜索商品")
    p.add_argument("keyword", help="搜索关键词")
    p.add_argument("--page", type=int, default=1, help="页码")
    p.add_argument("--sort", help="排序方式（如 _coefp）")
    add_json_raw(p)

    p = sub.add_parser("detail", help="商品详情")
    p.add_argument("url", help="商品链接")
    add_json_raw(p)

    p = sub.add_parser("orders", help="历史订单")
    p.add_argument("--page", type=int, default=1, help="页码")
    p.add_argument("--status", help="订单状态")
    add_json_raw(p)

    p = sub.add_parser("order", help="订单详情")
    p.add_argument("order_id", help="订单号")
    add_json_raw(p)

    p = sub.add_parser("cart", help="购物车操作")
    p.add_argument("cart_action", choices=["list", "add"], help="list:查看 add:加购")
    p.add_argument("item_id", nargs="?", help="商品 ID（add 时必需）")
    p.add_argument("--sku", help="SKU ID")
    p.add_argument("--qty", type=int, default=1, help="数量")
    add_json_raw(p)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "login": cmd_login,
        "info": cmd_info,
        "search": cmd_search,
        "detail": cmd_detail,
        "orders": cmd_orders,
        "order": cmd_order,
        "cart": cmd_cart,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()