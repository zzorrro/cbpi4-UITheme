#!/usr/bin/env bash
# Установщик плагина cbpi4-UITheme (цвета и шрифты интерфейса CraftBeerPi4).
# Запуск (имя пользователя Pi не важно):
#   curl -fsSL https://raw.githubusercontent.com/zzorrro/cbpi4-UITheme/main/install.sh | sudo bash
# Удаление плагина:  sudo bash install.sh remove   (или: sudo pip3 uninstall cbpi4-UITheme)
#
# Необязательные переменные окружения:
#   CBPI_PYTHON=/путь/к/python   Python, в котором установлен CraftBeerPi4 (если не найден автоматически)
#   NO_RESTART=1                  не перезапускать службу craftbeerpi
#   PLUGIN_SRC=...                откуда ставить плагин (по умолчанию архив с GitHub)
set -e
PLUGIN_SRC="${PLUGIN_SRC:-https://github.com/zzorrro/cbpi4-UITheme/archive/refs/heads/main.tar.gz}"
ACTION="${1:-install}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Нужны права root. Запустите через sudo."
  exit 1
fi

# --- ищем Python, в котором установлен CraftBeerPi4 ---
PYS=""
SEEN=""
add_py() {  # добавляет Python, если в нём есть cbpi и это окружение ещё не встречалось
  [ -x "$1" ] && "$1" -c "import cbpi" 2>/dev/null || return 0
  local key; key="$("$1" -c "import sys;print(sys.prefix)")"
  case "|$SEEN|" in *"|$key|"*) return 0;; esac
  SEEN="$SEEN|$key"; PYS="$PYS $1"
}

if [ -n "$CBPI_PYTHON" ]; then
  add_py "$CBPI_PYTHON"
else
  CB="$(command -v cbpi 2>/dev/null || true)"
  [ -n "$CB" ] && add_py "$(head -1 "$CB" | sed -n 's/^#!\s*//p' | awk '{print $1}')"
  for cb in $(find /home /root /opt /usr/local /srv -maxdepth 6 -path '*/bin/cbpi' -type f 2>/dev/null); do
    add_py "$(head -1 "$cb" | sed -n 's/^#!\s*//p' | awk '{print $1}')"
  done
  add_py "$(command -v python3 2>/dev/null || true)"
fi
if [ -z "$PYS" ]; then
  echo "CraftBeerPi4 не найден. Укажите Python вручную, например:"
  echo "  sudo CBPI_PYTHON=/home/pi/venv/bin/python bash install.sh"
  exit 1
fi

pipcmd() {  # pipcmd PYTHON args...
  local py="$1"; shift
  "$py" -m pip "$@" 2>/tmp/cbpi-uitheme-pip.err || {
    if grep -q "externally-managed" /tmp/cbpi-uitheme-pip.err; then
      "$py" -m pip "$@" --break-system-packages
    else
      cat /tmp/cbpi-uitheme-pip.err; return 1
    fi
  }
}

for PY in $PYS; do
  echo "CraftBeerPi4 найден: $PY"
  if [ "$ACTION" = "remove" ]; then
    pipcmd "$PY" uninstall -y cbpi4-UITheme >/dev/null && echo "Плагин удалён"
  else
    pipcmd "$PY" install --upgrade --no-deps "$PLUGIN_SRC" >/dev/null && echo "Плагин установлен"
  fi
done

if [ -z "$NO_RESTART" ] && command -v systemctl >/dev/null && systemctl list-unit-files craftbeerpi.service 2>/dev/null | grep -q craftbeerpi; then
  echo "Перезапуск службы craftbeerpi..."
  systemctl restart craftbeerpi
else
  echo "Перезапустите CraftBeerPi4 вручную, если служба не называется craftbeerpi."
fi
echo "Готово. Настройки: Settings, вкладка UI Theme. После изменения обновите страницу (F5)."
