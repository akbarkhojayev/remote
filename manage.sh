#!/usr/bin/env bash
# ==============================================================================
# Remote Bot — Boshqaruv va Monitoring Utility
# ==============================================================================

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

ACTION="${1:-help}"

case "$ACTION" in
    start)
        echo -e "${YELLOW}Bot ishga tushirilmoqda...${NC}"
        systemctl --user start remote-bot.service
        echo -e "${GREEN}✓ Bot muvaffaqiyatli ishga tushirildi.${NC}"
        ;;
    stop)
        echo -e "${YELLOW}Bot to'xtatilmoqda...${NC}"
        systemctl --user stop remote-bot.service
        echo -e "${GREEN}✓ Bot to'xtatildi.${NC}"
        ;;
    restart)
        echo -e "${YELLOW}Bot qayta yuklanmoqda...${NC}"
        systemctl --user restart remote-bot.service
        echo -e "${GREEN}✓ Bot qayta ishga tushirildi.${NC}"
        ;;
    status)
        echo -e "${BLUE}=== Bot Xizmati Holati ===${NC}"
        systemctl --user status remote-bot.service --no-pager
        ;;
    logs)
        echo -e "${BLUE}=== Jonli Loglar (Chiqish uchun Ctrl+C bosing) ===${NC}"
        if [ -f "remote_bot.log" ]; then
            tail -n 30 -f remote_bot.log
        else
            journalctl --user -u remote-bot.service -n 50 -f
        fi
        ;;
    test)
        echo -e "${YELLOW}Bot to'g'ridan-to'g'ri terminalda sinov uchun ishga tushirilmoqda...${NC}"
        echo -e "${BLUE}(To'xtatish uchun Ctrl+C bosing)${NC}\n"
        ./venv/bin/python bot.py
        ;;
    *)
        echo -e "${BLUE}=====================================================${NC}"
        echo -e "${BLUE}   🤖 Remote Bot Boshqaruv Utility                 ${NC}"
        echo -e "${BLUE}=====================================================${NC}"
        echo -e "\nFoydalanish: ${YELLOW}./manage.sh [buyruq]${NC}\n"
        echo -e "Buyruqlar:"
        echo -e "  ${GREEN}status${NC}   — Bot xizmati holatini ko'rish"
        echo -e "  ${GREEN}logs${NC}     — Jonli loglarni kuzatish (live)"
        echo -e "  ${GREEN}restart${NC}  — Botni qayta ishga tushirish"
        echo -e "  ${GREEN}start${NC}    — Botni ishga tushirish"
        echo -e "  ${GREEN}stop${NC}     — Botni to'xtatish"
        echo -e "  ${GREEN}test${NC}     — Botni terminalda to'g'ridan-to'g'ri sinab ko'rish"
        echo -e ""
        ;;
esac
