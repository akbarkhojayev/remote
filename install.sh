#!/usr/bin/env bash
# ==============================================================================
# Remote Bot — Linux Avtomatik O'rnatish va Sozlash Skripti
# ==============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo -e "${BLUE}=====================================================${NC}"
echo -e "${BLUE}   🚀 Remote Bot — Linux Avtomatik O'rnatuvchi      ${NC}"
echo -e "${BLUE}=====================================================${NC}\n"

# 1. Tizim paketlarini tekshirish va o'rnatish
echo -e "${YELLOW}[1/5] Tizim paketlari tekshirilmoqda...${NC}"

if command -v apt-get &>/dev/null; then
    echo -e "APT paket menejeri aniqlandi. Kerakli paketlar o'rnatilmoqda..."
    sudo apt-get update -qq || true
    sudo apt-get install -y -qq python3 python3-venv python3-pip fswebcam wl-clipboard libnotify-bin pulseaudio-utils || true
elif command -v dnf &>/dev/null; then
    echo -e "DNF paket menejeri aniqlandi..."
    sudo dnf install -y python3 python3-pip fswebcam wl-clipboard libnotify pulseaudio-utils || true
elif command -v pacman &>/dev/null; then
    echo -e "Pacman paket menejeri aniqlandi..."
    sudo pacman -Sy --noconfirm python python-pip fswebcam wl-clipboard libnotify libpulse || true
else
    echo -e "${YELLOW}Paket menejeri aniqlanmadi. Kerakli vositalar o'rnatilgan deb hisoblanadi.${NC}"
fi

# 2. Python Virtual Muhiti (venv)
echo -e "\n${YELLOW}[2/5] Python virtual muhiti (venv) sozlanmoqda...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual muhit yaratildi.${NC}"
else
    echo -e "${GREEN}✓ Virtual muhit allaqachon mavjud.${NC}"
fi

# Paketlarni o'rnatish
echo -e "Python kutubxonalari o'rnatilmoqda..."
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q
echo -e "${GREEN}✓ Barcha Python kutubxonalari muvaffaqiyatli o'rnatildi.${NC}"

# 3. .env Konfiguratsiya fayli
echo -e "\n${YELLOW}[3/5] Konfiguratsiya (.env) tekshirilmoqda...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${YELLOW}.env fayli yaratildi.${NC}"
    
    echo -e "\n${BLUE}Iltimos, bot ma'lumotlarini kiriting:${NC}"
    read -rp "1. Telegram Bot Token (@BotFather): " user_token
    read -rp "2. Admin Telegram ID (@userinfobot): " user_admin_id
    
    if [ -n "$user_token" ]; then
        sed -i "s|^BOT_TOKEN=.*|BOT_TOKEN=$user_token|" .env
    fi
    if [ -n "$user_admin_id" ]; then
        sed -i "s|^ADMIN_ID=.*|ADMIN_ID=$user_admin_id|" .env
    fi
    echo -e "${GREEN}✓ Sozlamalar .env fayliga saqlandi.${NC}"
else
    echo -e "${GREEN}✓ .env fayli mavjud.${NC}"
fi

# 4. Systemd User Service sozlash
echo -e "\n${YELLOW}[4/5] Avtostart (Systemd Service) sozlanmoqda...${NC}"
SYSTEMD_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_DIR"

cat << EOF > "$SYSTEMD_DIR/remote-bot.service"
[Unit]
Description=Telegram Remote Control Bot (User Service)
PartOf=graphical-session.target
After=graphical-session.target network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$DIR
ExecStart=$DIR/venv/bin/python $DIR/bot.py
Restart=always
RestartSec=5
Environment=DISPLAY=:0
Environment=WAYLAND_DISPLAY=wayland-0
Environment=XDG_CURRENT_DESKTOP=ubuntu:GNOME

[Install]
WantedBy=default.target
EOF

# 5. Xizmatni yoqish va ishga tushirish
echo -e "\n${YELLOW}[5/5] Xizmat ishga tushirilmoqda...${NC}"
systemctl --user daemon-reload || true
systemctl --user enable remote-bot.service || true
systemctl --user restart remote-bot.service || true

chmod +x install.sh manage.sh uninstall.sh 2>/dev/null || true

echo -e "\n${GREEN}=====================================================${NC}"
echo -e "${GREEN}   🎉 O'RNATISH MUVAFFAQIYATLI YAKUNLANDI!          ${NC}"
echo -e "${GREEN}=====================================================${NC}"
echo -e "\nBot hozir fonda ishlayapti va har doim noutbuk yonganda avtomatik ishga tushadi."
echo -e "\nBoshqaruv uchun qulay buyruqlar:"
echo -e "  ${BLUE}./manage.sh status${NC}   — Bot holatini ko'rish"
echo -e "  ${BLUE}./manage.sh logs${NC}     — Jonli loglarni kuzatish"
echo -e "  ${BLUE}./manage.sh restart${NC}  — Botni qayta ishga tushirish"
echo -e "  ${BLUE}./manage.sh stop${NC}     — Botni to'xtatish\n"
