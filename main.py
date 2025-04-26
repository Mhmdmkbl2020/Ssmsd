import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import serial
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# إعداد مراقب المجلدات
class FolderMonitor(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        filepath = event.src_path
        if filepath.endswith('.pdf'):
            print(f"New file detected: {filepath}")
            # هنا يمكنك إضافة المعالجة مثل استخراج النصوص أو إرسال الرسائل
            process_file(filepath)

def process_file(filepath):
    # استخراج النصوص من ملف PDF (يمكنك استخدام PyPDF2)
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(filepath)
        text = "\n".join(page.extract_text() for page in reader.pages)
        
        # استخراج الرقم والرسالة
        lines = text.splitlines()
        number = None
        message = []
        for line in lines:
            if line.strip():  # أول سطر غير فارغ
                if not number:
                    number = line.strip()  # الرقم
                else:
                    message.append(line.strip())  # الرسالة
        message = "\n".join(message)
        
        # إرسال SMS
        if number and message:
            send_sms_via_gsm("COM3", number, message)

        # إرسال WhatsApp
        send_whatsapp_message(number, filepath)
        
        # حذف الملف
        os.remove(filepath)
        print(f"File {filepath} processed and deleted.")
    except Exception as e:
        print(f"Error processing file {filepath}: {e}")

# إرسال رسائل SMS باستخدام مودم GSM
def send_sms_via_gsm(modem_port, phone_number, message):
    try:
        modem = serial.Serial(modem_port, baudrate=9600, timeout=1)
        modem.write(b'AT+CMGF=1\r')  # وضع النصوص
        modem.write(f'AT+CMGS="{phone_number}"\r'.encode('utf-8'))
        modem.write(message.encode('utf-8') + b'\x1A')  # إنهاء بـ Ctrl+Z
        print(f"SMS sent to {phone_number}")
    except Exception as e:
        print(f"Failed to send SMS: {e}")
    finally:
        modem.close()

# إرسال رسائل WhatsApp باستخدام WhatsApp Web
def send_whatsapp_message(phone_number, file_path):
    try:
        driver = webdriver.Chrome()
        driver.get("https://web.whatsapp.com")
        input("Scan the QR code and press Enter...")
        
        search_box = driver.find_element(By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')
        search_box.send_keys(phone_number)
        search_box.send_keys(Keys.ENTER)
        
        attach_button = driver.find_element(By.XPATH, '//span[@data-icon="clip"]')
        attach_button.click()
        
        file_input = driver.find_element(By.XPATH, '//input[@type="file"]')
        file_input.send_keys(file_path)
        
        send_button = driver.find_element(By.XPATH, '//span[@data-icon="send"]')
        send_button.click()
        print(f"WhatsApp message sent to {phone_number}")
    except Exception as e:
        print(f"Failed to send WhatsApp message: {e}")
    finally:
        driver.quit()

# مراقبة المجلدات
def monitor_folder(folder_path):
    event_handler = FolderMonitor()
    observer = Observer()
    observer.schedule(event_handler, folder_path, recursive=False)
    observer.start()
    print(f"Monitoring folder: {folder_path}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    sms_folder = "./sms"
    whatsapp_folder = "./whatsapp"

    os.makedirs(sms_folder, exist_ok=True)
    os.makedirs(whatsapp_folder, exist_ok=True)

    monitor_folder(sms_folder)
    monitor_folder(whatsapp_folder)
