# -*- coding: utf-8 -*-
"""
cbpi4-UITheme: настройки цветов и шрифтов интерфейса CraftBeerPi4.

Плагин добавляет в Settings вкладку "UI Theme" и сам применяет значения: при каждой загрузке
страницы он отдаёт браузеру главный файл интерфейса (main.*.js) с подставленными цветами и
шрифтами. Файлы на диске НЕ изменяются, поэтому удаление плагина возвращает оригинальный вид.
Работает независимо от cbpi4-ui-patch (и вместе с ним).
Значение "Original" в любом поле оставляет оригинальный цвет или шрифт.

Как поменять значения по умолчанию: правьте словари COLORS и FONTS ниже.
Уже сохранённые на сервере значения при обновлении плагина не затираются.
"""
import asyncio
import logging
import os
import re

from aiohttp import web

from cbpi.api import *
from cbpi.api.config import ConfigType

logger = logging.getLogger(__name__)

SOURCE = "UI Theme"          # название вкладки в Settings
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")   # допустимый формат цвета: #RRGGBB

# --------------------------------------------------------------------------
# Цвета: имя настройки -> (значение по умолчанию, описание)
# Формат значения: #RRGGBB. В скобках указан оригинальный цвет CraftBeerPi4.
# --------------------------------------------------------------------------
COLORS = {
    "UI_THEME_PRIMARY_COLOR":        ("#e9b649", "Primary color: buttons, sliders, switches (original #00FF00)"),
    "UI_THEME_SECONDARY_COLOR":      ("#8A2535", "Secondary color: Stop, Cancel, Close, No buttons (original #f50057)"),
    "UI_THEME_SECONDARY_DARK_COLOR": ("#6A040F", "Secondary color on hover and press (original #c51162)"),
    "UI_THEME_SECONDARY_LIGHT_COLOR": ("#ff4081", "Secondary light shade, rarely used (original #ff4081)"),
    "UI_THEME_APPBAR_COLOR":         ("#e9b649", "Top application bar (original #00FF00)"),
    "UI_THEME_PAGE_BG_COLOR":        ("#444444", "Page background (original #444444)"),
    "UI_THEME_DASHBOARD_BG_COLOR":   ("#272227", "Dashboard background behind elements (original #272227)"),
    "UI_THEME_PAPER_COLOR":          ("#333333", "Background of dialogs, menus and cards (original #333333)"),
    "UI_THEME_CARD_BG_COLOR":        ("#2c282e", "Background of sensor and target temperature blocks (original #2c282e)"),
    "UI_THEME_PROGRESS_BAR_COLOR":   ("#e9b649", "Power bar on Actor buttons (original #00FF00)"),
    "UI_THEME_PROGRESS_BG_COLOR":    ("#2C1810", "Background of the power bar (original #008800)"),
    "UI_THEME_CHART_LINE_COLOR":     ("#e9b649", "Default chart line color (original #00FF00)"),
}

# --------------------------------------------------------------------------
# Шрифты. Список для выпадающего меню: (подпись, значение CSS).
# КАК ДОБАВИТЬ ШРИФТ: допишите строку в FONT_OPTIONS в формате
#   ("Подпись в меню", "Название 1, Название 2, sans-serif"),
# В конце значения указывайте общее семейство: sans-serif, serif или monospace.
# Нельзя использовать символы " и \ внутри значения.
# Пункт "Original" оставляет шрифт оригинального интерфейса.
# --------------------------------------------------------------------------
ORIGINAL = "Original"
FONT_OPTIONS = [
    (ORIGINAL, ORIGINAL),
    ("Segoe UI", "Segoe UI, Roboto, Arial, sans-serif"),
    ("Roboto", "Roboto, Segoe UI, Arial, sans-serif"),
    ("Arial", "Arial, Helvetica, sans-serif"),
    ("Verdana", "Verdana, Geneva, sans-serif"),
    ("Tahoma", "Tahoma, Segoe UI, sans-serif"),
    ("Trebuchet MS", "Trebuchet MS, Segoe UI, sans-serif"),
    ("DejaVu Sans", "DejaVu Sans, Verdana, sans-serif"),
    ("Ubuntu", "Ubuntu, Roboto, Arial, sans-serif"),
    ("System UI", "system-ui, sans-serif"),
    ("Georgia", "Georgia, serif"),
    ("Courier New", "Courier New, monospace"),
    ("Monospace", "monospace"),
]
DEFAULT_FONT = "Segoe UI, Roboto, Arial, sans-serif"

FONTS = {
    "UI_FONT_MAIN":  (DEFAULT_FONT, "Main interface font: buttons, menus, dialogs, texts (original Advent Pro)"),
    "UI_FONT_PLOT":  (DEFAULT_FONT, "Chart font: title and legend (original Advent Pro)"),
    "UI_FONT_CARDS": (ORIGINAL,     "Font of sensor cards on the dashboard (original JetBrains Mono)"),
}


# ==========================================================================
#            ПРИМЕНЕНИЕ НАСТРОЕК К ГЛАВНОМУ ФАЙЛУ ИНТЕРФЕЙСА (в памяти)
# ==========================================================================
HEX = r'#[0-9a-fA-F]{3,8}'
JS_RE = re.compile(r"/static/js/main\.[0-9a-f]+\.js$")
CSS_RE = re.compile(r"/static/css/main\.[0-9a-f]+\.css$")


def _gui_js_path(request_path, kind="js"):
    """Путь к файлу main.*.js (kind="js") или main.*.css (kind="css") внутри установленного пакета cbpi4gui."""
    import cbpi4gui
    name = request_path.rsplit("/", 1)[-1]
    p = os.path.join(os.path.dirname(cbpi4gui.__file__), "build", "static", kind, name)
    return p if os.path.isfile(p) else None


def transform(s, C, F):
    """Подставляет цвета C и шрифты F в текст main.js. Каждая замена независима:
    если код интерфейса другой версии и шаблон не найден, замена пропускается (в лог пишется предупреждение)."""
    skipped = []

    def crep(name, pattern, repl, count=1):
        nonlocal s
        new, n = re.subn(pattern, repl, s)
        if n != count:
            skipped.append("%s (%d вместо %d)" % (name, n, count))
            return
        s = new

    if C.get("primary"):
        crep("primary", r'primary:\{main:"%s"\}' % HEX, 'primary:{main:"%s"}' % C["primary"], 2)
    if C.get("secondary"):
        extra = ""
        if C.get("secondary_dark"):
            extra += ',dark:"%s"' % C["secondary_dark"]
        if C.get("secondary_light"):
            extra += ',light:"%s"' % C["secondary_light"]
        sec = 'secondary:{main:"%s"%s}' % (C["secondary"], extra)
        crep("secondary", r'secondary:[\w$]+\.A\}(?=,typography)', lambda m: sec + "}")
        crep("secondary_range", r'secondary:[\w$]+\.A\}(?=\}\))', lambda m: sec + "}")
    if C.get("appbar"):
        crep("appbar", r'background:"%s",(?=transition:t\.transitions\.create)' % HEX, 'background:"%s",' % C["appbar"])
    if C.get("page_bg"):
        crep("page_bg", r'body:\{backgroundColor:"%s"\}' % HEX, 'body:{backgroundColor:"%s"}' % C["page_bg"])
    if C.get("paper"):
        crep("paper", r'backgroundImage:"unset",backgroundColor:"%s"' % HEX,
             'backgroundImage:"unset",backgroundColor:"%s"' % C["paper"])
    if C.get("card_bg"):
        crep("card_bg", r'backgroundColor:"%s"(?=,(?:padding:5,borderRadius:5|color:"#fff",borderRadius:5))' % HEX,
             'backgroundColor:"%s"' % C["card_bg"], 3)
    if C.get("progress_bar") or C.get("progress_bg"):
        crep("progress", r'("& \.MuiLinearProgress-bar":\{backgroundColor:")(%s)("\},backgroundColor:")(%s)(")' % (HEX, HEX),
             lambda m: m[1] + (C.get("progress_bar") or m[2]) + m[3] + (C.get("progress_bg") or m[4]) + m[5], 5)
    if C.get("chart_line"):
        crep("chart_line", r'\|\|"%s",width:2,shape:"spline"' % HEX, lambda m: '||"%s",width:2,shape:"spline"' % C["chart_line"])
        crep("chart_line_default", r'\{name:"linecolor",default:"%s"' % HEX, lambda m: '{name:"linecolor",default:"%s"' % C["chart_line"])

    def lit(old, new, name, count=1):
        nonlocal s
        n = s.count(old)
        if n != count:
            skipped.append("%s (%d вместо %d)" % (name, n, count))
            return
        s = s.replace(old, new)

    if F.get("main"):
        lit('fontFamily:["Advent Pro","monospace"].join(",")', 'fontFamily:"%s"' % F["main"], "font_main")
    if F.get("plot"):
        lit('family:"Advent Pro, sans-serif"', 'family:"%s"' % F["plot"], "font_plot", 6)
    if F.get("cards"):
        lit('fontFamily:"JetBrains Mono, monospace"', 'fontFamily:"%s"' % F["cards"], "font_cards")
    return s, skipped


def transform_css(s, C):
    """Фон дашборда задан в main.*.css (классы divgrid и divnogrid). Подставляет выбранный цвет."""
    skipped = []
    if C.get("dashboard_bg"):
        for old, new in (("divgrid{background:#272227;", "divgrid{background:%s;" % C["dashboard_bg"]),
                         ("divnogrid{background:#272227}", "divnogrid{background:%s}" % C["dashboard_bg"])):
            if s.count(old) != 1:
                skipped.append("dashboard_bg: %s" % old)
            else:
                s = s.replace(old, new)
    return s, skipped


def read_theme(cbpi):
    """Читает текущие настройки; неверные значения и Original игнорируются (остаётся оригинал)."""
    def val(name):
        r = cbpi.config.cache.get(name)
        return str(r.value).strip() if r is not None and r.value is not None else ""

    def color(name):
        v = val(name)
        return v if HEX_RE.match(v) else None

    def font(name):
        v = val(name)
        if not v or v == ORIGINAL or any(c in v for c in '"\\\n\r<>{};'):
            return None
        return v

    C = {k: color(n) for k, n in (
        ("primary", "UI_THEME_PRIMARY_COLOR"), ("secondary", "UI_THEME_SECONDARY_COLOR"),
        ("secondary_dark", "UI_THEME_SECONDARY_DARK_COLOR"), ("secondary_light", "UI_THEME_SECONDARY_LIGHT_COLOR"),
        ("appbar", "UI_THEME_APPBAR_COLOR"), ("page_bg", "UI_THEME_PAGE_BG_COLOR"), ("dashboard_bg", "UI_THEME_DASHBOARD_BG_COLOR"), ("paper", "UI_THEME_PAPER_COLOR"),
        ("card_bg", "UI_THEME_CARD_BG_COLOR"), ("progress_bar", "UI_THEME_PROGRESS_BAR_COLOR"),
        ("progress_bg", "UI_THEME_PROGRESS_BG_COLOR"), ("chart_line", "UI_THEME_CHART_LINE_COLOR"))}
    F = {"main": font("UI_FONT_MAIN"), "plot": font("UI_FONT_PLOT"), "cards": font("UI_FONT_CARDS")}
    return C, F


_cache = {}
_CBPI = [None]   # ссылка на сервер CBPi4 (middleware вызывается и из под-приложений)


@web.middleware
async def theme_middleware(request, handler):
    """Отдаёт main.*.js с подставленными цветами и шрифтами. При любой ошибке отдаёт файл как есть."""
    if request.method == "GET" and JS_RE.search(request.path):
        try:
            cbpi = _CBPI[0]
            path = _gui_js_path(request.path)
            if path:
                C, F = read_theme(cbpi)
                key = (path, os.path.getmtime(path), tuple(sorted(C.items(), key=str)), tuple(sorted(F.items(), key=str)))
                if key not in _cache:
                    with open(path, encoding="utf-8") as f:
                        text = f.read()
                    text, skipped = transform(text, C, F)
                    if skipped:
                        logger.warning("UITheme: часть замен пропущена (другая версия интерфейса?): %s", "; ".join(skipped))
                    _cache.clear()
                    _cache[key] = text
                return web.Response(text=_cache[key], content_type="application/javascript", charset="utf-8",
                                    headers={"Cache-Control": "no-cache"})
        except Exception as e:
            logger.error("UITheme: ошибка подстановки, отдаю оригинальный файл: %s", e)
    if request.method == "GET" and CSS_RE.search(request.path):
        try:
            path = _gui_js_path(request.path, "css")
            if path:
                C, _F = read_theme(_CBPI[0])
                key = (path, os.path.getmtime(path), C.get("dashboard_bg"))
                if key not in _cache:
                    with open(path, encoding="utf-8") as f:
                        text = f.read()
                    text, skipped = transform_css(text, C)
                    if skipped:
                        logger.warning("UITheme: замена в CSS пропущена (другая версия интерфейса?): %s", "; ".join(skipped))
                    _cache[key] = text
                return web.Response(text=_cache[key], content_type="text/css", charset="utf-8",
                                    headers={"Cache-Control": "no-cache"})
        except Exception as e:
            logger.error("UITheme: ошибка подстановки CSS, отдаю оригинальный файл: %s", e)
    return await handler(request)


class UITheme(CBPiExtension):
    def __init__(self, cbpi):
        self.cbpi = cbpi
        _CBPI[0] = cbpi
        cbpi.app.middlewares.append(theme_middleware)
        self._task = asyncio.create_task(self.run())

    async def _ensure(self, name, default, description, type_, options=None):
        """Создаёт настройку, если её нет, иначе обновляет описание и список, сохраняя значение."""
        raw = self.cbpi.config.cache.get(name)
        cur = raw.value if raw is not None and raw.value not in (None, "") else None
        value = default if cur is None else cur
        if type_ == ConfigType.STRING and not (HEX_RE.match(str(value)) or value == ORIGINAL):
            logger.warning("UITheme: %s has invalid value %r, reset to %s", name, value, default)
            value = default
        if type_ == ConfigType.SELECT and options and value not in [o["value"] for o in options]:
            # значение введено вручную или шрифт убран из списка: добавим его в список
            options = options + [{"label": str(value), "value": value}]
        await self.cbpi.config.add(name, value, type=type_, description=description,
                                   source=SOURCE, options=options)

    async def _migrate_old_names(self):
        """Старые версии плагина называли цвета UI_<ИМЯ>_COLOR. Теперь UI_THEME_<ИМЯ>_COLOR
        (так в Settings шрифты идут перед цветами). Переносим сохранённые значения и удаляем старые."""
        for new in COLORS:
            old = "UI_" + new[len("UI_THEME_"):]
            raw_old = self.cbpi.config.cache.get(old)
            if raw_old is None:
                continue
            raw_new = self.cbpi.config.cache.get(new)
            if raw_new is None and raw_old.value not in (None, ""):
                await self.cbpi.config.add(new, raw_old.value, type=ConfigType.STRING, description="",
                                           source=SOURCE, options=None)
            try:
                await self.cbpi.config.remove(old)
            except Exception as e:
                logger.warning("UITheme: cannot remove old setting %s: %s", old, e)

    async def run(self):
        try:
            await self._migrate_old_names()
            for name, (default, desc) in COLORS.items():
                await self._ensure(name, default, desc + ". Format #RRGGBB or Original", ConfigType.STRING)
            options = [{"label": l, "value": v} for l, v in FONT_OPTIONS]
            for name, (default, desc) in FONTS.items():
                await self._ensure(name, default, desc, ConfigType.SELECT, list(options))
            logger.info("UITheme: settings registered")
        except Exception as e:
            logger.error("UITheme: failed to register settings: %s", e)


def setup(cbpi):
    cbpi.plugin.register("UITheme", UITheme)
