import pickle
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ================= 配置 =================
COOKIE_FILE = "cvrplib_cookies.pkl"
LOGIN_URL = "https://galgos.inf.puc-rio.br/cvrplib/index.php/en/login"


# =======================================

def manual_login_and_save():
    print(">>> 正在启动浏览器...")

    # 保持浏览器打开，直到手动关闭
    options = webdriver.ChromeOptions()
    options.add_experimental_option("detach", True)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    try:
        driver.get(LOGIN_URL)
        print("\n" + "=" * 50)
        print("【人工介入模式】")
        print("1. 浏览器已打开，请现在去浏览器里手动操作：")
        print("   - 点击那个烦人的 Accept")
        print("   - 输入账号密码")
        print("   - 点击登录")
        print("2. 确保页面跳转到了登录后的状态（比如能看到 Log out 按钮）")
        print("=" * 50)

        # 关键步骤：在这里暂停，等待你输入回车
        input(">>> 确认已登录成功后，请在这里按【回车键】保存 Cookie...")

        # 获取并保存 Cookie
        cookies = driver.get_cookies()
        with open(COOKIE_FILE, "wb") as f:
            pickle.dump(cookies, f)

        print(f"\n√ 成功！Cookies 已保存到当前目录下的 {COOKIE_FILE}")
        print("现在你可以运行主程序 auto_sub.py 了，它会自动读取这个文件。")

    except Exception as e:
        print(f"\n× 出错啦: {e}")
    finally:
        print("正在关闭浏览器...")
        driver.quit()


if __name__ == "__main__":
    manual_login_and_save()