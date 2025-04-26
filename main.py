import os
import time
import sys
import serial
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyPDF2 import PdfReader
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, relative_path)

class FolderMonitor(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        filepath = event.src_path
        if filepath.endswith('.pdf'):
            print(f"تم اكتشاف ملف جديد: {filepath}")
            process_file(filepath)

def process_file(filepath):
    try:
        reader = PdfReader(filepath)
        text = "\n".join(page.extract_text() for page in reader.pages)
        
        lines = text.splitlines()
        number, message = None, []
        for line in lines:
            if line.strip():
                if not number:
                    number = line.strip()
                else:
                    message.append(line.strip())
        
        if number and message:
            send_sms_via_gsm("COM3", number, "\n".join(message))
            send_whatsapp_message(number, filepath)
            
        os.remove(filepath)
        print(f"تم معالجة الملف وحذفه: {filepath}")
    except Exception as e:
        print(f"خطأ في المعالجة: {str(e)}")

def send_sms_via_gsm(modem_port, number, message):
    try:
        modem = serial.Serial(modem_port, baudrate=9600, timeout=1)
        modem.write(b'AT+CMGF=1\r')
        modem.write(f'AT+CMGS="{number}"\r'.encode('utf-8'))
        modem.write(message.encode('utf-8') + b'\x1A')
        print(f"تم إرسال SMS إلى {number}")
        modem.close()
    except Exception as e:
        print(f"فشل إرسال SMS: {str(e)}")

def send_whatsapp_message(number, file_path):
    try:
        driver = webdriver.Chrome(executable_path=resource_path('chromedriver.exe'))
        driver.get("https://web.whatsapp.com")
        input("امسح QR code ثم اضغط Enter...")
        
        search_box = driver.find_element(By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')
        search_box.send_keys(number + Keys.ENTER)
        
        attach_button = driver.find_element(By.XPATH, '//span[@data-icon="clip"]')
        attach_button.click()
        
        file_input = driver.find_element(By.XPATH, '//input[@type="file"]')
        file_input.send_keys(file_path)
        
        send_button = driver.find_element(By.XPATH, '//span[@data-icon="send"]')
        send_button.click()
        time.sleep(5)
        driver.quit()
        print(f"تم إرسال ملف عبر WhatsApp إلى {number}")
    except Exception as e:
        print(f"فشل إرسال WhatsApp: {str(e)}")

def monitor_folder(folder):
    event_handler = FolderMonitor()
    observer = Observer()
    observer.schedule(event_handler, folder, recursive=False)
    observer.start()
    print(f"جاري مراقبة المجلد: {folder}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    for folder in ['sms', 'whatsapp']:
        os.makedirs(folder, exist_ok=True)
    
    monitor_folder('sms')
    monitor_folder('whatsapp')
