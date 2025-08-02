# Debug & QA методология для Telegram‑бота на Python (Cursor + Railway)

Этот файл — готовый **регламент** для отладки и самопроверки. Его можно скормить Cursor’у как инструкцию (system / project notes), а также использовать вручную.

> Если вы не используете GitHub Actions — достаточно следовать командам отсюда локально. Никаких внешних сервисов не требуется.

---

## 0) Мини‑чеклист контекста (заполните)
- Библиотека: `python-telegram-bot` **или** `aiogram` (укажите одну).
- Режим приёма апдейтов: `webhook` (рекомендуется в проде) или `long polling` (локально).
- Python: версия (например, 3.11).
- БД/кэш: (например, Postgres/Redis) или «нет».
- Деплой: Railway (веб‑сервис).
- Бизнес‑инварианты: (что **никогда** не должно ломаться).

Сохраните это сверху проекта в `README.md`.

---

## 1) Быстрый старт без CI (локально)

### 1.1 Установки (один раз)
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -U pip
pip install ruff mypy pytest hypothesis python-dotenv tenacity
# Если используете python-telegram-bot:
pip install python-telegram-bot[ext]
# Если используете aiogram:
pip install aiogram
```

### 1.2 Команды «quality gate» (запускать перед каждым пушем/деплоем)
```bash
# Линтер и автоисправления (проверка без изменений):
ruff check . && ruff format --check .

# Типы (строгость можно наращивать по мере готовности):
mypy .

# Тесты (тихо, быстро):
pytest -q
```

> Если чего‑то нет — создайте минимальные тесты из раздела ниже, а линтер/тайпчек настройте по умолчанию (работает «из коробки»).

---

## 2) Базовая архитектура и точки контроля
- `handlers/` — только разбор апдейта и делегирование логики.
- `services/` — бизнес‑логика (вызовы API/БД, ретраи, таймауты).
- `middlewares/` — логирование, корреляция, rate‑limit, i18n.
- `settings.py` — конфиг через `env`/`.env` (pydantic/settings по желанию).
- `health.py` — эндпоинт `GET /health` → `200 OK` (для Railway).
- `metrics` (опционально) — если используете Prometheus‑клиент.

**Правило:** нет тяжёлой логики в хендлерах; все I/O вызываются из `services/` с ретраями, таймаутами и логами.

---

## 3) Логи, таймауты, ретраи (готовые сниппеты)

### 3.1 Логирование JSON
```python
# file: logging_setup.py
import json, logging, sys

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "time": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
        }
        if record.exc_info:
            base["exc"] = self.formatException(record.exc_info)
        return json.dumps(base, ensure_ascii=False)

def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)
```

Подключайте в `main.py` до старта бота:
```python
from logging_setup import setup_logging
setup_logging()
```

### 3.2 Ретраи с экспоненциальной паузой и джиттером (tenacity)
```python
# file: services/util_retry.py
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

def retryable():
    return retry(
        reraise=True,
        stop=stop_after_attempt(5),                   # до 5 попыток
        wait=wait_exponential_jitter(initial=0.2, max=5.0),  # экспонента + джиттер
    )
```

Применение:
```python
# file: services/api_client.py
import asyncio, http.client
from services.util_retry import retryable

@retryable()
async def fetch_something(arg: str) -> dict:
    # примитивный пример
    await asyncio.sleep(0.01)
    if arg == "flaky":
        raise ConnectionError("temporary")
    return {"ok": True}
```

### 3.3 Таймауты и корректная отмена
```python
# file: services/with_timeout.py
import asyncio

async def with_timeout(coro, seconds: float):
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except asyncio.TimeoutError:
        raise TimeoutError(f"Timed out after {seconds}s")
```

---

## 4) Анти‑спам и лимиты Telegram (минимальное решение)

Telegram ограничивает частоту сообщений. Добавьте элементарный **токен‑бакет** на чат и глобальный.

```python
# file: middlewares/rate_limit.py
import time
from collections import defaultdict, deque

class TokenBucket:
    def __init__(self, rate_per_sec: float, burst: int):
        self.rate = rate_per_sec
        self.capacity = burst
        self.tokens = burst
        self.updated = time.monotonic()

    def allow(self) -> bool:
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
        self.updated = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False

class RateLimiter:
    def __init__(self, per_chat_rate=1.0, per_chat_burst=3, global_rate=20.0, global_burst=20):
        self.per_chat = defaultdict(lambda: TokenBucket(per_chat_rate, per_chat_burst))
        self.global_bucket = TokenBucket(global_rate, global_burst)

    def allow(self, chat_id: int) -> bool:
        return self.global_bucket.allow() and self.per_chat[chat_id].allow()
```

Применение в хендлере (псевдо‑код):
```python
# inside handler
if not rate_limiter.allow(chat_id):
    # мягко молчим или отвечаем «слишком часто»
    return
```

---

## 5) Минимальные тесты (pytest + Hypothesis)

### 5.1 Юниты для сервисов
```python
# file: tests/test_api_client.py
import pytest, asyncio
from services.api_client import fetch_something

@pytest.mark.asyncio
async def test_fetch_ok():
    assert await fetch_something("ok") == {"ok": True}

@pytest.mark.asyncio
async def test_fetch_retry():
    with pytest.raises(ConnectionError):
        # после 5 ретраев свалится
        await fetch_something("flaky")  # пример, адаптируйте под себя
```

### 5.2 Property‑based для парсера команд
```python
# file: tests/test_commands.py
from hypothesis import given, strategies as st

def parse_cmd(s: str) -> str:
    s = s.strip()
    return s.split()[0] if s else ""

@given(st.text())
def test_parse_cmd_never_crashes(s):
    # Парсер не должен падать ни на каких строках
    parse_cmd(s)
```

Запуск: `pytest -q`

---

## 6) Railway: простой и проверяемый путь

### 6.1 Вариант A — Long Polling (проще всего)
- Подходит для старта и локальной проверки.
- Нужна только переменная окружения `TELEGRAM_TOKEN`.

`main.py` (эскиз для python-telegram-bot):
```python
import asyncio, os
from logging_setup import setup_logging
from telegram.ext import ApplicationBuilder, CommandHandler

async def start(update, context):
    await update.message.reply_text("Я жив!")

async def main():
    setup_logging()
    token = os.environ["TELEGRAM_TOKEN"]
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await app.wait_until_closed()
    await app.stop()
    await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

**Проверка локально:**
```bash
export TELEGRAM_TOKEN=...   # Windows: set TELEGRAM_TOKEN=...
python main.py
```

### 6.2 Вариант B — Webhook (рекомендуется в проде)
- Нужен веб‑приложение (например, FastAPI) + эндпоинт `/webhook` + `GET /health`.
- В Railway создайте Web Service; платформа сама выставит `PORT`.

Эскиз (`FastAPI` + python-telegram-bot):
```python
# file: web.py
import os, asyncio
from fastapi import FastAPI, Request
from logging_setup import setup_logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler

app = FastAPI()
telegram_app = None

@app.on_event("startup")
async def startup():
    global telegram_app
    setup_logging()
    token = os.environ["TELEGRAM_TOKEN"]
    webhook_url = os.environ["WEBHOOK_URL"]  # укажите домен Railway (или кастомный)
    telegram_app = ApplicationBuilder().token(token).build()
    telegram_app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Привет!")))
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(url=f"{webhook_url}/webhook")

@app.on_event("shutdown")
async def shutdown():
    await telegram_app.stop()
    await telegram_app.shutdown()

@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}
```

`Procfile` не обязателен; Railway для Python запустит `python -m uvicorn web:app --host 0.0.0.0 --port ${PORT}`. Можно указать команду запуска в настройках сервиса.

**Переменные в Railway:**
- `TELEGRAM_TOKEN` — токен бота
- `WEBHOOK_URL` — ваш публичный URL (из Railway Domains)

**Проверка после деплоя:**
1. Откройте Logs в Railway — проверьте, что приложение запустилось и вебхук установлен.
2. Откройте `https://<ваш-домен>/health` — должны видеть `{"ok": true}`.
3. В Telegram отправьте `/start` — бот должен отвечать.

---

## 7) Стандартная процедура отладки
1. Зафиксируйте **симптом** и время (лог/алерт).
2. Сузьте область: какой апдейт/хендлер/версия.
3. Воспроизведите локально: сохраните проблемный апдейт → минимальный тест/скрипт.
4. Проверьте последние изменения (diff), внешние факторы (429, сеть, БД).
5. Соберите артефакты: DEBUG‑логи, метрики (если есть).
6. Сформулируйте гипотезу → минимальный фикс → тест → деплой.
7. Напишите короткий post‑mortem: причина, как не допустить повторно.

---

## 8) Мини‑чеклист перед релизом
- [ ] `ruff check` и `ruff format --check` зелёные.
- [ ] `mypy` зелёный (строгость приемлема).
- [ ] `pytest -q` зелёный (есть хотя бы smoke‑тесты хендлеров/сервисов).
- [ ] Логи структурированные (без секретов).
- [ ] Rate‑limit включён (пер‑чат и глобально).
- [ ] Для webhook: `GET /health` даёт 200<1s; вебхук установлен.
- [ ] Секреты заданы через переменные окружения (`TELEGRAM_TOKEN`, и т.п.).

---

## 9) Как «скармливать» это Cursor’у
Вставьте этот документ целиком как **инструкцию проекта** и просите:
- «Проверь код по разделам 3 и 4: добавь ретраи/таймауты и rate‑limit».
- «Сгенерируй тесты из раздела 5 для функций A/B».
- «Подготовь web.py под webhook для Railway, домен такой‑то».

---

## 10) Частые проблемы и быстрые проверки
- **429 Too Many Requests** → уменьшите темп, проверьте токен‑бакеты.
- **Webhook не зовётся** → проверьте домен/SSL/порт; `GET /health`; логи старта (установка вебхука).
- **Долгие ответы** → добавьте таймауты, проверьте блокирующие вызовы в хендлерах.
- **Секреты в логах** → проверьте форматтер и точки логирования.

Удачи! Сначала — простая проверка локально, потом — Railway. Без лишней сложности.
