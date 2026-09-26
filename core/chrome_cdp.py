"""
Модуль взаимодействия с Google Chrome через Chrome DevTools Protocol (CDP).
Обеспечивает подключение к открытым вкладкам браузера, навигацию,
поиск полей ввода на любых веб-сайтах и автоматический ввод запросов.
"""
import os
import re
import json
import time
import shutil
import asyncio
import tempfile
import subprocess
import urllib.request
import urllib.parse
from typing import Optional, Any, Callable

# Словарь прямых поисковых шаблонов для популярных сервисов
KNOWN_SITE_SEARCH_PATTERNS: dict[str, str] = {
    "кинопоиск": "https://www.kinopoisk.ru/index.php?kp_query={query}",
    "kinopoisk": "https://www.kinopoisk.ru/index.php?kp_query={query}",
    "авито": "https://www.avito.ru/rossiya?q={query}",
    "avito": "https://www.avito.ru/rossiya?q={query}",
    "озон": "https://www.ozon.ru/search/?text={query}",
    "ozon": "https://www.ozon.ru/search/?text={query}",
    "википедия": "https://ru.wikipedia.org/w/index.php?search={query}",
    "wikipedia": "https://ru.wikipedia.org/w/index.php?search={query}",
    "вайлдберриз": "https://www.wildberries.ru/catalog/0/search.aspx?search={query}",
    "wildberries": "https://www.wildberries.ru/catalog/0/search.aspx?search={query}",
    "яндекс маркет": "https://market.yandex.ru/search?text={query}",
    "маркет": "https://market.yandex.ru/search?text={query}",
    "алиэкспресс": "https://aliexpress.ru/wholesale?SearchText={query}",
    "aliexpress": "https://aliexpress.ru/wholesale?SearchText={query}",
    "стим": "https://store.steampowered.com/search/?term={query}",
    "steam": "https://store.steampowered.com/search/?term={query}",
    "рутуб": "https://rutube.ru/search/?query={query}",
    "rutube": "https://rutube.ru/search/?query={query}",
    "твич": "https://www.twitch.tv/search?term={query}",
    "twitch": "https://www.twitch.tv/search?term={query}",
    "реддит": "https://www.reddit.com/search/?q={query}",
    "reddit": "https://www.reddit.com/search/?q={query}",
    "гитхаб": "https://github.com/search?q={query}",
    "github": "https://github.com/search?q={query}",
    "хабр": "https://habr.com/ru/search/?q={query}",
    "habr": "https://habr.com/ru/search/?q={query}",
    "гугл": "https://www.google.com/search?q={query}",
    "google": "https://www.google.com/search?q={query}",
    "яндекс": "https://ya.ru/search/?text={query}",
    "yandex": "https://ya.ru/search/?text={query}"
}

KNOWN_SITE_DOMAINS: dict[str, str] = {
    "кинопоиск": "https://www.kinopoisk.ru",
    "kinopoisk": "https://www.kinopoisk.ru",
    "авито": "https://www.avito.ru",
    "avito": "https://www.avito.ru",
    "озон": "https://www.ozon.ru",
    "ozon": "https://www.ozon.ru",
    "википедия": "https://ru.wikipedia.org",
    "wikipedia": "https://ru.wikipedia.org",
    "вайлдберриз": "https://www.wildberries.ru",
    "wildberries": "https://www.wildberries.ru",
    "яндекс маркет": "https://market.yandex.ru",
    "маркет": "https://market.yandex.ru",
    "алиэкспресс": "https://aliexpress.ru",
    "aliexpress": "https://aliexpress.ru",
    "стим": "https://store.steampowered.com",
    "steam": "https://store.steampowered.com",
    "рутуб": "https://rutube.ru",
    "rutube": "https://rutube.ru",
    "твич": "https://www.twitch.tv",
    "twitch": "https://www.twitch.tv",
    "реддит": "https://www.reddit.com",
    "reddit": "https://www.reddit.com",
    "гитхаб": "https://github.com",
    "github": "https://github.com",
    "хабр": "https://habr.com",
    "habr": "https://habr.com"
}


class ChromeCDPController:
    """Управляет вкладками Chrome по протоколу Chrome DevTools (CDP)."""

    def __init__(self, port: int = 9222, on_log: Optional[Callable[[str], None]] = None):
        self.port = port
        self.on_log = on_log

    def log(self, message: str) -> None:
        """Логирует информационное сообщение."""
        if self.on_log:
            self.on_log(message)
        print(f"[ChromeCDP] {message}")

    def is_cdp_available(self) -> bool:
        """Проверяет, отвечает ли Chrome по порту отладки CDP."""
        try:
            url = f"http://127.0.0.1:{self.port}/json/version"
            req = urllib.request.Request(url, headers={"User-Agent": "Antigravity/1.0"})
            with urllib.request.urlopen(req, timeout=0.8) as resp:
                return resp.status == 200
        except Exception:
            return False

    @staticmethod
    def find_chrome_executable() -> Optional[str]:
        """Определяет путь к исполняемому файлу chrome.exe в системе."""
        candidates = [
            shutil.which("chrome"),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
        ]
        for path in candidates:
            if path and os.path.exists(path):
                return path
        return None

    def launch_chrome_with_cdp(self) -> bool:
        """Запускает Chrome с включенным портом отладки CDP."""
        if self.is_cdp_available():
            return True

        chrome_path = self.find_chrome_executable()
        if not chrome_path:
            self.log("Ошибка: исполняемый файл Chrome не найден в системе.")
            return False

        profile_dir = os.path.join(tempfile.gettempdir(), "chrome_cdp_profile")
        os.makedirs(profile_dir, exist_ok=True)

        cmd = [
            chrome_path,
            f"--remote-debugging-port={self.port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check"
        ]

        try:
            subprocess.Popen(cmd)
            # Ожидаем инициализации сокета CDP (до 3 секунд)
            for _ in range(15):
                time.sleep(0.2)
                if self.is_cdp_available():
                    self.log(f"Chrome успешно запущен с CDP на порту {self.port}")
                    return True
        except Exception as e:
            self.log(f"Не удалось запустить Chrome: {e}")

        return False

    def get_tabs(self) -> list[dict[str, Any]]:
        """Возвращает список открытых страниц (вкладок) Chrome."""
        if not self.is_cdp_available():
            return []

        try:
            url = f"http://127.0.0.1:{self.port}/json/list"
            req = urllib.request.Request(url, headers={"User-Agent": "Antigravity/1.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return [t for t in data if t.get("type") == "page"]
        except Exception as e:
            self.log(f"Ошибка получения списка вкладок: {e}")
            return []

    def open_new_tab(self, url: str) -> Optional[dict[str, Any]]:
        """Открывает новую вкладку с заданным URL через CDP HTTP API."""
        if not self.is_cdp_available():
            return None

        try:
            encoded_url = urllib.parse.quote(url)
            endpoint = f"http://127.0.0.1:{self.port}/json/new?{encoded_url}"
            req = urllib.request.Request(endpoint, method="PUT")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            self.log(f"Ошибка создания вкладки через CDP: {e}")
            return None

    def evaluate_javascript_sync(self, ws_url: str, expression: str, timeout: float = 4.0) -> dict[str, Any]:
        """Синхронная обертка для выполнения произвольного JavaScript в контексте вкладки."""
        return asyncio.run(self._evaluate_javascript_async(ws_url, expression, timeout))

    async def _evaluate_javascript_async(self, ws_url: str, expression: str, timeout: float) -> dict[str, Any]:
        """Выполняет JavaScript во вкладке Chrome через WebSocket протокол CDP."""
        import websockets

        try:
            async with websockets.connect(ws_url) as ws:
                req_id = int(time.time() * 1000) % 100000
                payload = {
                    "id": req_id,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": expression,
                        "returnByValue": True,
                        "awaitPromise": True
                    }
                }
                await ws.send(json.dumps(payload))

                start = time.time()
                while time.time() - start < timeout:
                    raw_msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    msg = json.loads(raw_msg)
                    if msg.get("id") == req_id:
                        return msg.get("result", {}).get("result", {})

        except Exception as e:
            self.log(f"Ошибка выполнения JavaScript через CDP: {e}")

        return {"type": "undefined"}

    def run_universal_search_script(
        self,
        ws_url: str,
        query: str,
        click_first: bool = False
    ) -> tuple[bool, str]:
        """
        Внедряет универсальный скрипт поиска по сайту:
        находит поле поиска, фокусируется, вводит запрос, жмет Enter
        и при необходимости кликает по первому результату.
        """
        escaped_query = json.dumps(query, ensure_ascii=False)
        click_flag = "true" if click_first else "false"

        script = f"""
        (() => {{
            const query = {escaped_query};
            const clickFirst = {click_flag};

            // 1. Поиск строки ввода по селекторам
            const selectors = [
                'input[type="search"]',
                '[role="searchbox"]',
                'input[name*="search" i]',
                'input[name*="query" i]',
                'input[name="q"]',
                'input[name="text"]',
                'input[placeholder*="поиск" i]',
                'input[placeholder*="search" i]',
                'input[placeholder*="найти" i]',
                'input[aria-label*="поиск" i]',
                'input[aria-label*="search" i]',
                'textarea[placeholder*="поиск" i]'
            ];

            let inputEl = null;
            for (const sel of selectors) {{
                const found = Array.from(document.querySelectorAll(sel)).filter(el => {{
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden';
                }});
                if (found.length > 0) {{
                    inputEl = found[0];
                    break;
                }}
            }}

            if (!inputEl) {{
                return {{ success: false, message: 'Поле поиска не найдено на странице' }};
            }}

            // 2. Ввод текста с эмуляцией пользовательских событий
            inputEl.focus();
            inputEl.value = query;
            inputEl.dispatchEvent(new Event('input', {{ bubbles: true }}));
            inputEl.dispatchEvent(new Event('change', {{ bubbles: true }}));

            // 3. Отправка формы или нажатие клавиши Enter
            const enterDown = new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }});
            const enterUp = new KeyboardEvent('keyup', {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }});
            inputEl.dispatchEvent(enterDown);
            inputEl.dispatchEvent(enterUp);

            if (inputEl.form) {{
                try {{
                    inputEl.form.dispatchEvent(new Event('submit', {{ bubbles: true, cancelable: true }}));
                }} catch (e) {{}}
            }}

            // 4. Опциональный переход на первый результат
            if (clickFirst) {{
                setTimeout(() => {{
                    const cardSelectors = [
                        'main a[href]:not([href="#"])',
                        'article a[href]:not([href="#"])',
                        '[class*="results" i] a[href]',
                        '[class*="item" i] a[href]',
                        '[class*="product" i] a[href]',
                        '[class*="card" i] a[href]',
                        'h3 a[href]',
                        'h2 a[href]'
                    ];
                    for (const sel of cardSelectors) {{
                        const links = Array.from(document.querySelectorAll(sel)).filter(el => {{
                            const rect = el.getBoundingClientRect();
                            return rect.width > 30 && rect.height > 15;
                        }});
                        if (links.length > 0) {{
                            links[0].click();
                            break;
                        }}
                    }}
                }}, 1200);
            }}

            return {{ success: true, message: 'Поисковый запрос введен и отправлен' }};
        }})()
        """

        res = self.evaluate_javascript_sync(ws_url, script)
        val = res.get("value", {}) if isinstance(res, dict) else {}
        if isinstance(val, dict) and val.get("success"):
            return True, val.get("message", "Успешно")
        err_msg = val.get("message", "Элемент не найден") if isinstance(val, dict) else "Ошибка скрипта"
        return False, err_msg

    def execute_site_search(
        self,
        site_name: str,
        query: str,
        click_first: bool = False
    ) -> tuple[bool, str, str]:
        """
        Главная точка входа для поиска на любом сайте.
        Возвращает: (успех, сообщение, итоговый URL).
        """
        clean_site = site_name.lower().strip()
        clean_query = query.strip()

        # 1. Проверяем наличие прямого шаблона поиска (Fast-Path)
        pattern = KNOWN_SITE_SEARCH_PATTERNS.get(clean_site)
        if pattern:
            encoded_q = urllib.parse.quote(clean_query)
            target_url = pattern.format(query=encoded_q)
            self.log(f"Использован прямой поисковый шаблон для {site_name}: {target_url}")
            return True, f"Поиск на {site_name}: {clean_query}", target_url

        # 2. Если сайт указан как домен или известен его адрес
        site_url = KNOWN_SITE_DOMAINS.get(clean_site)
        if not site_url:
            if "." in clean_site and not clean_site.startswith("http"):
                site_url = f"https://{clean_site}"
            elif clean_site.startswith("http"):
                site_url = clean_site
            else:
                # Fallback: поиск через Google с ограничением по сайту
                target_url = f"https://www.google.com/search?q={urllib.parse.quote(clean_site + ' ' + clean_query)}"
                return True, f"Поиск в Google: {clean_site} {clean_query}", target_url

        # 3. Если CDP доступен - открываем сайт и используем универсальный скрипт
        if self.is_cdp_available():
            tab = self.open_new_tab(site_url)
            if tab and "webSocketDebuggerUrl" in tab:
                ws_url = tab["webSocketDebuggerUrl"]
                time.sleep(2.0)  # Ждем первичной загрузки разметки
                ok, msg = self.run_universal_search_script(ws_url, clean_query, click_first=click_first)
                if ok:
                    return True, f"Выполнен поиск на {site_name}: {clean_query}", site_url
                self.log(f"Предупреждение CDP: {msg}. Открываем прямой URL.")

        # 4. Базовый fallback - открываем сайт
        return True, f"Открыт сайт {site_name}", site_url
