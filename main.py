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
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)

def resource_path(relative_path):
    """ حل مشكلة مسارات الملفات عند التجميع """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, relative_path)

class PDFHandler(FileSystemEventHandler):
    """ معالج أحداث نظام الملفات للمجلدات المراقبة """
    def on_created(self, event):
        try:
            if not event.is_directory and event.src_path.lower().endswith('.pdf'):
                logging.info(f'تم اكتشاف ملف جديد: {event.src_path}')
                self.process_pdf(event.src_path)
        except Exception as e:
            logging.error(f'خطأ في معالجة الحدث: {str(e)}')

    def process_pdf(self, file_path):
        """ معالجة ملف PDF واستخراج المعلومات """
        try:
            # استخراج النص من PDF
            with open(file_path, 'rb') as file:
                reader = PdfReader(file)
                text = '\n'.join(page.extract_text() or '' for page in reader.pages)

            # تحليل المحتوى
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if len(lines) < 2:
                raise ValueError('الملف لا يحتوي على معلومات كافية')
            
            phone_number = lines[0]
            message = '\n'.join(lines[1:])

            # إرسال الرسائل
            self.send_sms(phone_number, message)
            self.send_whatsapp(phone_number, file_path)

            # تنظيف الملف
            os.remove(file_path)
            logging.info(f'تم معالجة الملف بنجاح: {os.path.basename(file_path)}')

        except Exception as e:
            logging.error(f'خطأ في معالجة الملف {file_path}: {str(e)}')
            os.rename(file_path, os.path.join('failed', os.path.basename(file_path)))

    def send_sms(self, number, message):
        """ إرسال SMS عبر منفذ COM """
        try:
            with serial.Serial(
                port='COM3',
                baudrate=9600,
                timeout=1
            ) as modem:
                modem.write(b'AT+CMGF=1\r')
                modem.write(f'AT+CMGS="{number}"\r'.encode('utf-8'))
                modem.write(message.encode('utf-8') + b'\x1A')
                logging.info(f'تم إرسال SMS إلى {number}')
        except Exception as e:
            logging.error(f'فشل إرسال SMS: {str(e)}')

    def send_whatsapp(self, number, file_path):
        """ إرسال ملف عبر WhatsApp Web """
        try:
            # إعداد المتصفح مع WebDriver Manager
            service = Service(ChromeDriverManager().install())
            options = webdriver.ChromeOptions()
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            
            driver = webdriver.Chrome(service=service, options=options)
            driver.get('https://web.whatsapp.com')
            
            # انتظار مسح QR code
            input('الرجاء مسح رمز QR ثم الضغط على Enter...')
            
            # البحث عن الرقم
            search_box = driver.find_element(By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')
            search_box.send_keys(number + Keys.ENTER)
            
            # إرفاق الملف
            attach_btn = driver.find_element(By.XPATH, '//span[@data-icon="clip"]')
            attach_btn.click()
            
            file_input = driver.find_element(By.XPATH, '//input[@type="file"]')
            file_input.send_keys(os.path.abspath(file_path))
            
            # إرسال الملف
            send_btn = driver.find_element(By.XPATH, '//span[@data-icon="send"]')
            send_btn.click()
            time.sleep(5)
            
            logging.info(f'تم الإرسال إلى {number} عبر WhatsApp')
            
        except Exception as e:
            logging.error(f'فشل إرسال WhatsApp: {str(e)}')
        finally:
            if 'driver' in locals():
                driver.quit()

def monitor_folders():
    """ بدء مراقبة المجلدات """
    folders = ['sms', 'whatsapp']
    observer = Observer()
    
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
        event_handler = PDFHandler()
        observer.schedule(event_handler, folder, recursive=False)
        logging.info(f'بدأت المراقبة على مجلد: {folder}')
    
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == '__main__':
    # إنشاء المجلدات الضرورية
    for folder in ['sms', 'whatsapp', 'logs', 'failed']:
        os.makedirs(folder, exist_ok=True)
    
    monitor_folders()
