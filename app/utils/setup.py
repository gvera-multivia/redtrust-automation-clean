import os
import random
import tempfile
from uuid import uuid4

# THIRD PARTY PACKAGES 
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.proxy import Proxy

# PERSONAL PACKAGES - UTILS
from app.helper.loggerV2 import LoggerV2
from app.utils.utils import random_wait
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import shutil


USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    # Edge Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    # Chrome Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Firefox Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.78 Safari/537.36",
    # Safari Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    # Chrome Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.91 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; rv:115.0) Gecko/20100101 Firefox/115.0",
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.54 Safari/537.36",
    # Safari Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    # Firefox Linux
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    # Edge Windows
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/126.0.2592.54 Safari/537.36",
    # Chrome Android
    "Mozilla/5.0 (Linux; Android 14; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.54 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Samsung Galaxy S23) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.76 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; Mi 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.58 Mobile Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:126.0) Gecko/20100101 Firefox/126.0",
    # Safari Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15",
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.199 Safari/537.36",
    # Firefox Linux
    "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
    # Chrome Android
    "Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.199 Mobile Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:112.0) Gecko/20100101 Firefox/112.0",
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.5563.146 Safari/537.36",
    # Chrome Android
    "Mozilla/5.0 (Linux; Android 12; Redmi Note 10 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.76 Mobile Safari/537.36",
    # iPhone Safari
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
    # Chrome Android
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.76 Mobile Safari/537.36",
    # iPad Safari
    "Mozilla/5.0 (iPad; CPU OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
    # iPhone Safari
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    # iPad Safari
    "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    # iPhone Safari
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    # iPad Safari
    "Mozilla/5.0 (iPad; CPU OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    # Googlebot
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    # Headless Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/125.0.6422.78 Safari/537.36",
]


class WebDriverSetup:
    MAX_RETRIES = 3

    def __init__(self, temp_profile, portal_link:str, module:str, log_dir:str, filename:str, cliente:str, task_id: str, execution_id: str, site="default"):
        self.temp_profile = temp_profile
        self.portal_link = portal_link
        self.site = site
        self.logger = LoggerV2(
            execution_id=execution_id,
            module=module,
            class_name=self.__class__.__name__,
            log_dir=log_dir,
            filename=filename
        )
        self.cliente = cliente
        self.task_id = task_id

    def _create_download_directory(self, download_path):
        if not os.path.exists(download_path):
            self.logger.debug(self.cliente, self.task_id, "Pending", f"📂 Creando directorio de descargas: {download_path}")
            os.makedirs(download_path)
        self.logger.debug(self.cliente, self.task_id, "Pending", f"📂 Directorio de descargas ya existe: {download_path}")

    def setup_chrome_driver_descargas(self):
        user_agent = random.choice(USER_AGENTS)

        extension_path = os.path.join(
            os.environ['USERPROFILE'],
            "Documents", "workspace", "redtrust-automation", "app", "utils", f"chromedriver-win64-138", "ijdeibmhkjmgbjofgiaodomklfdnagdg", "5.0.4.0_0"
        )

        built_profile = os.path.join(
            os.environ['USERPROFILE'],
            "AppData", "Local", "Google", "Chrome", "User Data"
            # "Documents", "workspace", "redtrust-automation", "app", "utils", "chromedriver-win64-138"
        )

        # Copy entire contents of chromedriver-win64-138 into temp_profile
        data_dir = self.temp_profile
        try:
            # Prefer copytree merge when available (Python 3.8+)
            shutil.copytree(built_profile, data_dir, dirs_exist_ok=True)
        except TypeError:
            # Fallback for older Python: copy entries individually
            try:
                for item in os.listdir(built_profile):
                    s = os.path.join(built_profile, item)
                    d = os.path.join(data_dir, item)
                    if os.path.isdir(s):
                        if os.path.exists(d):
                            shutil.rmtree(d)
                        shutil.copytree(s, d)
                    else:
                        shutil.copy2(s, d)
            except Exception as e:
                print(f"Error copying chromedriver contents to tempfile: {e}")
                data_dir = built_profile
        except Exception as e:
            print(f"Error copying chromedriver contents to tempfile: {e}")
            data_dir = built_profile

        load_dotenv()
        DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR")
        download_path = os.path.join(DOWNLOAD_DIR, self.site, uuid4().hex[:8])
        self._create_download_directory(download_path)
        
        options = Options()
        options.add_argument(f"--user-data-dir={data_dir}")
        options.add_argument(f"--profile-directory=Default")
        options.add_argument("--remote-debugging-port=0")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_argument("--disable-infobars")
        options.add_argument(f"--load-extension={extension_path}")
        options.add_argument("--start-maximized")
        options.add_argument("--timeout=60000")
        options.add_argument("--log-level=3")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--no-default-browser-check")
        options.add_argument(f"--user-agent={user_agent}")

        options.proxy = Proxy({ 'proxyType': "MANUAL", 'httpProxy' : 'http://brd-customer-hl_e86cf638-zone-datacenter_proxy1:v1a7ys0slxf2@brd.superproxy.io:33335'})
        prefs = {
            "plugins.always_open_pdf_externally": True,
            "download.default_directory": download_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(120)
        driver.set_script_timeout(120)

        return self._load_page(driver), download_path

    def setup_chrome_driver_altas(self):
        user_agent = random.choice(USER_AGENTS)

        extension_path = os.path.join(
            os.environ['USERPROFILE'],
            "Documents", "workspace", "redtrust-automation", "app", "utils", f"chromedriver-win64-138", "ijdeibmhkjmgbjofgiaodomklfdnagdg", "5.0.4.0_0"
        )

        built_profile = os.path.join(
            os.environ['USERPROFILE'],
            "AppData", "Local", "Google", "Chrome", "User Data"
            # "Documents", "workspace", "redtrust-automation", "app", "utils", "chromedriver-win64-138"
        )

        # Copy entire contents of chromedriver-win64-138 into temp_profile
        data_dir = self.temp_profile
        try:
            # Prefer copytree merge when available (Python 3.8+)
            shutil.copytree(built_profile, data_dir, dirs_exist_ok=True)
        except TypeError:
            # Fallback for older Python: copy entries individually
            try:
                for item in os.listdir(built_profile):
                    s = os.path.join(built_profile, item)
                    d = os.path.join(data_dir, item)
                    if os.path.isdir(s):
                        if os.path.exists(d):
                            shutil.rmtree(d)
                        shutil.copytree(s, d)
                    else:
                        shutil.copy2(s, d)
            except Exception as e:
                print(f"Error copying chromedriver contents to tempfile: {e}")
                data_dir = built_profile
        except Exception as e:
            print(f"Error copying chromedriver contents to tempfile: {e}")
            data_dir = built_profile
        
        options = Options()
        options.add_argument(f"--user-data-dir={data_dir}")
        options.add_argument(f"--profile-directory=Default")
        options.add_argument("--remote-debugging-port=0")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_argument("--disable-infobars")
        options.add_argument(f"--load-extension={extension_path}")
        options.add_argument("--start-maximized")
        options.add_argument("--timeout=60000")
        options.add_argument("--log-level=3")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--no-default-browser-check")
        options.add_argument(f"--user-agent={user_agent}")

        options.proxy = Proxy({ 'proxyType': "MANUAL", 'httpProxy' : 'http://brd-customer-hl_e86cf638-zone-datacenter_proxy1:v1a7ys0slxf2@brd.superproxy.io:33335'})
        prefs = {
            "plugins.always_open_pdf_externally": True,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)
        
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(120)
        driver.set_script_timeout(120)

        return self._load_page(driver)

    def _load_page(self, driver: webdriver):
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                driver.get(self.portal_link)
                self.logger.info(self.cliente, self.task_id, "Pending", f"🔗 Cargando {self.portal_link} (Intento {attempt}/{self.MAX_RETRIES})")
                return driver
            except WebDriverException as e:
                self.logger.error(self.cliente, self.task_id, "Failure", f"⚠️ Error al cargar la página: {e}")
                if attempt < self.MAX_RETRIES:
                    random_wait('LONG', wait= True)
                else:
                    self.logger.error(self.cliente, self.task_id, "Failure", "⚠️ No se pudo cargar la página después de varios intentos.")
                    driver.quit()
                    raise SystemExit("⚠️ No se pudo cargar la página después de varios intentos.")
                
