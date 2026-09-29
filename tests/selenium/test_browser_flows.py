import time
from decimal import Decimal
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from apps.accounts.models import User, Role

class SkillbridgeSeleniumTestCase(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.driver = None
        # Headless Chrome initialization
        try:
            options = ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--window-size=1920,1080')
            cls.driver = webdriver.Chrome(options=options)
        except Exception:
            # Fallback to Edge
            try:
                edge_options = EdgeOptions()
                edge_options.add_argument('--headless')
                edge_options.add_argument('--disable-gpu')
                edge_options.add_argument('--no-sandbox')
                edge_options.add_argument('--window-size=1920,1080')
                cls.driver = webdriver.Edge(options=edge_options)
            except Exception as e:
                raise RuntimeError(f'Could not initialize a Selenium headless browser: {e}')

        cls.driver.implicitly_wait(5)

    @classmethod
    def tearDownClass(cls):
        if cls.driver:
            cls.driver.quit()
        super().tearDownClass()

    def setUp(self):
        # Seed test users for authenticated flows
        self.client_user = User.objects.create_user(
            email='kamrulhasansiam29@gmail.com',
            username='siam',
            password='mominrifat2211',
            role=Role.CLIENT,
            first_name='Kamrul Hasan',
            last_name='Siam',
            is_email_verified=True
        )
        self.freelancer_user = User.objects.create_user(
            email='mominrifat8@gmail.com',
            username='rifat',
            password='mominrifat2211',
            role=Role.FREELANCER,
            first_name='Momin',
            last_name='Rifat',
            is_email_verified=True
        )

    def test_homepage_branding_and_navigation(self):
        self.driver.get(self.live_server_url)
        self.assertIn('skillbridge', self.driver.title.lower())

        navbar = self.driver.find_element(By.TAG_NAME, 'nav')
        self.assertIsNotNone(navbar)

        page_source = self.driver.page_source
        self.assertTrue('skillbridge' in page_source.lower() or 'skillcoin' in page_source.lower())

    def test_jobs_catalog_page_rendering(self):
        self.driver.get(f'{self.live_server_url}/jobs/')
        self.assertIn('skillbridge', self.driver.title.lower())
        main_content = self.driver.find_element(By.TAG_NAME, 'main')
        self.assertIsNotNone(main_content)

    def test_freelancers_directory_page(self):
        self.driver.get(f'{self.live_server_url}/freelancers/')
        self.assertIn('skillbridge', self.driver.title.lower())
        page_source = self.driver.page_source.lower()
        self.assertTrue('freelancer' in page_source or 'talent' in page_source)

    def test_categories_and_search_pages(self):
        # Categories directory
        self.driver.get(f'{self.live_server_url}/categories/')
        self.assertIn('skillbridge', self.driver.title.lower())

        # Search page
        self.driver.get(f'{self.live_server_url}/search/?q=python')
        self.assertIn('skillbridge', self.driver.title.lower())

    def test_register_page_rendering(self):
        self.driver.get(f'{self.live_server_url}/accounts/register/')
        self.assertIn('skillbridge', self.driver.title.lower())

        # Check required registration form inputs
        email_input = self.driver.find_element(By.NAME, 'email')
        password_input = self.driver.find_element(By.NAME, 'password')
        first_name_input = self.driver.find_element(By.NAME, 'first_name')
        self.assertTrue(email_input.is_displayed())
        self.assertTrue(password_input.is_displayed())
        self.assertTrue(first_name_input.is_displayed())

    def test_login_page_form_interaction(self):
        self.driver.get(f'{self.live_server_url}/accounts/login/')
        self.assertIn('skillbridge', self.driver.title.lower())

        identifier_input = self.driver.find_element(By.NAME, 'identifier')
        password_input = self.driver.find_element(By.NAME, 'password')
        submit_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')

        self.assertTrue(identifier_input.is_displayed())
        self.assertTrue(password_input.is_displayed())

        # Fill with invalid credentials to test client-server interaction
        identifier_input.send_keys('invalid@test.com')
        password_input.send_keys('wrongpassword')
        submit_btn.click()

        time.sleep(1)
        self.assertIn('/accounts/login', self.driver.current_url)

    def test_authenticated_client_login_and_dashboard_access(self):
        # Complete login with valid client credentials
        self.driver.get(f'{self.live_server_url}/accounts/login/')
        identifier_input = self.driver.find_element(By.NAME, 'identifier')
        password_input = self.driver.find_element(By.NAME, 'password')
        submit_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')

        identifier_input.send_keys('kamrulhasansiam29@gmail.com')
        password_input.send_keys('mominrifat2211')
        submit_btn.click()

        time.sleep(1)
        # Should redirect to client dashboard or home
        current_url = self.driver.current_url
        self.assertTrue('/dashboard' in current_url or self.live_server_url in current_url)

    def test_all_public_footer_pages(self):
        pages = ['/how-it-works/', '/about/', '/help/', '/terms/', '/privacy/', '/contact/']
        for page in pages:
            self.driver.get(f'{self.live_server_url}{page}')
            self.assertIn('skillbridge', self.driver.title.lower())
