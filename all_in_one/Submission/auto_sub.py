import os
import time
import random
import pickle
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ================= 配置区域 =================
USERNAME = "mahdi.mostajabdaveh1@huawei.com"  # 替换为你的账号
PASSWORD = "Huawei2026"  # 替换为你的密码

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 建议使用 os.path.join 处理路径，兼容性更好
FILE_DIR = os.path.join(BASE_DIR, "to_sub_sols")
print(f"文件目录: {FILE_DIR}")

COOKIE_FILE = "cvrplib_cookies.pkl"
FILE_EXT = ".sol"  # 或者是 .txt, 根据比赛要求过滤文件后缀

# 网址配置
LOGIN_URL = "https://galgos.inf.puc-rio.br/cvrplib/index.php/en/login"
SUBMIT_URL = "https://galgos.inf.puc-rio.br/cvrplib/index.php/en/user/submission/new"

# 并发与延迟配置
HEADLESS = False  # 设置为 True 则不显示浏览器界面（后台运行）
MIN_DELAY = 2  # 操作间最小等待秒数
MAX_DELAY = 5  # 操作间最大等待秒数


# ===========================================

class CvrpSubmitter:
    def __init__(self):
        # 1. 设置 Chrome 选项
        options = webdriver.ChromeOptions()
        if HEADLESS:
            options.add_argument('--headless')
        # 保持浏览器打开
        options.add_experimental_option("detach", True)

        # 2. 初始化 Driver (修复了这里的错误)
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        self.wait = WebDriverWait(self.driver, 20)

    def handle_cookie_banner(self):
        """专门处理截图中的 Cookie 横幅"""
        try:
            # 查找绿色的 Accept 按钮
            accept_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Accept')]")
            if accept_btn.is_displayed():
                print("Detected cookie banner, clicking Accept...")
                accept_btn.click()
                time.sleep(1)  # 等一下让遮罩消失
        except:
            # 如果没找到按钮，说明没有弹窗，忽略即可
            pass

    def save_cookies(self):
        """登录成功后，把饼干保存到本地文件"""
        try:
            cookies = self.driver.get_cookies()
            with open(COOKIE_FILE, "wb") as f:
                pickle.dump(cookies, f)
            print(f"√ Cookies 已保存到 {COOKIE_FILE}，下次无需登录")
        except Exception as e:
            print(f"× 保存 Cookies 失败: {e}")

    def load_cookies(self):
        """尝试从本地加载 Cookie"""
        if not os.path.exists(COOKIE_FILE):
            return False

        try:
            # 关键点：Selenium 添加 Cookie 前必须先访问一次该域名
            self.driver.get("https://galgos.inf.puc-rio.br/cvrplib/")

            with open(COOKIE_FILE, "rb") as f:
                cookies = pickle.load(f)
                for cookie in cookies:
                    self.driver.add_cookie(cookie)

            print(">>> 已加载本地 Cookies，尝试刷新...")
            self.driver.refresh()
            time.sleep(2)  # 刷新后稍微等一下

            # 检查是否真的登录成功了
            if "login" not in self.driver.current_url:
                print("√ Cookie 有效，自动登录成功！")
                return True
            else:
                print("! Cookie 可能已过期，需要重新登录")
                return False

        except Exception as e:
            print(f"加载 Cookies 出错: {e}")
            return False

    def login(self):
        """智能登录逻辑"""
        # 1. 先尝试用 Cookie 登录
        if self.load_cookies():
            return

        # 2. 如果 Cookie 无效，走常规账号密码流程
        print(">>> 开始账号密码登录...")
        self.driver.get(LOGIN_URL)

        # !! 这里处理你截图中的横幅 !!
        self.handle_cookie_banner()

        try:
            user_input = self.wait.until(EC.presence_of_element_located((By.NAME, "username")))
            pass_input = self.driver.find_element(By.NAME, "password")

            user_input.clear()
            user_input.send_keys(USERNAME)
            pass_input.clear()
            pass_input.send_keys(PASSWORD)

            # 再次检查是否有横幅遮挡了登录按钮
            self.handle_cookie_banner()

            login_btn = self.driver.find_element(By.XPATH, "//button[@type='submit'] | //input[@type='submit']")
            login_btn.click()

            # 等待登录完成
            self.wait.until(lambda d: "login" not in d.current_url)
            print(">>> 登录动作完成")

            # 3. 登录成功后，保存 Cookie 供下次使用
            self.save_cookies()

        except Exception as e:
            print(f"!!! 登录失败: {e}")
            self.driver.quit()
            exit()

    def random_sleep(self):
        """为了安全和加载，随机睡眠一段时间"""
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    def upload_single_file(self, file_path):
        """上传单个文件的逻辑"""
        file_name = os.path.basename(file_path)
        print(f"--- 正在处理: {file_name} ---")

        try:
            # 1. 进入上传页面
            self.driver.get(SUBMIT_URL)

            # 2. 定位上传框
            file_input = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']")))

            # 3.1 直接发送路径
            file_input.send_keys(file_path)

            # 3.2 点击 Create 按钮
            create_btn = self.driver.find_element(By.XPATH,
                                                  "//button[contains(text(), 'Create')] | //input[@value='Create']")
            create_btn.click()

            # 3.3 等待跳转
            self.wait.until(EC.url_changes(SUBMIT_URL))

            print(f"√ 成功上传: {file_name}")
            self.random_sleep()
            return True

        except Exception as e:
            print(f"× 上传失败 [{file_name}]: {str(e)[:100]}")
            return False

    def process_files(self, file_list):
        """批量处理文件列表"""
        failed_files = []
        for file_path in file_list:
            success = self.upload_single_file(file_path)
            if not success:
                failed_files.append(file_path)
        return failed_files

    def close(self):
        self.driver.quit()


def main():
    if not os.path.exists(FILE_DIR):
        print(f"错误: 文件夹不存在 -> {FILE_DIR}")
        return

    # 1. 获取所有文件
    all_files = [
        os.path.join(FILE_DIR, f)
        for f in os.listdir(FILE_DIR)
        if f.endswith(FILE_EXT)
    ]

    if not all_files:
        print(f"未在 {FILE_DIR} 找到后缀为 {FILE_EXT} 的文件。")
        return

    print(f"共发现 {len(all_files)} 个文件待上传。")

    bot = CvrpSubmitter()
    bot.login()

    # 2. 第一轮上传
    print("\n=== 开始第一轮上传 ===")
    failed_list = bot.process_files(all_files)

    # 3. 失败重试逻辑
    if failed_list:
        print(f"\n=== 第一轮结束，{len(failed_list)} 个文件失败，开始重试 ===")
        print("等待 10 秒冷却...")
        time.sleep(10)

        # 再次尝试失败的列表
        final_failed = bot.process_files(failed_list)

        if final_failed:
            print("\n" + "=" * 30)
            print("!!! 以下文件最终上传失败，请手动处理 !!!")
            for f in final_failed:
                print(f)
            print("=" * 30)
        else:
            print("\n所有文件重试后上传成功！")
    else:
        print("\n所有文件一次性上传成功！")

    bot.close()


if __name__ == "__main__":
    main()