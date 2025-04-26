import os
import sys
import time
import logging
import win32serviceutil
import servicemanager
import win32event
import win32service
import serial
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyPDF2 import PdfReader
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager

# إعداد نظام التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('PDFService.log'),
        logging.StreamHandler()
    ]
)

class PDFService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PDFAutoSender"
    _svc_display_name_ = "PDF Auto Sender Service"
    _svc_description_ = "Automatically processes PDF files and sends notifications via SMS and WhatsApp"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.observer = None
        self.driver = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        if self.observer:
            self.observer.stop()
        if self.driver:
            self.driver.quit()

    def SvcDoRun(self):
        self.initialize_services()
        self.start_monitoring()

    def initialize_services(self):
        try:
            options = Options()
            options.add_argument("--headless")
            service = Service(GeckoDriverManager().install())
            self.driver = webdriver.Firefox(service=service, options=options)
            self.driver.get("https://web.whatsapp.com")
            logging.info("تم تهيئة متصفح Firefox بنجاح")
            time.sleep(30)  # وقت لمسح QR code
        except Exception as e:
            logging.error(f"فشل في تهيئة المتصفح: {str(e)}")

    class PDFHandler(FileSystemEventHandler):
        def __init__(self, outer):
            self.outer = outer

        def on_created(self, event):
            if not event.is_directory and event.src_path.lower().endswith('.pdf'):
                logging.info(f"تم اكتشاف ملف جديد: {event.src_path}")
                self.process_file(event.src_path)

        def process_file(self, file_path):
            try:
                with open(file_path, 'rb') as f:
                    reader = PdfReader(f)
                    text = '\n'.join([page.extract_text() or '' for page in reader.pages])

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
                self.outer.driver.find_element(By.XPATH, '//div[@role="textbox"]').send_keys(number + Keys.ENTER)
                self.outer.driver.find_element(By.XPATH, '//div[@title="إرفاق"]').click()
                self.outer.driver.find_element(By.XPATH, '//input[@type="file"]').send_keys(os.path.abspath(file_path))
                time.sleep(2)
                self.outer.driver.find_element(By.XPATH, '//div[@aria-label="إرسال"]').click()
                logging.info(f"تم الإرسال عبر واتساب إلى {number}")
            except Exception as e:
                logging.error(f"فشل إرسال واتساب: {str(e)}")
                self.outer.initialize_services()

    def start_monitoring(self):
        for folder in ['sms', 'whatsapp']:
            os.makedirs(folder, exist_ok=True)

        event_handler = self.PDFHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, 'sms', recursive=False)
        self.observer.schedule(event_handler, 'whatsapp', recursive=False)
        self.observer.start()
        logging.info("بدأت الخدمة بنجاح")

        while True:
            time.sleep(10)

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(PDFService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(PDFService)
