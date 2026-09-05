#!/usr/bin/env bash
# ==============================================================================
# Remote Bot — O'chirish (Uninstall) Skripti
# ==============================================================================

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}Remote Bot xizmati to'xtatilmoqda va o'chirilmoqda...${NC}"

systemctl --user stop remote-bot.service 2>/dev/null || true
systemctl --user disable remote-bot.service 2>/dev/null || true

SERVICE_FILE="$HOME/.config/systemd/user/remote-bot.service"
if [ -f "$SERVICE_FILE" ]; then
    rm -f "$SERVICE_FILE"
    systemctl --user daemon-reload
    echo -e "${GREEN}✓ Systemd xizmat fayli o'chirildi.${NC}"
fi

echo -e "\n${GREEN}✓ Remote Bot xizmati muvaffaqiyatli to'xtatildi va tizimdan olib tashlandi.${NC}"
echo -e "Loyiha papkasini o'chirish uchun: ${BLUE}rm -rf $(pwd)${NC}\n"
