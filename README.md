# 🚀 Linux Remote Control & Monitoring Telegram Bot

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Aiogram-3.x-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" alt="Aiogram" />
  <img src="https://img.shields.io/badge/OS-Linux%20%2F%20Ubuntu-E95420?style=for-the-badge&logo=ubuntu&logoColor=white" alt="Ubuntu" />
  <img src="https://img.shields.io/badge/Display-Wayland%20%26%20X11-FCC624?style=for-the-badge&logo=linux&logoColor=black" alt="Wayland" />
  <img src="https://img.shields.io/badge/Status-Production%20Ready-success?style=for-the-badge" alt="Status" />
</p>

Telegram orqali shaxsiy Linux (Ubuntu / GNOME / Wayland) noutbuk yoki kompyuteringizni masofadan toʻliq monitoring qilish, kuzatish va xavfsiz boshqarish imkonini beruvchi asinxron Telegram boti.

---

## 📑 Mundarija

- [Imkoniyatlar (Features)](#-imkoniyatlar-features)
- [Tizim Talablari (Requirements)](#-tizim-talablari-requirements)
- [O'rnatish va Sozlash (Installation)](#-ornatish-va-sozlash-installation)
- [GNOME Extension Sozlamasi](#-gnome-extension-sozlamasi)
- [Avtomatik Ishga Tushirish (Systemd Service)](#-avtomatik-ishga-tushirish-systemd-service)
- [Foydalanish va Buyruqlar (Commands)](#-foydalanish-va-buyruqlar-commands)
- [Arxitektura va Xavfsizlik](#-arxitektura-va-xavfsizlik)
- [Muammolarni Bartaraf Etish (Troubleshooting)](#-muammolarni-bartaraf-etish-troubleshooting)

---

## ✨ Imkoniyatlar (Features)

| Boʻlim | Imkoniyat | Tavsif |
|---|---|---|
| 📊 **Monitoring** | Tizim Holati | CPU, RAM, Disk boʻsh joyi, Batareya quvvati va zaryadlash holati, Wi-Fi SSID, Ovoz balandligi |
| 📱 **Faollik** | Active Window Tracker | Foydalanuvchi aynan qaysi dasturda (Chrome, PyCharm, VS Code, Terminal va h.k.) ishlayotganini aniqlash |
| 📸 **Kamera** | Web-camera Capture | Noutbukning veb-kamerasi orqali bir zumda 1080p sifatda surat olib Telegramga yuborish (`fswebcam`) |
| 🎵 **Spotify** | Spotify Controller | Noutbukda Spotify'ni ochish, treklarni boshqarish (Play/Pause, Next, Prev, trek va ijrochi nomi) |
| 🔊 **Ovoz** | Volume Control | Inline tugmalar orqali ovozni boshqarish (+10%, -10%, Mute/Unmute) |
| 🔒 **Qulflash** | Lock Screen | Ekranni masofadan bir zumda qulflash (`gdbus` / `loginctl`) |
| 📋 **Clipboard** | Vaqtinchalik Xotira | Noutbuk clipboardidagi matnni oʻqish va yangi matn nusxalash (`wl-clipboard`) |
| 🔔 **Xabarnoma** | Desktop Notification | Noutbuk ekraniga yuqori darajadagi (Critical) xabar chiqarish (`notify-send`) |
| 📅 **Hisobot** | Screen Time & Daily Report | Har daqiqada ilovalar vaqtini yigʻish va har kuni 23:55 da umumiy kunlik hisobotni joʻnatish |
| 🔋 **Ogohlantirish** | Low Battery Alert | Batareya 20% dan tushib ketganda Telegramga avtomatik ogohlantirish yuborish |
| 🟢 **Startup Alert** | Boot Notification | Noutbuk yoqilganda administratorga holat xabarini yuborish |
| 🔄 / 🛑 **Quvvat** | Reboot / Shutdown | Tasdiqlash dialogi orqali xavfsiz qayta ishga tushirish yoki oʻchirish |

---

## 📦 Tizim Talablari (Requirements)

Bot Linux (Wayland yoki X11) tizim buyruqlari bilan ishlaydi. Kerakli paketlarni oʻrnating:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip \
                    fswebcam \
                    wl-clipboard pulseaudio-utils network-manager libnotify-bin
```

---

## 🛠 O'rnatish va Sozlash (Installation)

### 1. Loyihani yuklab oling:
```bash
git clone https://github.com/USERNAME/remote_bot.git
cd remote_bot
```

### 2. Python virtual muhitini (venv) yarating va paketlarni o'rnating:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Konfiguratsiyani sozlang (`.env`):
`.env.example` faylidan nusxa oling va oʻzingizning maʼlumotlaringizni kiriting:
```bash
cp .env.example .env
nano .env
```

`.env` fayli namunasi:
```ini
# Telegram Bot Token (@BotFather orqali olingan)
BOT_TOKEN=8930960513:AAFcGZfimSz3WtgEmsTc7iwj8rTQAUjLNY4

# Sizning Telegram raqamli ID'ingiz (@userinfobot orqali olishingiz mumkin)
ADMIN_ID=8200157886

# Sozlamalar
TIMEZONE=Asia/Tashkent
TRACK_INTERVAL_SECONDS=60
DAILY_REPORT_HOUR=23
DAILY_REPORT_MINUTE=55
LOW_BATTERY_THRESHOLD=20
```

### 4. Botni sinov tariqasida ishga tushiring:
```bash
python bot.py
```
Telegramda botingizga `/start` buyrugʻini yuboring.

---

## 🧩 GNOME Extension Sozlamasi (Tavsiya etiladi)

Wayland muhitida xavfsizlik cheklovlari tufayli boshqa oynalar nomini toʻgʻridan-toʻgʻri oʻqib boʻlmaydi. Bot 100% aniqlikda fokusdagi dastur nomini olishi uchun **Window Calls** GNOME extensionidan foydalanadi:

1. Brauzerda [Window Calls Extension](https://extensions.gnome.org/extension/4724/window-calls/) sahifasiga kiring.
2. Extensionni yoqing (**ON**).
3. Bot avtomatik ravishda D-Bus orqali ochiq oynalarni taniydi. *(Extension boʻlmasa, bot avtomatik ravishda jarayonlar tahliliga (fallback) oʻtadi).*

---

## ⚙️ Avtomatik Ishga Tushirish (Systemd Service)

Noutbuk yoqilishi bilan bot fonda avtomatik va toʻxtovsiz ishlashi uchun `systemd` user xizmatini sozlang:

```bash
# 1. Systemd user katalogini yarating (agar yo'q bo'lsa)
mkdir -p ~/.config/systemd/user/

# 2. Xizmat faylini ko'chiring
cp remote-bot.service ~/.config/systemd/user/

# 3. Systemd'ni qayta yuklang va xizmatni yoqing
systemctl --user daemon-reload
systemctl --user enable --now remote-bot.service

# 4. Holatini tekshirish
systemctl --user status remote-bot.service
```

### Xizmat boshqaruv buyruqlari:
```bash
# Xizmatni qayta ishga tushirish (yangilanishlardan so'ng)
systemctl --user restart remote-bot.service

# Xizmat loglarini jonli ko'rish
journalctl --user-unit=remote-bot.service -f
```

---

## 🎮 Foydalanish va Buyruqlar (Commands)

Botdagi barcha imkoniyatlar qulay menyu tugmalari orqali boshqariladi:

```
┌─────────────────┬─────────────────┐
│   📊 Holat      │   📸 Kamera     │
├─────────────────┼─────────────────┤
│   🎵 Spotify    │   🔊 Ovoz       │
├─────────────────┼─────────────────┤
│   🔒 Qulflash   │   📋 Clipboard  │
├─────────────────┼─────────────────┤
│ 📅 Kunlik hisob │ 🔔 Xabar yubor  │
├─────────────────┼─────────────────┤
│ 🔄 Qayta yoqish │   🛑 O'chirish  │
└─────────────────┴─────────────────┘
```

- **📊 Holat (`/status`)**: CPU, RAM, Disk, Batareya, Wi-Fi, Ovoz va ayni paytda ochiq boʻlgan dastur haqida toʻliq hisobot.
- **📸 Kamera (`/photo`)**: Veb-kameradan bir zumda foto oladi va yuboradi.
- **🎵 Spotify (`/spotify`)**: Noutbukda Spotify'ni ishga tushirish va treklarni boshqarish pulti (Play/Pause, Next, Prev, trek va ijrochi nomi).
- **🔊 Ovoz**: Ovozni pasaytirish/koʻtarish yoki Mute qilish uchun qulay inline menyu.
- **📋 Clipboard**: Kompyuterdan nusxa olingan matnni olish yoki kompyuter xotirasiga yangi matn joylash.
- **📅 Kunlik hisobot (`/report`)**: Kun davomida qaysi dasturlarda necha soat ishlaganingiz va batareya dinamikasi haqida hisobot.
- **🔔 Xabar yuborish**: Noutbuk ekraniga pop-up xabarnoma chiqaradi.
- **🔄 Qayta yoqish (`/reboot`) & 🛑 Oʻchirish (`/shutdown`)**: Tasdiqlash tugmasi orqali tizimni boshqarish.

---

## 🔒 Arxitektura va Xavfsizlik

1. **Ruxsat Cheklovi (Access Control):** Faqat `.env` dagi `ADMIN_ID` foydalanuvchisi soʻrovlariga javob beradi. Begona foydalanuvchilar urinishlari avtomatik bloklanadi va log fayliga qayd etiladi.
2. **Toʻliq Asinxron:** Barcha tizim buyruqlari (`nmcli`, `fswebcam`, `pactl`, `wl-copy`) `asyncio.to_thread` orqali alohida oqimlarda bajariladi, shuning uchun hech qanday buyruq botni qotirib qoʻymaydi.
3. **Doimiy Xotira (Data Persistence):** Kunlik statistika har daqiqada `daily_stats.json` fayliga xavfsiz (atomic) yozib boriladi. Noutbuk oʻchib yonsa ham hisob-kitoblar yoʻqolmaydi.
4. **Sleep/Wake Recovery:** Agar noutbuk soat 23:55 da uyqu rejimida boʻlgan boʻlsa, ertalab yoqilganda oʻtgan kungi hisobot avtomatik tarzda Telegramga yuboriladi.

---

## ❓ Muammolarni Bartaraf Etish (Troubleshooting)

- **Kamera xatoligi bersa:** Kamera boshqa dastur (Zoom, brauzer) tomonidan band qilinmaganligini tekshiring:
  ```bash
  fuser /dev/video0
  ```
- **Loglarni ko'rish:**
  ```bash
  tail -f remote_bot.log
  ```

---

## 👨‍💻 Muallif

Loyiha shaxsiy noutbukni masofadan toʻliq va qulay boshqarish uchun yaratilgan.
Savollar va takliflar boʻyicha GitHub Issues orqali murojaat qilishingiz mumkin.
