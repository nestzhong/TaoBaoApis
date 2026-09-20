from builder.auth import default_auth_path
from taobao_apis import TaobaoApis
from taobao_login import TaobaoLogin


def main():
    auth = TaobaoLogin.auto()

    if not auth.is_login:
        print("\n未获取到登录态，可设置环境变量后重试：")
        print(f"  export TB_COOKIES='cookie1=xxx; cookie2=yyy; ...'")
        return

    print(f"登录成功: unb={auth.unb}, _nk_={auth.nk}")
    print(f"Cookie 已持久化到: {auth._storage_path}")
    print(f"Cookie 数量: {len(auth.cookie)}, 包含 _m_h5_tk={bool(auth.sign_token)}")

    taobao = TaobaoApis(auth=auth)
    res = taobao.get_cart_list()
    if res.get("ret", [""])[0] == "SUCCESS::调用成功":
        print(f"API 测试通过: 获取购物车成功")
    else:
        print(f"API 测试结果: {res.get('ret', ['unknown'])[0]}")


if __name__ == "__main__":
    main()