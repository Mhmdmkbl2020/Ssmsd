import os
import sys
import time
import logging
import serial
import bluetooth
import tkinter as tk
from tkinter import ttk, messagebox
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyPDF2 import PdfReader
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager

# إعدادات عامة
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('PDFService.log'),
        logging.StreamHandler()
    ]
)

class BluetoothManager:
    def __init__(self):
        self.connected_device = None
        self.sock = None
        
    def pair_device(self):
        devices = bluetooth.discover_devices(duration=8, lookup_names=True)
        return devices
        
    def connect(self, address):
        self.sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        self.sock.connect((address, 1))
        self.connected_device = address
        
    def send_sms(self, number, message):
        if self.sock:
            self.sock.send(f"SMS:{number}:{message}".encode())

class PDFServiceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF Auto Sender")
        self.geometry("400x300")
        
        # حالة الخدمات
        self.whatsapp_enabled = False
        self.modem_sms_enabled = False
        self.bluetooth_sms_enabled = False
        
        # إعداد البلوتوث
        self.bluetooth_manager = BluetoothManager()
        
        # واجهة المستخدم
        self.create_widgets()
        
        # بدء المراقبة الخلفية
        self.observer = Observer()
        self.event_handler = PDFHandler(self)
        self.start_monitoring()
        
    def create_widgets(self):
        # إطار التحكم
        control_frame = ttk.LabelFrame(self, text="التحكم بالخدمات")
        control_frame.pack(pady=10, fill='x', padx=10)
        
        # زر الواتساب
        self.whatsapp_btn = ttk.Button(
            control_frame,
            text="تشغيل الواتساب",
            command=self.toggle_whatsapp
        )
        self.whatsapp_btn.pack(pady=5, fill='x')
        
        # زر مودم SMS
        self.modem_btn = ttk.Button(
            control_frame,
            text="تشغيل مودم SMS",
            command=self.toggle_modem_sms
        )
        self.modem_btn.pack(pady=5, fill='x')
        
        # زر بلوتوث SMS
        self.bluetooth_btn = ttk.Button(
            control_frame,
            text="تشغيل بلوتوث SMS",
            command=self.toggle_bluetooth_sms
        )
        self.bluetooth_btn.pack(pady=5, fill='x')
        
        # إطار البلوتوث
        bluetooth_frame = ttk.LabelFrame(self, text="إعدادات البلوتوث")
        bluetooth_frame.pack(pady=10, fill='x', padx=10)
        
        ttk.Button(
            bluetooth_frame,
            text="إقران جهاز جديد",
            command=self.pair_bluetooth
        ).pack(pady=5, fill='x')
        
    def toggle_whatsapp(self):
        self.whatsapp_enabled = not self.whatsapp_enabled
        self.whatsapp_btn.config(
            text="إيقاف الواتساب" if self.whatsapp_enabled else "تشغيل الواتساب"
        )
        logging.info(f"حالة الواتساب: {'مفعل' if self.whatsapp_enabled else 'معطل'}")
        
    def toggle_modem_sms(self):
        self.modem_sms_enabled = not self.modem_sms_enabled
        self.modem_btn.config(
            text="إيقاف مودم SMS" if self.modem_sms_enabled else "تشغيل مودم SMS"
        )
        logging.info(f"حالة مودم SMS: {'مفعل' if self.modem_sms_enabled else 'معطل'}")
        
    def toggle_bluetooth_sms(self):
        self.bluetooth_sms_enabled = not self.bluetooth_sms_enabled
        self.bluetooth_btn.config(
            text="إيقاف بلوتوث SMS" if self.bluetooth_sms_enabled else "تشغيل بلوتوث SMS"
        )
        logging.info(f"حالة بلوتوث SMS: {'مفعل' if self.bluetooth_sms_enabled else 'معطل'}")
        
    def pair_bluetooth(self):
        devices = self.bluetooth_manager.pair_device()
        if devices:
            device_list = "\n".join([f"{name} ({addr})" for addr, name in devices])
            messagebox.showinfo("الأجهزة المكتشفة", device_list)
            
            addr = devices[0][0]  # اختيار أول جهاز
            self.bluetooth_manager.connect(addr)
            messagebox.showinfo("تم الإقران", "تم الاتصال بنجاح!")
        else:
            messagebox.showerror("خطأ", "لم يتم العثور على أجهزة")
            
    def start_monitoring(self):
        for folder in ['sms', 'whatsapp']:
            os.makedirs(folder, exist_ok=True)
            
        self.observer.schedule(self.event_handler, 'sms', recursive=False)
        self.observer.schedule(self.event_handler, 'whatsapp', recursive=False)
        self.observer.start()
        
    def run(self):
        self.mainloop()
        self.observer.stop()
        self.observer.join()

class PDFHandler(FileSystemEventHandler):
    def __init__(self, app):
        self.app = app
        self.driver = None
        self.init_browser()
        
    def init_browser(self):
        try:
            options = Options()
            options.add_argument("--headless")
            service = Service(GeckoDriverManager().install())
            self.driver = webdriver.Firefox(service=service, options=options)
            self.driver.get("https://web.whatsapp.com")
            time.sleep(30)
        except Exception as e:
            logging.error(f"فشل تهيئة المتصفح: {str(e)}")
            
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.pdf'):
            Thread(target=self.process_file, args=(event.src_path,)).start()
            
    def process_file(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                reader = PdfReader(f)
                text = '\n'.join([page.extract_text() or '' for page in reader.pages])
                
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            number, message = lines[0], '\n'.join(lines[1:])
            
            if self.app.modem_sms_enabled:
                self.send_modem_sms(number, message)
                
            if self.app.bluetooth_sms_enabled:
                self.app.bluetooth_manager.send_sms(number, message)
                
            if self.app.whatsapp_enabled:
                self.send_whatsapp(file_path, number)
                
            os.remove(file_path)
            
        except Exception as e:
            logging.error(f"خطأ: {str(e)}")
            os.rename(file_path, f"failed_{os.path.basename(file_path)}")
            
    def send_modem_sms(self, number, message):
        try:
            with serial.Serial('COM3', 9600, timeout=1) as modem:
                modem.write(b'AT+CMGF=1\r')
                modem.write(f'AT+CMGS="{number}"\r'.encode() + message.encode() + b'\x1A')
        except Exception as e:
            logging.error(f"فشل إرسال SMS: {str(e)}")
            
    def send_whatsapp(self, file_path, number):
        try:
            self.driver.find_element(By.XPATH, '//div[@role="textbox"]').send_keys(number + Keys.ENTER)
            self.driver.find_element(By.XPATH, '//div[@title="إرفاق"]').click()
            self.driver.find_element(By.XPATH, '//input[@type="file"]').send_keys(os.path.abspath(file_path))
            time.sleep(2)
            self.driver.find_element(By.XPATH, '//div[@aria-label="إرسال"]').click()
        except Exception as e:
            logging.error(f"فشل إرسال واتساب: {str(e)}")
            self.init_browser()

if __name__ == '__main__':
    app = PDFServiceApp()
    app.run()
