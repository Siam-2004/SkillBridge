import time
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions

class BaseSprint3SeleniumTestCase(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            o = ChromeOptions()
            for arg in ['--headless', '--disable-gpu', '--no-sandbox', '--window-size=1920,1080']: o.add_argument(arg)
            cls.driver = webdriver.Chrome(options=o)
        except Exception:
            o = EdgeOptions()
            for arg in ['--headless', '--disable-gpu', '--no-sandbox', '--window-size=1920,1080']: o.add_argument(arg)
            cls.driver = webdriver.Edge(options=o)
        cls.driver.implicitly_wait(6)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, 'driver', None): cls.driver.quit()
        super().tearDownClass()

    def login_user(self, identifier, password):
        self.driver.get(f'{self.live_server_url}/')
        self.driver.delete_all_cookies()
        self.driver.get(f'{self.live_server_url}/accounts/login/')
        time.sleep(0.5)
        self.driver.find_element(By.NAME, 'identifier').send_keys(identifier)
        self.driver.find_element(By.NAME, 'password').send_keys(password)
        self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        time.sleep(1)
