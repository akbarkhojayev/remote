"""
Telegram Remote Control & Monitoring Bot for Linux (Ubuntu / GNOME / Wayland).
Universal, Asinxron, Ma'lumotlarni yo'qotmaydigan va Zamonaviy Dizaynga ega Tizim.
Muallif: Abz
"""

import os
import re
import sys
import json
import socket
import logging
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter
from typing import Optional, Dict, Any, Tuple, List

import psutil
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    FSInputFile,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage


# ==============================================================================
# 1. KONFIGURATSIYA VA .ENV YUKLASH
# ==============================================================================

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
LOG_FILE = BASE_DIR / "remote_bot.log"
STATS_FILE = BASE_DIR / "daily_stats.json"


def load_env():
    """Tizim muhit o'zgaruvchilari va .env faylini yuklaydi."""
    if ENV_FILE.exists():
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key not in os.environ:
                        os.environ[key] = val
        except Exception as e:
            print(f"Ogohlantirish: .env faylini o'qishda xatolik: {e}", file=sys.stderr)


load_env()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID_RAW = os.environ.get("ADMIN_ID", "0").strip()

try:
    ADMIN_ID = int(ADMIN_ID_RAW)
except ValueError:
    ADMIN_ID = 0

if not BOT_TOKEN or not ADMIN_ID:
    print(
        "XATOLIK: BOT_TOKEN yoki ADMIN_ID .env faylida topilmadi!\n"
        "Iltimos, .env faylini to'g'ri to'ldiring (.env.example ga qarang).",
        file=sys.stderr,
    )
    sys.exit(1)

TIMEZONE_STR = os.environ.get("TIMEZONE", "Asia/Tashkent")
try:
    UZ_TZ = ZoneInfo(TIMEZONE_STR)
except Exception:
    UZ_TZ = ZoneInfo("Asia/Tashkent")

TRACK_INTERVAL_SECONDS = int(os.environ.get("TRACK_INTERVAL_SECONDS", "60"))
DAILY_REPORT_HOUR = int(os.environ.get("DAILY_REPORT_HOUR", "23"))
DAILY_REPORT_MINUTE = int(os.environ.get("DAILY_REPORT_MINUTE", "55"))
LOW_BATTERY_THRESHOLD = int(os.environ.get("LOW_BATTERY_THRESHOLD", "20"))


# ==============================================================================
# 2. LOGGING SOZLAMALARI
# ==============================================================================

logger = logging.getLogger("remote_bot")
logger.setLevel(logging.INFO)

log_formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)

if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

logging.getLogger("aiogram").setLevel(logging.INFO)


# ==============================================================================
# 3. BOT VA FSM HOLATLARI
# ==============================================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class NotifyState(StatesGroup):
    waiting_text = State()


class ClipboardState(StatesGroup):
    waiting_text = State()


# ==============================================================================
# 4. TUGMALAR VA MENYULAR (MODERN DESIGN)
# ==============================================================================

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Holat"), KeyboardButton(text="📸 Kamera")],
        [KeyboardButton(text="🎵 Spotify"), KeyboardButton(text="🔊 Ovoz")],
        [KeyboardButton(text="🔒 Qulflash"), KeyboardButton(text="📋 Clipboard")],
        [KeyboardButton(text="📅 Kunlik hisobot"), KeyboardButton(text="🔔 Xabar yuborish")],
        [KeyboardButton(text="🔄 Qayta yoqish"), KeyboardButton(text="🛑 O'chirish")],
    ],
    resize_keyboard=True,
)

status_inline_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Yangilash", callback_data="status_refresh"),
            InlineKeyboardButton(text="📸 Kamera", callback_data="quick_photo"),
            InlineKeyboardButton(text="🎵 Spotify", callback_data="quick_music"),
        ]
    ]
)

music_inline_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="⏮ Oldingi", callback_data="mus_prev"),
            InlineKeyboardButton(text="⏯ Play / Pause", callback_data="mus_play_pause"),
            InlineKeyboardButton(text="⏭ Keyingi", callback_data="mus_next"),
        ],
        [
            InlineKeyboardButton(text="🟢 Spotify'ni Ochish", callback_data="mus_open_spotify"),
            InlineKeyboardButton(text="🔄 Yangilash", callback_data="mus_refresh"),
        ]
    ]
)

volume_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🔉 -10%", callback_data="vol_down"),
            InlineKeyboardButton(text="🔇 Mute / Unmute", callback_data="vol_mute"),
            InlineKeyboardButton(text="🔊 +10%", callback_data="vol_up"),
        ]
    ]
)

clipboard_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="📥 Matnni o'qish", callback_data="clip_get"),
            InlineKeyboardButton(text="📤 Yangi matn yozish", callback_data="clip_set"),
        ]
    ]
)


def confirm_kb(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_{action}"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel"),
            ]
        ]
    )


# ==============================================================================
# 5. KUNLIK STATISTIKA VA DOIMIYLIK (PERSISTENCE)
# ==============================================================================

daily_stats: Dict[str, Any] = {
    "date": datetime.now(UZ_TZ).strftime("%Y-%m-%d"),
    "app_minutes": Counter(),
    "battery_samples": [],
    "report_sent": False,
}

low_battery_notified = False

SYSTEM_IGNORE_CLASSES = {
    "org.gnome.shell", "gnome-shell", "desktop", "mutter",
    "mutter-x11-frames", "mutter-guard-window", "dock", "", "bosh ekran"
}


def get_device_name() -> str:
    """Qurilma modelini aniqlaydi (Surface Laptop, ThinkPad, Ubuntu PC va h.k.)."""
    env_name = os.environ.get("DEVICE_NAME", "").strip()
    if env_name:
        return env_name

    try:
        p = Path("/sys/devices/virtual/dmi/id/product_name")
        if p.exists():
            val = p.read_text(encoding="utf-8").strip()
            if val and val.lower() not in ("system product name", "to be filled by o.e.m.", "default string", "none"):
                return val
    except Exception:
        pass

    try:
        vendor_p = Path("/sys/devices/virtual/dmi/id/sys_vendor")
        vendor = vendor_p.read_text(encoding="utf-8").strip() if vendor_p.exists() else ""
        if vendor and vendor.lower() not in ("system manufacturer", "to be filled by o.e.m."):
            return f"{vendor} Linux"
    except Exception:
        pass

    try:
        h = socket.gethostname()
        if h and h.lower() not in ("localhost", "sandbox", "none"):
            return f"{h} (Linux)"
    except Exception:
        pass

    return "Linux Qurilma"


def make_progress_bar(percent: int, length: int = 8) -> str:
    """Foiz uchun ixcham va chiroyli progress-bar tayyorlaydi."""
    filled = round(percent / 100 * length)
    filled = max(0, min(length, filled))
    return f"[{'■' * filled}{'□' * (length - filled)}]"


def load_daily_stats():
    """Diskdagi daily_stats.json faylidan statistikani yuklaydi."""
    global daily_stats
    today_str = datetime.now(UZ_TZ).strftime("%Y-%m-%d")

    if STATS_FILE.exists():
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("date") == today_str:
                    daily_stats["date"] = today_str
                    daily_stats["app_minutes"] = Counter(data.get("app_minutes", {}))
                    daily_stats["battery_samples"] = data.get("battery_samples", [])
                    daily_stats["report_sent"] = bool(data.get("report_sent", False))
                    logger.info(f"Bugungi statistika qayta tiklandi ({today_str}).")
                    return
                else:
                    daily_stats = {
                        "date": data.get("date"),
                        "app_minutes": Counter(data.get("app_minutes", {})),
                        "battery_samples": data.get("battery_samples", []),
                        "report_sent": bool(data.get("report_sent", False)),
                    }
                    logger.info(f"O'tgan kungi statistika yuklandi ({data.get('date')}).")
                    return
        except Exception as e:
            logger.warning(f"daily_stats.json faylini o'qishda xatolik: {e}")

    reset_daily_stats(today_str)


def save_daily_stats():
    """Statistikani daily_stats.json fayliga xavfsiz (atomic) yozadi."""
    try:
        data = {
            "date": daily_stats.get("date"),
            "app_minutes": dict(daily_stats.get("app_minutes", {})),
            "battery_samples": daily_stats.get("battery_samples", [])[-200:],
            "report_sent": daily_stats.get("report_sent", False),
        }
        temp_file = STATS_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        temp_file.replace(STATS_FILE)
    except Exception as e:
        logger.error(f"Statistikani saqlashda xatolik: {e}")


def reset_daily_stats(date_str: Optional[str] = None):
    """Kunlik statistikani tozalaydi."""
    global daily_stats
    if not date_str:
        date_str = datetime.now(UZ_TZ).strftime("%Y-%m-%d")
    daily_stats["date"] = date_str
    daily_stats["app_minutes"] = Counter()
    daily_stats["battery_samples"] = []
    daily_stats["report_sent"] = False
    save_daily_stats()
    logger.info(f"Kunlik statistika tozalandi: {date_str}")


# ==============================================================================
# 6. TIZIM VA WAYLAND ASINXRON FUNKSIYALARI
# ==============================================================================

def get_wayland_env() -> Dict[str, str]:
    """Wayland va GNOME D-Bus uchun kerakli muhit o'zgaruvchilarini shakllantiradi."""
    uid = os.getuid()
    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
    env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"
    if "WAYLAND_DISPLAY" not in env:
        env["WAYLAND_DISPLAY"] = "wayland-0"
    if "DISPLAY" not in env:
        env["DISPLAY"] = ":0"
    return env


def _sync_get_wifi_name() -> str:
    """Wi-Fi yoki faol tarmoq nomini ko'p bosqichli ishonchli usulda aniqlaydi."""
    env = get_wayland_env()

    # 1-usul: nmcli active connection list (juda tez, skanersiz)
    try:
        output = subprocess.check_output(
            ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"],
            env=env,
            timeout=2.5,
        ).decode("utf-8", errors="ignore")
        for line in output.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            name, conn_type = line.split(":", 1)
            name = name.strip()
            conn_type_lower = conn_type.lower()
            if any(w in conn_type_lower for w in ("wireless", "wifi", "802-11-wireless")):
                return name
            elif any(e in conn_type_lower for e in ("ethernet", "802-3-ethernet")):
                return f"LAN ({name})"
    except Exception:
        pass

    # 2-usul: nmcli dev wifi list
    try:
        output = subprocess.check_output(
            ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
            env=env,
            timeout=3,
        ).decode("utf-8", errors="ignore")
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("yes:"):
                ssid = line.split("yes:")[-1].strip()
                if ssid:
                    return ssid
    except Exception:
        pass

    # 3-usul: iwgetid (wireless-tools)
    try:
        output = subprocess.check_output(["iwgetid", "-r"], timeout=1.5).decode("utf-8", errors="ignore").strip()
        if output:
            return output
    except Exception:
        pass

    # 4-usul: iw dev
    try:
        output = subprocess.check_output(["iw", "dev"], timeout=1.5).decode("utf-8", errors="ignore")
        m = re.search(r"ssid\s+(.+)", output)
        if m and m.group(1).strip():
            return m.group(1).strip()
    except Exception:
        pass

    # 5-usul: Internet yo'nalishi (ip route)
    try:
        output = subprocess.check_output(["ip", "route", "get", "1.1.1.1"], timeout=1.5).decode("utf-8", errors="ignore")
        if "via" in output or "dev" in output:
            m = re.search(r"dev\s+(\S+)", output)
            if m:
                iface = m.group(1)
                if iface.startswith(("wl", "wlan", "wifi")):
                    return "Wi-Fi (Ulangan)"
                return f"Ulangan ({iface})"
            return "Ulangan"
    except Exception:
        pass

    return "Ulanmagan"


async def get_wifi_name() -> str:
    return await asyncio.to_thread(_sync_get_wifi_name)


def _sync_get_volume_percent() -> str:
    env = get_wayland_env()
    try:
        output = subprocess.check_output(
            ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
            env=env,
            timeout=2,
        ).decode("utf-8", errors="ignore")
        match = re.search(r"(\d+)%", output)
        return f"{match.group(1)}%" if match else "N/A"
    except Exception:
        return "N/A"


async def get_current_volume_percent() -> str:
    return await asyncio.to_thread(_sync_get_volume_percent)


def _sync_is_muted() -> bool:
    env = get_wayland_env()
    try:
        output = subprocess.check_output(
            ["pactl", "get-sink-mute", "@DEFAULT_SINK@"],
            env=env,
            timeout=2,
        ).decode("utf-8", errors="ignore")
        return "yes" in output.lower()
    except Exception:
        return False


async def is_muted() -> bool:
    return await asyncio.to_thread(_sync_is_muted)


def _sync_run_volume_action(arg: str) -> str:
    env = get_wayland_env()
    try:
        if arg == "up":
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+10%"], env=env, timeout=2)
        elif arg == "down":
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-10%"], env=env, timeout=2)
        else:
            subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], env=env, timeout=2)
    except Exception as e:
        logger.error(f"Ovoz o'zgartirishda xato: {e}")

    vol = _sync_get_volume_percent()
    muted = _sync_is_muted()
    text = (
        "🔊 <b>Ovoz Boshqaruvi</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔈 <b>Joriy daraja:</b> <b>{vol}</b>"
    )
    if muted:
        text += " (O'chirilgan 🔇)"
    text += "\n━━━━━━━━━━━━━━━━━━━━━"
    return text


async def run_volume_action(arg: str) -> str:
    return await asyncio.to_thread(_sync_run_volume_action, arg)


def clean_app_name(raw_name: str) -> str:
    """Ilova nomini toza, takrorlanishlarsiz va chiroyli formatga keltiradi."""
    if not raw_name:
        return "Bosh ekran"

    raw_lower = raw_name.lower().strip()

    # Maxsus dasturlar xaritasi
    if "telegram" in raw_lower:
        return "Telegram"
    if "chrome" in raw_lower:
        return "Google Chrome"
    if "firefox" in raw_lower:
        return "Firefox"
    if "pycharm" in raw_lower:
        return "PyCharm"
    if "antigravity" in raw_lower:
        return "Antigravity"
    if "code" in raw_lower or "vscode" in raw_lower:
        return "VS Code"
    if "clion" in raw_lower:
        return "CLion"
    if "idea" in raw_lower or "intellij" in raw_lower:
        return "IntelliJ IDEA"
    if "terminal" in raw_lower or "ptyxis" in raw_lower:
        return "Terminal"
    if "nautilus" in raw_lower or "files" in raw_lower:
        return "Fayllar (Nautilus)"
    if "vlc" in raw_lower:
        return "VLC Player"
    if "spotify" in raw_lower:
        return "Spotify"
    if "obsidian" in raw_lower:
        return "Obsidian"
    if "slack" in raw_lower:
        return "Slack"
    if "discord" in raw_lower:
        return "Discord"
    if "postman" in raw_lower:
        return "Postman"
    if "dbeaver" in raw_lower:
        return "DBeaver"
    if "docker" in raw_lower:
        return "Docker Desktop"
    if "settings" in raw_lower or "control-center" in raw_lower:
        return "Sozlamalar"
    if "system-monitor" in raw_lower:
        return "Tizim Monitori"
    if "writer" in raw_lower:
        return "LibreOffice Writer"
    if "calc" in raw_lower:
        return "LibreOffice Calc"

    # Nuqtali ID larni oxirgi qismini olish (masalan: org.gnome.Calculator -> Calculator)
    if "." in raw_name:
        parts = raw_name.split(".")
        candidate = parts[-1]
        if candidate.lower() not in ("desktop", "exe", "bin", "app"):
            raw_name = candidate

    # So'zlarni tozalash va takrorlanishlarni olib tashlash
    cleaned = raw_name.replace("-", " ").replace("_", " ").strip()
    words = cleaned.split()

    # Agar so'zlar takroriy blok bo'lsa (masalan: ["some", "app", "some", "app"])
    n = len(words)
    if n >= 2 and n % 2 == 0:
        half = n // 2
        if [w.lower() for w in words[:half]] == [w.lower() for w in words[half:]]:
            words = words[:half]

    seen = []
    for w in words:
        if not seen or w.lower() != seen[-1].lower():
            seen.append(w)

    result = " ".join(seen)
    return result.capitalize() if result else "Bosh ekran"


def _sync_get_focused_window_via_extension() -> Optional[str]:
    """GNOME 'Window Calls' extension orqali fokusdagi oynani aniqlaydi."""
    env = get_wayland_env()
    try:
        res = subprocess.check_output(
            [
                "busctl", "--user", "--json=short", "call",
                "org.gnome.Shell",
                "/org/gnome/Shell/Extensions/Windows",
                "org.gnome.Shell.Extensions.Windows",
                "List",
            ],
            env=env,
            timeout=1.5,
        ).decode("utf-8", errors="ignore")

        outer = json.loads(res)
        data_field = outer.get("data")
        inner_str = data_field[0] if isinstance(data_field, list) else data_field
        windows = json.loads(inner_str)

        for w in windows:
            if w.get("focus"):
                raw = w.get("wm_class") or w.get("wm_class_instance") or w.get("title") or ""
                return raw
    except Exception:
        pass
    return None


def _sync_get_active_window_name() -> str:
    """Ayni paytda fokusda turgan (ishlatilayotgan) haqiqiy dasturni aniqlaydi."""
    env = get_wayland_env()

    # 1-usul: GNOME Window Calls extension (Wayland uchun eng aniq)
    try:
        raw = _sync_get_focused_window_via_extension()
        if raw and raw.lower() not in SYSTEM_IGNORE_CLASSES:
            return clean_app_name(raw)
    except Exception:
        pass

    # 2-usul: X11 / XWayland mosligi
    try:
        win_id = subprocess.check_output(["xdotool", "getactivewindow"], env=env, timeout=1).decode().strip()
        if win_id:
            xprop_out = subprocess.check_output(["xprop", "-id", win_id, "WM_CLASS"], env=env, timeout=1).decode()
            m = re.search(r'WM_CLASS\(STRING\) =.*?"(.*?)"', xprop_out)
            if m and m.group(1).lower() not in SYSTEM_IGNORE_CLASSES:
                return clean_app_name(m.group(1))
    except Exception:
        pass

    # 3-usul: psutil orqali foydalanuvchi jarayonlarini qidirish
    try:
        current_uid = os.getuid()
        proc_candidates = []

        for p in psutil.process_iter(['name', 'cmdline', 'uids', 'create_time']):
            try:
                info = p.info
                if not info.get('uids') or info['uids'].real != current_uid:
                    continue

                pname = (info.get('name') or "").lower()
                cmd = " ".join(info.get('cmdline') or []).lower()

                if pname in ("systemd", "gnome-shell", "dbus-daemon", "pulseaudio", "pipewire", "bash", "python3", "python"):
                    continue

                if pname.startswith(("gsd-", "xdg-", "gvfs")):
                    continue

                if "antigravity" in cmd or "antigravity" in pname:
                    return "Antigravity"
                elif "pycharm" in cmd:
                    proc_candidates.append(("PyCharm", info['create_time']))
                elif "code" in pname and "--type=" not in cmd:
                    proc_candidates.append(("VS Code", info['create_time']))
                elif "chrome" in pname and "--type=" not in cmd:
                    proc_candidates.append(("Google Chrome", info['create_time']))
                elif "telegram" in pname:
                    proc_candidates.append(("Telegram", info['create_time']))
                else:
                    proc_candidates.append((clean_app_name(pname), info['create_time']))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if proc_candidates:
            proc_candidates.sort(key=lambda x: x[1], reverse=True)
            return proc_candidates[0][0]
    except Exception:
        pass

    return "Bosh ekran"


async def get_active_window_name() -> str:
    return await asyncio.to_thread(_sync_get_active_window_name)


async def build_status_view() -> Tuple[str, InlineKeyboardMarkup]:
    """Tizim monitoring holati matnini va inline tugmalarni tayyorlaydi."""
    cpu = round(psutil.cpu_percent(interval=None))
    ram = round(psutil.virtual_memory().percent)

    disk = psutil.disk_usage("/")
    free_gb = disk.free / (1024 ** 3)
    disk_percent = round(disk.percent)

    battery = psutil.sensors_battery()
    if battery:
        bat_state = "Zaryadlanmoqda ⚡️" if battery.power_plugged else "Batareyada 🔋"
        bat_text = f"<b>{round(battery.percent)}%</b> <i>({bat_state})</i>"
    else:
        bat_text = "Mavjud emas"

    wifi_name, volume, muted, current_app = await asyncio.gather(
        get_wifi_name(),
        get_current_volume_percent(),
        is_muted(),
        get_active_window_name(),
    )

    volume_text = f"<b>{volume}</b>" + (" <i>(O'chirilgan 🔇)</i>" if muted else "")
    device_name = get_device_name()
    now_str = datetime.now(UZ_TZ).strftime("%H:%M:%S")

    cpu_bar = make_progress_bar(cpu)
    ram_bar = make_progress_bar(ram)

    text = (
        "🖥 <b>TIZIM MONITORINGI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡️ <b>CPU:</b> <code>{cpu_bar}</code> <b>{cpu}%</b>\n"
        f"🧠 <b>RAM:</b> <code>{ram_bar}</code> <b>{ram}%</b>\n"
        f"🔋 <b>Batareya:</b> {bat_text}\n"
        f"💽 <b>Disk:</b> <b>{disk_percent}%</b> band <i>({free_gb:.1f} GB bo'sh)</i>\n"
        f"📶 <b>Tarmoq:</b> <code>{wifi_name}</code>\n"
        f"🔊 <b>Ovoz:</b> {volume_text}\n"
        f"📱 <b>Hozir ochiq:</b> <b>{current_app}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"💻 <i>Qurilma: {device_name}</i>\n"
        f"🕒 <i>Yangilangan: {now_str}</i>"
    )

    return text, status_inline_kb


def build_daily_report_text(stats_dict: Optional[Dict[str, Any]] = None) -> str:
    """Kunlik hisobot matnini generatsiya qiladi."""
    stats = stats_dict or daily_stats
    date_str = stats.get("date", datetime.now(UZ_TZ).strftime("%Y-%m-%d"))
    battery_samples = stats.get("battery_samples", [])

    if battery_samples:
        start_percent = battery_samples[0]["percent"]
        current_percent = battery_samples[-1]["percent"]
        min_percent = min(s["percent"] for s in battery_samples)
        max_percent = max(s["percent"] for s in battery_samples)
    else:
        battery = psutil.sensors_battery()
        cur = round(battery.percent) if battery else 0
        start_percent = current_percent = min_percent = max_percent = cur

    total_minutes = sum(stats.get("app_minutes", {}).values())
    hours = total_minutes // 60
    minutes = total_minutes % 60

    # Ilova nomlarini tozalab, birlashtirish (merge)
    merged_apps = Counter()
    for raw_k, count in stats.get("app_minutes", {}).items():
        cleaned_k = clean_app_name(raw_k)
        if cleaned_k and cleaned_k not in SYSTEM_IGNORE_CLASSES:
            merged_apps[cleaned_k] += count

    top_apps = merged_apps.most_common(8)
    apps_lines = []
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]
    rank = 0
    for name, count in top_apps:
        h = count // 60
        m = count % 60
        time_str = f"{h} soat {m} daqiqa" if h > 0 else f"{m} daqiqa"
        medal = medals[rank] if rank < len(medals) else f"🔹 {rank + 1}."
        apps_lines.append(f"{medal} <b>{name}</b> — {time_str}")
        rank += 1

    apps_text = "\n".join(apps_lines) if apps_lines else "<i>Ilovalar faolligi qayd etilmadi</i>"
    device_name = get_device_name()

    return (
        f"📊 <b>KUNLIK FOYDALANISH HISOBOTI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🗓 <b>Sana:</b> <code>{date_str}</code>\n"
        f"⏱ <b>Umumiy faol vaqt:</b> <b>{hours} soat {minutes} daqiqa</b>\n"
        f"🔋 <b>Batareya dinamikasi:</b> {start_percent}% ➔ {current_percent}% "
        f"<i>(min: {min_percent}%, max: {max_percent}%)</i>\n\n"
        f"📱 <b>Eng ko'p ishlatilgan ilovalar:</b>\n"
        f"{apps_text}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"💻 <i>{device_name} • Avtomatik hisobot</i>"
    )


def _sync_get_clipboard_text() -> Optional[str]:
    env = get_wayland_env()
    try:
        output = subprocess.check_output(["wl-paste", "--no-newline"], env=env, timeout=2).decode("utf-8", errors="ignore")
        return output if output else None
    except Exception:
        return None


async def get_clipboard_text() -> Optional[str]:
    return await asyncio.to_thread(_sync_get_clipboard_text)


def _sync_set_clipboard_text(text: str):
    env = get_wayland_env()
    subprocess.run(["wl-copy", "--", text], env=env, timeout=2, check=True)


async def set_clipboard_text(text: str):
    await asyncio.to_thread(_sync_set_clipboard_text, text)


def _sync_take_photo(output_path: str):
    subprocess.run(
        [
            "fswebcam",
            "-r", "1920x1080",
            "-S", "25",
            "--jpeg", "95",
            "--no-banner",
            output_path,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=10,
        check=True,
    )


async def take_photo(output_path: str):
    await asyncio.to_thread(_sync_take_photo, output_path)



def _sync_lock_screen():
    env = get_wayland_env()
    try:
        subprocess.run(
            [
                "gdbus", "call", "--session",
                "--dest", "org.gnome.ScreenSaver",
                "--object-path", "/org/gnome/ScreenSaver",
                "--method", "org.gnome.ScreenSaver.Lock",
            ],
            env=env,
            timeout=2,
            check=True,
        )
    except Exception:
        subprocess.run(["loginctl", "lock-session"], timeout=2)


async def lock_screen():
    await asyncio.to_thread(_sync_lock_screen)


def _sync_send_notification(text: str):
    env = get_wayland_env()
    subprocess.run(["notify-send", "-u", "critical", "--", "Telegram Xabari", text], env=env, timeout=3, check=True)


async def send_desktop_notification(text: str):
    await asyncio.to_thread(_sync_send_notification, text)



def _sync_open_spotify() -> bool:
    env = get_wayland_env()
    logger.info("Spotify ishga tushirilmoqda...")
    # 1. Native app, snap yoki flatpak
    for cmd in (["spotify"], ["snap", "run", "spotify"], ["flatpak", "run", "com.spotify.Client"], ["gtk-launch", "spotify"]):
        try:
            subprocess.Popen(cmd, env=env)
            logger.info(f"Spotify dasturi ishga tushirildi ({cmd[0]}).")
            return True
        except Exception:
            pass

    # 2. Spotify Web Player fallback
    web_url = "https://open.spotify.com"
    for cmd in (["gio", "open", web_url], ["google-chrome", web_url], ["firefox", web_url], ["xdg-open", web_url]):
        try:
            subprocess.Popen(cmd, env=env)
            logger.info(f"Spotify Web Player ochildi ({cmd[0]}).")
            return True
        except Exception:
            pass

    return False


async def open_spotify() -> bool:
    return await asyncio.to_thread(_sync_open_spotify)


def _sync_get_music_info() -> Dict[str, str]:
    env = get_wayland_env()
    info = {"title": "", "artist": "", "album": "", "status": "To'xtatilgan ⏸", "player": "Spotify", "art_url": ""}

    # 1. playerctl
    try:
        out = subprocess.check_output(
            ["playerctl", "metadata", "--format", "{{title}};;;{{artist}};;;{{album}};;;{{status}};;;{{playerName}};;;{{mpris:artUrl}}"],
            env=env,
            timeout=2,
        ).decode("utf-8", errors="ignore").strip()
        if out:
            parts = out.split(";;;")
            if len(parts) >= 5:
                info["title"] = parts[0].strip()
                info["artist"] = parts[1].strip()
                info["album"] = parts[2].strip() if len(parts) > 2 else ""
                info["status"] = "Ijro etilmoqda 🟢" if parts[3].lower() == "playing" else "Pauzada ⏸"
                info["player"] = clean_app_name(parts[4])
                info["art_url"] = parts[5].strip() if len(parts) > 5 else ""
                return info
    except Exception:
        pass

    # 2. dbus-send / gdbus ListNames
    players = []
    try:
        out = subprocess.check_output(
            ["dbus-send", "--session", "--type=method_call", "--print-reply",
             "--dest=org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus.ListNames"],
            env=env,
            timeout=2
        ).decode("utf-8", errors="ignore")
        players = re.findall(r'string "(org\.mpris\.MediaPlayer2\.[^"]+)"', out)
    except Exception:
        pass

    if not players:
        try:
            out = subprocess.check_output(
                ["gdbus", "call", "--session", "--dest", "org.freedesktop.DBus",
                 "--object-path", "/org/freedesktop/DBus", "--method", "org.freedesktop.DBus.ListNames"],
                env=env,
                timeout=2
            ).decode("utf-8", errors="ignore")
            players = re.findall(r"'(org\.mpris\.MediaPlayer2\.[^']+)'", out)
        except Exception:
            pass

    if not players:
        players = ["org.mpris.MediaPlayer2.spotify"]

    spotify_first = sorted(players, key=lambda x: 0 if "spotify" in x.lower() else 1)

    for target in spotify_first:
        player_raw = target.split("org.mpris.MediaPlayer2.")[-1]
        info["player"] = clean_app_name(player_raw)

        # Metadata via dbus-send
        try:
            meta_rep = subprocess.check_output(
                [
                    "dbus-send", "--session", "--type=method_call", "--print-reply",
                    f"--dest={target}",
                    "/org/mpris/MediaPlayer2",
                    "org.freedesktop.DBus.Properties.Get",
                    "string:org.mpris.MediaPlayer2.Player",
                    "string:Metadata"
                ],
                env=env,
                timeout=2
            ).decode("utf-8", errors="ignore")

            title_m = re.search(r'string "xesam:title"\s+variant\s+string "([^"]+)"', meta_rep)
            if title_m:
                info["title"] = title_m.group(1).strip()

            album_m = re.search(r'string "xesam:album"\s+variant\s+string "([^"]+)"', meta_rep)
            if album_m:
                info["album"] = album_m.group(1).strip()

            artists_block = re.findall(r'string "xesam:artist".*?array \[(.*?)\]', meta_rep, re.DOTALL)
            if artists_block:
                artists = re.findall(r'string "([^"]+)"', artists_block[0])
                info["artist"] = ", ".join(artists)

        except Exception:
            pass

        # PlaybackStatus via dbus-send
        try:
            status_rep = subprocess.check_output(
                [
                    "dbus-send", "--session", "--type=method_call", "--print-reply",
                    f"--dest={target}",
                    "/org/mpris/MediaPlayer2",
                    "org.freedesktop.DBus.Properties.Get",
                    "string:org.mpris.MediaPlayer2.Player",
                    "string:PlaybackStatus"
                ],
                env=env,
                timeout=1.5
            ).decode("utf-8", errors="ignore")
            if 'string "Playing"' in status_rep:
                info["status"] = "Ijro etilmoqda 🟢"
            elif 'string "Paused"' in status_rep:
                info["status"] = "Pauzada ⏸"
        except Exception:
            pass

        if info["title"]:
            return info

    return info


async def get_music_info() -> Dict[str, str]:
    return await asyncio.to_thread(_sync_get_music_info)


def _sync_media_control(action: str) -> str:
    env = get_wayland_env()
    logger.info(f"Media boshqaruv buyrug'i: {action}")

    method_map = {
        "play_pause": "PlayPause",
        "next": "Next",
        "prev": "Previous",
    }
    method = method_map.get(action, "PlayPause")

    # 1. dbus-send to spotify directly
    try:
        subprocess.run(
            [
                "dbus-send", "--session", "--type=method_call",
                "--dest=org.mpris.MediaPlayer2.spotify",
                "/org/mpris/MediaPlayer2",
                f"org.mpris.MediaPlayer2.Player.{method}"
            ],
            env=env,
            timeout=2,
            check=True
        )
        logger.info(f"Spotify'ga dbus-send muvaffaqiyatli yuborildi ({method})")
        return f"✅ Spotify: {method} bajarildi"
    except Exception:
        pass

    # 2. playerctl
    try:
        if action == "play_pause":
            subprocess.run(["playerctl", "play-pause"], env=env, timeout=2, check=True)
            return "⏯ Ijro holati o'zgartirildi"
        elif action == "next":
            subprocess.run(["playerctl", "next"], env=env, timeout=2, check=True)
            return "⏭ Keyingi trekka o'tkazildi"
        elif action == "prev":
            subprocess.run(["playerctl", "previous"], env=env, timeout=2, check=True)
            return "⏮ Oldingi trekka o'tkazildi"
    except Exception:
        pass

    # 3. Dynamic MPRIS players
    players = []
    try:
        out = subprocess.check_output(
            ["dbus-send", "--session", "--type=method_call", "--print-reply",
             "--dest=org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus.ListNames"],
            env=env,
            timeout=2
        ).decode("utf-8", errors="ignore")
        players = re.findall(r'string "(org\.mpris\.MediaPlayer2\.[^"]+)"', out)
    except Exception:
        pass

    for target in players:
        try:
            subprocess.run(
                [
                    "dbus-send", "--session", "--type=method_call",
                    f"--dest={target}",
                    "/org/mpris/MediaPlayer2",
                    f"org.mpris.MediaPlayer2.Player.{method}"
                ],
                env=env,
                timeout=2,
                check=True
            )
            logger.info(f"{target} ga {method} muvaffaqiyatli yuborildi")
            return f"✅ {clean_app_name(target.split('.')[-1])}: {method} bajarildi"
        except Exception:
            pass

    # 4. xdotool media keys
    try:
        key_map = {
            "play_pause": "XF86AudioPlay",
            "next": "XF86AudioNext",
            "prev": "XF86AudioPrev",
        }
        if action in key_map:
            subprocess.run(["xdotool", "key", key_map[action]], env=env, timeout=2, check=True)
            return "✅ Media tugmasi bosildi"
    except Exception as e:
        logger.warning(f"xdotool media xatosi: {e}")

    return "⚠️ Noutbukda Spotify yoki faol musiqa pleyeri topilmadi."


async def run_media_control(action: str) -> str:
    return await asyncio.to_thread(_sync_media_control, action)


async def build_music_view() -> Tuple[str, InlineKeyboardMarkup]:
    """Spotify va musiqa boshqaruvi matnini shakllantiradi."""
    info = await get_music_info()
    title = info.get("title")
    artist = info.get("artist")
    album = info.get("album")
    status = info.get("status", "To'xtatilgan ⏸")
    player = info.get("player", "")

    is_spotify = "spotify" in player.lower()
    header_title = "🟢 <b>SPOTIFY BOSHQARUVI</b>" if is_spotify else "🎵 <b>MUSIQA BOSHQARUVI</b>"

    if title or (player and player not in ("Bosh ekran", "")):
        meta_lines = []
        if title:
            meta_lines.append(f"🎧 <b>Trek:</b> <b>{title}</b>")
        if artist:
            meta_lines.append(f"👤 <b>Ijrochi:</b> <b>{artist}</b>")
        if album:
            meta_lines.append(f"💿 <b>Albom:</b> {album}")
        meta_lines.append(f"📊 <b>Holat:</b> {status}")
        if player:
            meta_lines.append(f"💻 <b>Pleyer:</b> {player}")
        meta_text = "\n".join(meta_lines)
    else:
        meta_text = (
            "🎧 <b>Ayni paytda faol musiqa ijro etilmayapti.</b>\n\n"
            "💡 <i>Noutbukingizda <b>Spotify</b> yoki veb-pleyerini ishga tushirish uchun quyidagi tugmani bosing:</i>"
        )

    text = (
        f"{header_title}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"{meta_text}\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )
    return text, music_inline_kb


# ==============================================================================
# 7. XAVFSIZLIK FILTRI VA MIDDLEWARE
# ==============================================================================

@dp.message(F.from_user.id != ADMIN_ID)
async def unauthorized_message(message: types.Message):
    user = message.from_user
    logger.warning(f"Ruxsatsiz xabar urinishi! ID: {user.id}, Ism: {user.full_name}, Username: @{user.username}")
    await message.reply("⛔️ Kechirasiz, siz ushbu noutbuk boshqaruvchisi emassiz!")


@dp.callback_query(F.from_user.id != ADMIN_ID)
async def unauthorized_callback(callback: CallbackQuery):
    logger.warning(f"Ruxsatsiz callback urinishi! ID: {callback.from_user.id}")
    await callback.answer("⛔️ Ruxsat berilmagan!", show_alert=True)


# ==============================================================================
# 8. HANDLERS VA BUYRUQLAR
# ==============================================================================

@dp.message(Command("start", "help"))
async def cmd_start(message: types.Message):
    device_name = get_device_name()
    logger.info("Admin /start buyrug'ini yubordi.")
    await message.answer(
        "🤖 <b>Masofaviy Boshqaruv Markazi</b>\n"
        f"💻 <b>Qurilma:</b> <code>{device_name}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Noutbukingizni nazorat qilish va buyruqlar berish uchun quyidagi menyudan foydalaning 👇",
        parse_mode="HTML",
        reply_markup=main_menu,
    )


@dp.message(Command("status"))
@dp.message(F.text == "📊 Holat")
async def cmd_status(message: types.Message):
    status_text, kb = await build_status_view()
    await message.answer(status_text, parse_mode="HTML", reply_markup=kb)


@dp.callback_query(F.data == "status_refresh")
async def callback_status_refresh(callback: CallbackQuery):
    try:
        status_text, kb = await build_status_view()
        await callback.message.edit_text(status_text, parse_mode="HTML", reply_markup=kb)
        await callback.answer("✅ Yangilandi")
    except Exception:
        await callback.answer("Ma'lumotlar yangilandi")


@dp.message(Command("report"))
@dp.message(F.text == "📅 Kunlik hisobot")
async def cmd_report(message: types.Message):
    report_text = build_daily_report_text()
    await message.answer(report_text, parse_mode="HTML")


async def handle_photo_capture(target_chat_id: int):
    now_str = datetime.now(UZ_TZ).strftime("%H:%M:%S")
    cam_file = f"/tmp/cam_shot_{int(datetime.now().timestamp())}.jpg"
    try:
        await take_photo(cam_file)
        photo = FSInputFile(cam_file)
        await bot.send_photo(chat_id=target_chat_id, photo=photo, caption=f"📸 <b>Veb-kamera surati</b> • <i>{now_str}</i>", parse_mode="HTML")
        logger.info("Kamera surati yuborildi.")
    except Exception as e:
        logger.error(f"Kamera xatosi: {e}")
        await bot.send_message(chat_id=target_chat_id, text=f"❌ Kamera xatoligi: {e}")
    finally:
        if os.path.exists(cam_file):
            try:
                os.remove(cam_file)
            except Exception:
                pass


@dp.message(Command("photo"))
@dp.message(F.text == "📸 Kamera")
async def cmd_photo(message: types.Message):
    msg = await message.answer("📸 Surat olinmoqda, kuting...")
    await handle_photo_capture(message.chat.id)
    try:
        await msg.delete()
    except Exception:
        pass


@dp.callback_query(F.data == "quick_photo")
async def callback_quick_photo(callback: CallbackQuery):
    await callback.answer("📸 Surat olinmoqda...")
    await handle_photo_capture(callback.message.chat.id)


@dp.message(Command("music", "spotify"))
@dp.message(F.text.in_({"🎵 Spotify", "Spotify", "🎵 Musiqa", "🎵 Musiqa (Spotify)", "Musiqa", "/music", "/spotify"}))
async def cmd_music(message: types.Message):
    logger.info(f"Admin Musiqa/Spotify bo'limiga kirdi. (Xabar: '{message.text}')")
    try:
        text, kb = await build_music_view()
        await message.answer(text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        logger.error(f"cmd_music xatosi: {e}")
        await message.answer("🎵 <b>Spotify Boshqaruvi</b>\n\nQuyidagi tugmalardan foydalaning 👇", parse_mode="HTML", reply_markup=music_inline_kb)


@dp.callback_query(F.data == "quick_music")
async def callback_quick_music(callback: CallbackQuery):
    text, kb = await build_music_view()
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data == "mus_open_spotify")
async def callback_mus_open_spotify(callback: CallbackQuery):
    success = await open_spotify()
    if success:
        await callback.answer("🟢 Noutbukda Spotify ochildi!", show_alert=True)
    else:
        await callback.answer("❌ Spotify ilovasini ochib bo'lmadi.", show_alert=True)




@dp.callback_query(F.data == "mus_refresh")
async def callback_mus_refresh(callback: CallbackQuery):
    try:
        text, kb = await build_music_view()
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await callback.answer("✅ Yangilandi")
    except Exception:
        await callback.answer("Ma'lumotlar yangilandi")


@dp.callback_query(F.data.in_({"mus_play_pause", "mus_next", "mus_prev"}))
async def callback_mus_controls(callback: CallbackQuery):
    action_map = {
        "mus_play_pause": "play_pause",
        "mus_next": "next",
        "mus_prev": "prev",
    }
    action = action_map[callback.data]
    msg = await run_media_control(action)
    await callback.answer(msg)
    await asyncio.sleep(0.5)
    try:
        text, kb = await build_music_view()
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass




@dp.message(Command("lock"))
@dp.message(F.text == "🔒 Qulflash")
async def cmd_lock(message: types.Message):
    try:
        await lock_screen()
        await message.answer("🔒 <b>Ekran muvaffaqiyatli qulflandi!</b>", parse_mode="HTML")
        logger.info("Ekran masofadan qulflandi.")
    except Exception as e:
        logger.error(f"Qulflashda xato: {e}")
        await message.answer(f"❌ Qulflashda xatolik yuz berdi: {e}")


@dp.message(F.text == "🔔 Xabar yuborish")
async def notify_button(message: types.Message, state: FSMContext):
    await state.set_state(NotifyState.waiting_text)
    await message.answer("✍️ Noutbuk ekranida ko'rsatiladigan xabarni yozing:")


@dp.message(NotifyState.waiting_text)
async def notify_receive_text(message: types.Message, state: FSMContext):
    text = message.text
    await state.clear()
    try:
        await send_desktop_notification(text)
        await message.answer("🔔 <b>Xabar noutbuk ekranida ko'rsatildi!</b>", parse_mode="HTML", reply_markup=main_menu)
        logger.info(f"Ekranga xabar chiqarildi: {text[:40]}")
    except Exception as e:
        logger.error(f"Ekranga xabar chiqarishda xato: {e}")
        await message.answer(f"❌ Xatolik: {e}", reply_markup=main_menu)


@dp.message(F.text == "🔊 Ovoz")
async def volume_button(message: types.Message):
    vol = await get_current_volume_percent()
    muted = await is_muted()
    text = (
        "🔊 <b>Ovoz Boshqaruvi</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔈 <b>Joriy daraja:</b> <b>{vol}</b>"
    )
    if muted:
        text += " (O'chirilgan 🔇)"
    text += "\n━━━━━━━━━━━━━━━━━━━━━"
    await message.answer(text, parse_mode="HTML", reply_markup=volume_kb)


@dp.callback_query(F.data.in_({"vol_up", "vol_down", "vol_mute"}))
async def volume_callback(callback: CallbackQuery):
    action_map = {"vol_up": "up", "vol_down": "down", "vol_mute": "mute"}
    arg = action_map[callback.data]
    try:
        result_text = await run_volume_action(arg)
        await callback.message.edit_text(result_text, parse_mode="HTML", reply_markup=volume_kb)
    except Exception as e:
        logger.error(f"Ovoz callback xatosi: {e}")
        await callback.message.edit_text(f"❌ Xatolik: {e}", reply_markup=volume_kb)
    await callback.answer()


@dp.message(F.text == "📋 Clipboard")
async def clipboard_button(message: types.Message):
    await message.answer(
        "📋 <b>Clipboard (Vaqtinchalik xotira)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Quyidagi amallardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=clipboard_kb,
    )


@dp.callback_query(F.data == "clip_get")
async def clipboard_get_callback(callback: CallbackQuery):
    await callback.answer()
    text = await get_clipboard_text()
    if text:
        if len(text) > 3800:
            text = text[:3800] + "\n... (qolgan qismi qisqartirildi)"
        await callback.message.answer(f"📥 <b>Nusxalangan matn:</b>\n\n<code>{text}</code>", parse_mode="HTML")
    else:
        await callback.message.answer("📋 Clipboard bo'sh yoki matn topilmadi.")


@dp.callback_query(F.data == "clip_set")
async def clipboard_set_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ClipboardState.waiting_text)
    await callback.message.answer("✍️ Noutbuk xotirasiga (clipboard) yoziladigan matnni yuboring:")


@dp.message(ClipboardState.waiting_text)
async def clipboard_receive_text(message: types.Message, state: FSMContext):
    text = message.text
    await state.clear()
    try:
        await set_clipboard_text(text)
        await message.answer("✅ <b>Matn noutbuk clipboard'iga nusxalandi!</b>", parse_mode="HTML", reply_markup=main_menu)
        logger.info("Clipboard'ga yangi matn saqlandi.")
    except Exception as e:
        logger.error(f"Clipboard yozish xatosi: {e}")
        await message.answer(f"❌ Xatolik: {e}", reply_markup=main_menu)


@dp.message(Command("reboot"))
@dp.message(F.text == "🔄 Qayta yoqish")
async def cmd_reboot(message: types.Message):
    await message.answer(
        "⚠️ Noutbukni <b>qayta ishga tushirishni</b> tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=confirm_kb("reboot"),
    )


@dp.message(Command("shutdown"))
@dp.message(F.text == "🛑 O'chirish")
async def cmd_shutdown(message: types.Message):
    await message.answer(
        "⚠️ Noutbukni <b>butunlay o'chirishni</b> tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=confirm_kb("shutdown"),
    )


@dp.callback_query(F.data == "confirm_reboot")
async def confirm_reboot(callback: CallbackQuery):
    await callback.message.edit_text("🔄 <b>Noutbuk qayta ishga tushirilmoqda...</b>", parse_mode="HTML")
    await callback.answer()
    logger.info("Masofadan reboot buyrug'i berildi.")
    save_daily_stats()
    await asyncio.sleep(1)
    subprocess.Popen(["systemctl", "reboot"])


@dp.callback_query(F.data == "confirm_shutdown")
async def confirm_shutdown(callback: CallbackQuery):
    await callback.message.edit_text("🛑 <b>Noutbuk o'chirilmoqda...</b>", parse_mode="HTML")
    await callback.answer()
    logger.info("Masofadan shutdown buyrug'i berildi.")
    save_daily_stats()
    await asyncio.sleep(1)
    subprocess.Popen(["systemctl", "poweroff"])


@dp.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery):
    await callback.message.edit_text("❌ Amal bekor qilindi.")
    await callback.answer()


@dp.message()
async def fallback_unknown_message(message: types.Message):
    logger.info(f"Admin noma'lum xabar yubordi: '{message.text}'")
    await message.answer(
        "🤖 Quyidagi menyudan buyruqni tanlang:",
        reply_markup=main_menu,
    )


# ==============================================================================
# 9. FONDA KUZATUV VA HISOBOTLARNI BOSHQARISH
# ==============================================================================

async def app_tracker_loop():
    """Fonda har daqiqada faol dastur va batareyani kuzatib boradi."""
    global low_battery_notified
    logger.info("Application tracker fon jarayoni ishga tushdi.")

    while True:
        try:
            today_str = datetime.now(UZ_TZ).strftime("%Y-%m-%d")

            # Sana o'zgargan bo'lsa (yangi kun boshlangan yoki sleep'dan uyg'ongan)
            if daily_stats.get("date") != today_str:
                prev_date = daily_stats.get("date")
                if not daily_stats.get("report_sent", False) and sum(daily_stats.get("app_minutes", {}).values()) > 0:
                    try:
                        logger.info(f"O'tkazib yuborilgan hisobot yuborilmoqda: {prev_date}")
                        missed_report = f"⚠️ <b>Kechiktirilgan kunlik hisobot</b>\n" + build_daily_report_text(daily_stats)
                        await bot.send_message(chat_id=ADMIN_ID, text=missed_report, parse_mode="HTML")
                    except Exception as e:
                        logger.error(f"Kechiktirilgan hisobotni yuborishda xato: {e}")

                reset_daily_stats(today_str)

            # Batareya holati
            battery = psutil.sensors_battery()
            if battery:
                pct = round(battery.percent)
                daily_stats["battery_samples"].append({
                    "time": datetime.now(UZ_TZ).strftime("%H:%M"),
                    "percent": pct,
                    "plugged": battery.power_plugged,
                })

                # Past batareya ogohlantirishi
                if pct <= LOW_BATTERY_THRESHOLD and not battery.power_plugged:
                    if not low_battery_notified:
                        try:
                            await bot.send_message(
                                chat_id=ADMIN_ID,
                                text=(
                                    "⚠️ <b>DIQQAT: Batareya quvvati kam!</b>\n"
                                    "━━━━━━━━━━━━━━━━━━━━━\n"
                                    f"🔋 Joriy quvvat: <b>{pct}%</b>\n"
                                    "Iltimos, qurilmangizni zaryadlashga ulang."
                                ),
                                parse_mode="HTML",
                            )
                            low_battery_notified = True
                            logger.warning(f"Past batareya ogohlantirishi yuborildi ({pct}%).")
                        except Exception as e:
                            logger.error(f"Batareya ogohlantirishini yuborishda xato: {e}")
                elif battery.power_plugged:
                    low_battery_notified = False

            # Faol dasturni hisoblash
            current_app = await get_active_window_name()
            if current_app and current_app not in SYSTEM_IGNORE_CLASSES:
                daily_stats["app_minutes"][current_app] += 1

            # Har daqiqada xotirani saqlash
            save_daily_stats()

        except Exception as e:
            logger.error(f"Tracker xatoligi: {e}")

        await asyncio.sleep(TRACK_INTERVAL_SECONDS)


async def daily_report_scheduler():
    """Belgilangan vaqtda (masalan, 23:55) kunlik hisobotni jo'natadi."""
    logger.info("Daily report scheduler ishga tushdi.")
    while True:
        try:
            now = datetime.now(UZ_TZ)
            is_report_time = (now.hour == DAILY_REPORT_HOUR and now.minute >= DAILY_REPORT_MINUTE)
            
            if is_report_time and not daily_stats.get("report_sent", False):
                report_text = build_daily_report_text()
                await bot.send_message(chat_id=ADMIN_ID, text=report_text, parse_mode="HTML")
                daily_stats["report_sent"] = True
                save_daily_stats()
                logger.info(f"Kunlik hisobot administratorga yuborildi ({now.strftime('%Y-%m-%d')}).")
        except Exception as e:
            logger.error(f"Kunlik hisobot scheduler xatosi: {e}")

        await asyncio.sleep(30)


# ==============================================================================
# 10. ISHGA TUSHISH BILDIRISHNOMASI VA ASOSIY LOOP
# ==============================================================================

async def on_startup_notify():
    """Bot ishga tushganda administratorga xabar beradi."""
    boot_time = datetime.now(UZ_TZ).strftime("%Y-%m-%d %H:%M:%S")
    battery = psutil.sensors_battery()
    bat_text = f"{round(battery.percent)}%" if battery else "Aniqlanmadi"
    wifi_name = await get_wifi_name()
    device_name = get_device_name()

    text = (
        "🟢 <b>Qurilma Muvaffaqiyatli Yondi!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"💻 <b>Qurilma:</b> <code>{device_name}</code>\n"
        f"🔋 <b>Batareya:</b> <b>{bat_text}</b>\n"
        f"📶 <b>Tarmoq:</b> <code>{wifi_name}</code>\n"
        f"🕒 <b>Vaqt:</b> {boot_time}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Boshqaruv uchun quyidagi menyudan foydalaning 👇</i>"
    )
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode="HTML", reply_markup=main_menu)
        logger.info("Startup notification yuborildi.")
    except Exception as e:
        logger.error(f"Startup xabarini yuborishda xatolik: {e}")


async def main():
    device_name = get_device_name()
    logger.info(f"Remote Bot ishga tushmoqda... Qurilma: {device_name}")
    logger.info(f"ADMIN_ID: {ADMIN_ID}, TIMEZONE: {TIMEZONE_STR}")

    load_daily_stats()
    await on_startup_notify()

    asyncio.create_task(app_tracker_loop())
    asyncio.create_task(daily_report_scheduler())

    try:
        await dp.start_polling(bot, drop_pending_updates=True)
    finally:
        save_daily_stats()
        await bot.session.close()
        logger.info("Bot faoliyati to'xtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot qo'lda to'xtatildi.")
