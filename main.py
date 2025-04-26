import os
import sys
import time
import logging
import serial
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyPDF2 import PdfReader
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# إعداد نظام التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)

class PDFHandler(FileSystemEventHandler):
    def __init__(self):
        self.driver = None
        self.init_browser()

    def init_browser(self):
        try:
            service = Service(ChromeDriverManager().install())
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.get('https://web.whatsapp.com')
            time.sleep(15)  # وقت لمسح QR code
        except Exception as e:
            logging.error(f"فشل في تهيئة المتصفح: {str(e)}")

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.pdf'):
            logging.info(f'تم اكتشاف ملف جديد: {event.src_path}')
            self.process_file(event.src_path)

    def process_file(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                reader = PdfReader(f)
                text = '\n'.join(page.extract_text() or '' for page in reader.pages)
            
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if len(lines) < 2:
                raise ValueError("تنسيق الملف غير صحيح")
            
            number = lines[0]
            message = '\n'.join(lines[1:])
            
            self.send_sms(number, message)
            self.send_whatsapp(file_path, number)
            
            os.remove(file_path)
            logging.info(f"تمت معالجة الملف: {os.path.basename(file_path)}")
            
        except Exception as e:
            logging.error(f"خطأ في المعالجة: {str(e)}")
            os.rename(file_path, f"failed_{os.path.basename(file_path)}")

    def send_sms(self, number, message):
        try:
            with serial.Serial('COM3', 9600, timeout=1) as modem:
                modem.write(b'AT+CMGF=1\r')
                modem.write(f'AT+CMGS="{number}"\r'.encode('utf-8'))
                modem.write(message.encode('utf-8') + b'\x1A')
                logging.info(f"تم إرسال SMS إلى {number}")
        except Exception as e:
            logging.error(f"فشل إرسال SMS: {str(e)}")

    def send_whatsapp(self, file_path, number):
        try:
            self.driver.find_element(By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]').send_keys(number + Keys.ENTER)
            self.driver.find_element(By.XPATH, '//span[@data-icon="clip"]').click()
            self.driver.find_element(By.XPATH, '//input[@type="file"]').send_keys(os.path.abspath(file_path))
            self.driver.find_element(By.XPATH, '//span[@data-icon="send"]').click()
            time.sleep(3)
            logging.info(f"تم الإرسال عبر واتساب إلى {number}")
        except Exception as e:
            logging.error(f"فشل إرسال واتساب: {str(e)}")
            self.init_browser()

def main():
    for folder in ['sms', 'whatsapp']:
        os.makedirs(folder, exist_ok=True)
    
    event_handler = PDFHandler()
    observer = Observer()
    observer.schedule(event_handler, 'sms', recursive=False)
    observer.schedule(event_handler, 'whatsapp', recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == '__main__':
    main()
