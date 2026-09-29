# AI Task Bot — пошаговый план
### Omni-Channel Task Management · тестовое на AI Engineering Intern

**Срок:** 2–3 дня · **Где:** `~/Desktop/board` (монорепо) · **Этот файл = source of truth.** Если решение меняется, сначала правим план, потом код.

---

## 📑 Оглавление

| Фаза | Что | День |
|---|---|---|
| 0 | Правила, решения, каркас репо | 1 |
| 1 | Backend core: config, logging, errors, БД | 1 |
| 2 | Docker + compose + health | 1 |
| 3 | REST API + auth | 1 |
| 4 | Очереди, бот (текст), «ходячий скелет» фронта | 1 |
| 5 | AI: транскрипция + экстрактор, голосовой пайплайн | 2 |
| 6 | Realtime (SSE) | 2 |
| 7 | React-дашборд | 2–3 |
| 8 | CI, README, финальная приёмка | 3 |

Маркеры: `✅ DoD` — когда шаг закрыт · `🔍` — команда проверки · `⚠️` — ловушка · `💡` — почему именно так.

---

## 🤝 Как работаем

- **Один шаг = один коммит.** Сообщение — одно короткое предложение на английском в повелительном наклонении (`Add task API`). Без `Co-Authored-By` и без атрибуции.
- **Комментарии** только там, где неочевидно «почему», и только на английском. Без докстрингов, пересказывающих код.
- **Экономия:** без лишних абстракций и зависимостей. Интерфейс заводим, только когда реализаций две и больше. Отчёт по шагу — 1–2 строки.
- **Вопросы:** если решение неочевидно и влияет на результат, сначала спрашиваем, потом пишем код.
- **Секреты** хранятся только в `.env` (он в `.gitignore`). gitleaks стоит до первого коммита.

---

# ФАЗА 0 — Решения и каркас

## 0.1 Архитектура

**Модульный монолит с несколькими точками входа.** Один Python-пакет, один слой `services`, четыре процесса: `api`, `bot`, `worker` (транскрипция), `notifier` (уведомления). Все они stateless, общее состояние живёт только в Postgres и Redis.
💡 Бизнес-логика одна, откуда бы ни пришла задача. При этом процессы масштабируются и падают независимо.

```
Telegram ─► bot ──(1) ACK «🎤 Распознаю…» ─► Telegram
             │ (2) INSERT task(queued, tg_file_id)
             └─(3) enqueue ─► [transcription] ─► worker: download(file_id) → whisper → extract → UPDATE
                                                   ├─► PUBLISH events:user:{id} ─► api ─SSE─► React
                                                   └─► enqueue ─► [notifications] ─► notifier ─► edit ACK
React PATCH status ─► api ─► PUBLISH + enqueue ─► notifier ─► «🔄 #id → Completed»
```

## 0.2 Ключевые решения

| Вопрос | Решение | 💡 Почему |
|---|---|---|
| Язык | Python 3.12 | Вакансия ставит Python первым, Whisper-экосистема питоновская |
| API | FastAPI + SQLAlchemy 2 async + asyncpg + Alembic | Стандарт async-Python, pydantic даёт валидацию и OpenAPI |
| Бот | aiogram 3, long-polling, **1 реплика** | Ревьюеру не нужен туннель. Масштабирование бота — это переход на webhook (в README) |
| Очередь | arq (Redis) | asyncio-native, retry/timeout/job_id/cron из коробки |
| Воркеры | `worker` (transcription, `max_jobs=1`) и `notifier` (notifications, `max_jobs=20`) | Медленная транскрипция не блокирует быстрые уведомления. Whisper масштабируется репликами, а не потоками |
| STT | faster-whisper **`small`**, int8, VAD — по умолчанию; OpenAI — за флагом | Ключа нет; `small` заметно точнее на русском. Та же модель Whisper на CTranslate2 → «Whisper or similar» выполнено |
| Передача аудио | в очередь идёт только `tg_file_id`, воркер скачивает файл сам | Без общего volume; ACK быстрее; ретраи всегда могут скачать файл заново |
| Структурирование | правила (`dateparser` + ключевые слова + `#теги`) по умолчанию; LLM — за флагом | Работает без ключа, детерминированно, тестируется |
| Realtime | Redis Pub/Sub → SSE | Поток только server→client, браузер сам переподключается, масштабируется на N реплик API |
| Auth | magic-link из бота → httpOnly cookie с JWT | 128-битный токен не перебрать; один origin → cookie уходит и в `fetch`, и в `EventSource`; XSS не может украсть токен |
| Отказы | статус `failed` + кнопка «Повторить» + reconciler | Правда о состоянии хранится в БД, а не в отдельном DLQ |
| Время | `APP_TZ=Asia/Yerevan`, все даты `timestamptz` | «Завтра в 10» должно значить 10:00 по Еревану, а не по UTC |
| Фронт | React 19 + Vite + TS + Tailwind + @dnd-kit, отдаёт nginx | Быстро, лёгкий образ, один origin с API |

**Вне объёма** (фиксируем в README как осознанное решение): K8s, Terraform, webhook, transactional outbox, replay SSE, вложения кроме голоса.

## 0.3 Структура репо

```
board/
├── PLAN.md  README.md  Makefile  .env.example  .gitignore  .pre-commit-config.yaml
├── docker-compose.yml            # всё окружение, healthchecks
├── docker-compose.override.yml   # dev: hot-reload, открытые порты
├── .github/workflows/ci.yml
├── backend/
│   ├── pyproject.toml  uv.lock  Dockerfile  .dockerignore  alembic.ini  alembic/
│   ├── app/
│   │   ├── core/      config.py logging.py errors.py
│   │   ├── db/        base.py session.py models.py
│   │   ├── schemas/   task.py auth.py
│   │   ├── services/  tasks.py users.py auth.py events.py
│   │   ├── queue/     client.py
│   │   ├── ai/        transcriber.py extractor.py
│   │   ├── api/       main.py deps.py routes/{system,auth,tasks,events}.py
│   │   ├── bot/       main.py handlers.py texts.py
│   │   └── worker/    transcription.py notifications.py
│   └── tests/
└── web/
    ├── Dockerfile  nginx.conf  package.json  vite.config.ts
    └── src/ api.ts types.ts App.tsx hooks/ components/
```

**Правило слоёв:** `api`, `bot` и `worker` — тонкие входные точки, они вызывают `services`. `services` работают с `db`, `queue` и `ai`. `core` ни от чего не зависит. Окружение читает только `core/config.py`.

## 0.4 Каркас

- `git init`, `.gitignore` (Python, Node, `.env`, `__pycache__`, `node_modules`, `dist`, `.venv`)
- `.pre-commit-config.yaml` — копия из `final_project/app-api` + хуки `ruff` и `ruff-format`
- `backend/pyproject.toml`: зависимости с точными пинами, extra `[worker]` для faster-whisper; `ruff` (select `E,F,I,B,UP,SIM,ASYNC`), `mypy` с `disallow_untyped_defs` (не `--strict`: у aiogram/arq неполные типы, иначе шум), `pytest` с `asyncio_mode=auto`
- `.env.example`: только имена и безопасные дефолты, секреты пустые
- `Makefile`: `up down logs test lint fmt migrate`

✅ **DoD:** `pre-commit run -a` зелёный, `uv sync` ставит зависимости.
🔍 `pre-commit run -a && cd backend && uv run ruff check .`
Коммит: `Scaffold monorepo with tooling`

---

# ФАЗА 1 — Backend core

## 1.1 Config — `core/config.py`

`pydantic-settings`, один объект `Settings`, `get_settings()` с `lru_cache`. Поля: `DATABASE_URL`, `REDIS_URL`, `TELEGRAM_BOT_TOKEN`, `JWT_SECRET` (min 32), `SESSION_TTL_DAYS`, `WEB_URL` (для magic-link), `COOKIE_SECURE` (false в dev), `APP_TZ`, `TRANSCRIBER` (`faster_whisper|openai|fake`), `WHISPER_MODEL=small`, `WHISPER_THREADS`, `EXTRACTOR` (`rules|llm|fake`), `OPENAI_API_KEY` (optional), `VOICE_MAX_SEC=300`, `LOG_LEVEL`, `VERSION/COMMIT_SHA/BUILD_TIME`.

💡 Приложение с плохим env падает на старте с понятным списком ошибок, а не через час на первом запросе.
⚠️ Если `TRANSCRIBER=openai` или `EXTRACTOR=llm`, а ключа нет, — ошибка на старте (`model_validator`).

## 1.2 Logging — `core/logging.py`

structlog, JSON в проде и цветной вывод в dev. `request_id` и `task_id` через contextvars; секреты и токены не логируются.

## 1.3 Errors — `core/errors.py`

`AppError(status, code, message)` + подклассы `NotFound`, `Unauthorized`, `Conflict`. Хендлер FastAPI отдаёт единый формат `{"error": {"code", "message"}}`, любая неизвестная ошибка → непрозрачный 500, а детали уходят в лог.

## 1.4 БД — `db/`

- `base.py`: `DeclarativeBase` + naming convention для constraint'ов (иначе Alembic генерирует безымянные)
- `session.py`: `create_async_engine(pool_pre_ping=True)` + `async_sessionmaker`; один engine на процесс
- `models.py`:
  - `User(id, telegram_id uniq, username, first_name, created_at)`
  - `Task(id, user_id fk, title, description, tags ARRAY, status, priority, due_at timestamptz, source, raw_text, language, transcription_status, transcription_error, transcription_ms, transcription_attempt, tg_chat_id, tg_message_id, tg_file_id, created_at, updated_at)`
  - `TaskEvent(id, task_id fk, type, payload JSONB, created_at)` — аудит пайплайна
  - Статусы — Python `StrEnum` + `Enum(native_enum=False)` → в БД `VARCHAR` + `CHECK`
  - Индексы `(user_id, status)`, `(user_id, created_at desc)`, частичный `(transcription_status, updated_at) WHERE transcription_status IN ('queued','processing')` для reconciler
- Alembic: async `env.py`, первая миграция через autogenerate, **просмотренная глазами**

💡 `native_enum=False`: добавить статус — обычная миграция `CHECK`, а не `ALTER TYPE` вне транзакции.
💡 `pool_pre_ping`: после рестарта Postgres пул сам выкидывает мёртвые соединения.

✅ **DoD:** тест «невалидный env → ValidationError», миграция применяется на чистую БД.
Коммит: `Add config, logging, errors and database models`

---

# ФАЗА 2 — Docker и compose

## 2.1 `backend/Dockerfile` (multi-stage)

```
base    python:3.12-slim + uv (COPY --from=ghcr.io/astral-sh/uv), non-root user app
deps    uv sync --frozen --no-dev --no-install-project (только pyproject + uv.lock → кэш слоя)
app     код, UV_COMPILE_BYTECODE=1; CMD переопределяется в compose (api / bot / notifier / migrate)
worker  deps + extra [worker] + модель Whisper скачивается на этапе сборки
```
Build-args `VERSION`, `COMMIT_SHA`, `BUILD_TIME` → env → `/version`.
💡 Один образ `app` на api/bot/notifier: код общий, отличается только команда. Модель есть только в `worker`.
⚠️ Модель качаем в build, а не при старте: иначе первый запуск ждёт скачивания, и без интернета всё падает.

## 2.2 `docker-compose.yml`

| Сервис | Образ/target | Зависит от | Healthcheck |
|---|---|---|---|
| postgres | `postgres:17-alpine` + volume | — | `pg_isready` |
| redis | `redis:7-alpine`, `--appendonly yes` + volume | — | `redis-cli ping` |
| migrate | `app`, `alembic upgrade head` | postgres healthy | one-shot |
| api | `app`, uvicorn | migrate completed, redis healthy | `/ready` |
| bot | `app` | migrate completed, redis healthy | — |
| worker | `worker` | migrate completed, redis healthy | `arq --check …` |
| notifier | `app` | redis healthy | `arq --check …` |
| web | nginx (фаза 4.4) | api healthy | — |

`restart: unless-stopped` у долгоживущих сервисов. Наружу торчит только `web:8080`; в override для dev ещё `api:8000`, `postgres:5432`, `redis:6379`.
💡 `depends_on: condition: service_healthy / service_completed_successfully` убирает гонки на старте.

## 2.3 System routes — `api/routes/system.py`

- `/health` → `{"status":"ok"}` (liveness, без зависимостей)
- `/ready` → `SELECT 1` + `PING` Redis, при сбое 503
- `/version` → `{version, commit, buildTime}`

✅ **DoD:** `make up` поднимает стек, миграции проходят сами.
🔍 `curl -s localhost:8000/ready && docker compose ps` (всё healthy) `&& docker compose exec api whoami` (не root)
Коммит: `Add Docker setup and health endpoints`

---

# ФАЗА 3 — REST API и auth

## 3.1 Services

- `users.get_or_create(telegram_id, username, first_name)` — upsert через `on_conflict_do_update`
- `tasks`: `create`, `list(user_id, status?, q?)`, `get(user_id, id)`, `update`, `delete`, `stats`. **Каждый запрос фильтруется по `user_id`**; чужая задача → `NotFound`, а не 403 (не раскрываем, что она существует)
- `auth`:
  - `issue_login_link(user_id)` → `secrets.token_urlsafe(32)` в Redis `login:{token}`, TTL 300 → `{WEB_URL}/login?token=…`
  - `exchange(token)` → `GETDEL` (атомарно = одноразово) → JWT (`sub=user_id`, `exp`)

💡 `GETDEL` вместо `GET` + `DEL`: два параллельных запроса не смогут использовать одну ссылку дважды.

## 3.2 Routes + deps

- `deps.py`: `get_session`, `get_redis`, `current_user` (JWT из cookie `session`, PyJWT)
- `POST /api/auth/exchange {token}` → `Set-Cookie: session=<jwt>; HttpOnly; SameSite=Strict; Path=/; Secure=COOKIE_SECURE`
- `POST /api/auth/logout`, `GET /api/auth/me`
- `GET|POST /api/tasks`, `PATCH|DELETE /api/tasks/{id}`, `GET /api/stats`
- Схемы `TaskCreate`, `TaskUpdate` (все поля optional), `TaskOut`

💡 CSRF закрыт `SameSite=Strict` и тем, что API принимает только `application/json`.
⚠️ Magic-link открывается GET-запросом, а превью ссылок в Telegram делает GET заранее и «съело» бы токен. Поэтому страница `/login` во фронте забирает токен из URL и сама делает POST `exchange`; бот отправляет ссылку с `disable_web_page_preview`.

## 3.3 Тесты

Фикстуры: реальные Postgres и Redis из compose (`make test` поднимает их), `TRUNCATE … RESTART IDENTITY CASCADE` + `FLUSHDB` перед каждым тестом, `httpx.AsyncClient(ASGITransport)`.
- создать → получить в списке → PATCH статуса → удалить
- чужая задача → 404
- повторный токен → 401; без cookie → 401
- PATCH с невалидным статусом → 422

💡 `TRUNCATE` вместо rollback на тест: сервисы сами делают `commit`, а rollback потребовал бы savepoint-паттерна.

✅ **DoD:** тесты зелёные.
🔍 `make test`
Коммит: `Add task and auth API`

---

# ФАЗА 4 — Очереди, бот, ходячий скелет

## 4.1 `queue/client.py`

Ленивый пул `arq.create_pool`; хелперы:
- `enqueue_transcription(task_id, attempt)` → `_job_id=f"transcribe:{task_id}:{attempt}"`, `_queue_name="transcription"`
- `enqueue_notification(chat_id, text, message_id=None)` → `_queue_name="notifications"`

💡 `job_id` с номером попытки даёт идемпотентность в пределах попытки: дубль того же enqueue игнорируется, а ручной retry получает новый id.
⚠️ arq держит результат джобы (`keep_result`, по умолчанию 1 ч), и пока он лежит, enqueue с тем же `job_id` молча игнорируется. Поэтому у transcription `keep_result=0` и номер попытки в id.

## 4.2 Notifier — `worker/notifications.py`

`WorkerSettings`: `queue_name="notifications"`, `max_jobs=20`, `max_tries=5`. Джоба `notify` через aiogram `Bot`: если есть `message_id` → `edit_message_text`, иначе `send_message`. На `TelegramRetryAfter` → `Retry(defer=e.retry_after)`; на «message is not modified» — тихо выходим.
⚠️ Telegram ограничивает частоту отправки (~30 msg/s глобально). `RetryAfter` — штатная ситуация.

## 4.3 Бот — `bot/`

- `main.py`: `Dispatcher`, middleware, которое кладёт в handler сессию и пользователя (`get_or_create`), `start_polling`, graceful stop
- `handlers.py`:
  - `/start` — приветствие и как пользоваться
  - `/login` — magic-link (без превью)
  - `/help`
  - текст → `extractor` (с таймаутом 3 с и fallback на правила) → `tasks.create(source=text)` → ответ «✅ #id: title»
- `texts.py` — все строки бота в одном месте

## 4.4 Ходячий скелет фронта

Vite React-TS: страница `/login` (обмен токена) и простой список задач. `web/Dockerfile` (`node:22-alpine` build → `nginx:alpine`) и `nginx.conf` с `location /api/ → proxy_pass http://api:8000`. Сервис `web` в compose.
💡 К концу дня 1 все слои связаны в цепочку Telegram → бот → БД → API → nginx → браузер. Интеграционные проблемы (proxy, cookie, origin) всплывают сразу, а не на третий день.

✅ **DoD:** текст в Telegram → `/login` → ссылка → задача видна на `localhost:8080`.
Коммиты: `Add queue client, notifier and text bot`, `Add dashboard skeleton behind nginx`

---

# ФАЗА 5 — AI и голосовой пайплайн (ядро оценки)

## 5.1 `ai/transcriber.py`

```python
class Transcriber(Protocol):
    async def transcribe(self, audio: bytes) -> Transcript: ...   # text, language, duration
```
- `FasterWhisperTranscriber`: модель грузится один раз в `__init__` с `cpu_threads=WHISPER_THREADS`; вызов через `asyncio.to_thread` (CPU-bound, иначе блокирует event loop); `vad_filter=True`, `beam_size=1` ради скорости
- `OpenAITranscriber`: `whisper-1`, таймаут 30 с
- `FakeTranscriber`: возвращает текст или падает — для тестов
- `build_transcriber(settings)` — фабрика по `TRANSCRIBER`

## 5.2 `ai/extractor.py`

```python
class Extractor(Protocol):
    async def extract(self, text: str, now: datetime) -> TaskDraft: ...
```
- `RulesExtractor`: `#теги` → tags; `срочно|urgent|asap|!!` → urgent, `важно|important` → high; `dateparser.search.search_dates` (ru/en, `TIMEZONE=APP_TZ`, `RETURN_AS_TIMEZONE_AWARE`, `PREFER_DATES_FROM=future`) → `due_at`; из title вырезаются распознанные фрагменты, первая буква заглавная, до 120 символов
- `LLMExtractor`: OpenAI structured output по схеме `TaskDraft`; при ошибке или таймауте → fallback на правила
- Применяется и к тексту, и к голосу

## 5.3 Голос в боте

1. Проверка: `duration > VOICE_MAX_SEC` → вежливый отказ, в очередь не ставим
2. **Сразу** ответ «🎤 Распознаю…» — запоминаем его `message_id`
3. `tasks.create(source=voice, title="🎤 Голосовое…", transcription_status=queued, tg_file_id, tg_message_id=ack.id)`
4. `enqueue_transcription(task.id, attempt=1)`
5. Redis недоступен → ACK редактируется на «Сервис перегружен, попробуй позже»; задача остаётся `queued`, её подберёт reconciler

💡 Бот ничего не скачивает: ACK уходит меньше чем за секунду. Это и есть критерий «UX: speed of transcription feedback».

## 5.4 Worker — `worker/transcription.py`

`WorkerSettings`: `queue_name="transcription"`, `max_jobs=1`, `max_tries=3`, `job_timeout=120`, `keep_result=0`, `on_startup` → транскрайбер (прогрев модели), engine, `Bot`; `cron_jobs=[reconcile]` раз в минуту.

Джоба `transcribe(ctx, task_id)`:
1. Если задача уже `done` → выход (идемпотентность)
2. status → `processing`, publish `task.updated`
3. `bot.download(tg_file_id)` в память → `asyncio.wait_for(transcriber.transcribe(audio), 90)`
4. `extract` → обновить title/due/priority/tags/raw_text/language/`transcription_ms`
5. status → `done`, `TaskEvent`, publish, `enqueue_notification(edit ACK → «✅ #id: title\n📝 транскрипт»)`
6. Ошибка: если `ctx["job_try"] < max_tries` → `Retry(defer=2**job_try)`; иначе `failed` + `transcription_error` + `TaskEvent` + publish + notify «❌ Не смог распознать. Повтори в дашборде или пришли текстом»

⚠️ `job_timeout` в arq отменяет корутину, и на последней попытке обработчик отказа не выполнится — задача зависнет в `processing`. Поэтому внутренний `wait_for(90)` меньше `job_timeout(120)`: таймаут становится обычным исключением, которое мы обрабатываем.
⚠️ Поток в `to_thread` отменить нельзя, по таймауту он дорабатывает в фоне. При `max_jobs=1` это ограниченный и приемлемый расход.

**Reconciler** `reconcile(ctx)`: задачи в `queued`/`processing` с `updated_at` старше 5 минут → `transcription_attempt += 1`, enqueue с новым attempt; после 3 таких попыток → `failed`.
💡 Лечит dual-write: если процесс упал между `COMMIT` и `enqueue` или воркер был убит посреди джобы, задача не зависнет навсегда. Transactional outbox для такого объёма — перебор.

**Ручной retry:** `POST /api/tasks/{id}/retry` (только для `failed`) → `queued`, `attempt += 1`, enqueue. Файл заново скачивается по `tg_file_id`.

## 5.5 Тесты

- `RulesExtractor`: «Купить молоко завтра в 10, срочно #дом» → urgent, tags=[дом], due=завтра 10:00 Asia/Yerevan, title=«Купить молоко»
- Джоба с падающим `FakeTranscriber`: попытки 1–2 → `Retry`, попытка 3 → `failed` + notify
- Джоба с зависающим Fake → таймаут обработан как ошибка, а не как отмена
- Успешная джоба → `done`, поля заполнены; повторный запуск → no-op
- Reconciler подбирает задачу, застрявшую в `queued`

✅ **DoD:** голосовое → мгновенный ACK → через 2–5 с сообщение заменяется результатом.
🔍 отправить голосовое и выполнить `docker compose logs worker --tail 20` (видно `transcription_ms`)
Коммит: `Add voice transcription pipeline`

---

# ФАЗА 6 — Realtime

## 6.1 `services/events.py`

`publish(redis, user_id, type, task)` → `PUBLISH events:user:{id}` с JSON `{type, task}`. Вызывается из `services/tasks` после каждого commit и из воркера.
💡 Publish строго после commit, иначе клиент может получить событие о записи, которой ещё нет в БД.

## 6.2 `GET /api/events`

Аутентификация той же cookie → `StreamingResponse(text/event-stream)`: subscribe на канал пользователя, `event: <type>\ndata: <json>\n\n`, keep-alive `: ping` каждые 15 с, при отключении клиента — unsubscribe в `finally`.
💡 Один origin + cookie: `EventSource` отправляет её сам, никаких тикетов.
⚠️ Без keep-alive промежуточные прокси закрывают «молчащее» соединение.
Известный предел: одна Redis-подписка на соединение. Для тестового нормально; при росте — один `PSUBSCRIBE` на процесс и раздача по in-memory очередям (в README).

## 6.3 Уведомление о смене статуса

`PATCH` с изменением `status` → `enqueue_notification(«🔄 #id → Completed»)`. Замыкает omni-channel: изменения в вебе видны в Telegram.

✅ **DoD:** тест: POST задачи → в SSE-потоке приходит `task.created`.
🔍 `curl -N -b "session=$JWT" localhost:8000/api/events` + создать задачу в боте
Коммит: `Add realtime events over SSE`

---

# ФАЗА 7 — Дашборд

## 7.1 Слои фронта

Без роутера и стейт-менеджера: для двух экранов достаточно `App` и хуков. Tailwind, `@dnd-kit/core`.

- `api.ts` — `fetch`-обёртка: base `/api`, `credentials: "same-origin"`, на 401 → экран «войди через /login в боте»
- `types.ts` — `Task`, `Status`, `Priority` (зеркало `TaskOut`)
- `hooks/useAuth` — `/login?token=` → `exchange` → `history.replaceState` (убрать токен из URL) → `me`
- `hooks/useTasks` — загрузка списка, `updateStatus` с **оптимистичным обновлением и откатом** при ошибке, `retry(id)`, `applyEvent(e)`
- `hooks/useEventStream` — `EventSource("/api/events")`; при `onerror` → закрыть, backoff 1/2/5/10 с, после реконнекта **refetch списка**; состояние `connected | reconnecting`
- `components/Board` → 3 × `Column` → `TaskCard`: title, priority-бейдж, due, иконка источника; у голоса — «распознаётся…», транскрипт под спойлером или `failed` с кнопкой «Повторить»; drag между колонками = смена статуса; кнопки статуса на карточке для мобильных
- шапка: счётчики, индикатор соединения, logout

💡 Refetch после реконнекта проще и надёжнее, чем replay событий.

## 7.2 nginx для SSE

В `nginx.conf` для `/api/events`: `proxy_buffering off`, `proxy_read_timeout 1h`, `proxy_http_version 1.1`, `proxy_set_header Connection ''`. Для SPA: `try_files $uri /index.html`; статика с `immutable`, `index.html` — no-cache.
⚠️ Без `proxy_buffering off` nginx копит события в буфере, и realtime «не работает», хотя curl напрямую к api работает.

✅ **DoD:** `localhost:8080` → текст и голос в боте появляются на доске без F5 → перетаскивание в Completed → сообщение в Telegram → failed-карточка по «Повторить» уходит в распознавание.
🔍 ручной прогон + `npm run lint && npm run build`
Коммит: `Add Kanban dashboard with realtime updates`

---

# ФАЗА 8 — CI, README, приёмка

## 8.1 `.github/workflows/ci.yml`

- `lint`: ruff check + format --check + mypy; eslint + `tsc --noEmit`
- `test`: services postgres и redis, `pytest --junitxml --cov`, артефакт junit
- `build`: `docker build` всех target'ов с build-args (без push)
- `gitleaks`: `fetch-depth: 0`

Кэш по `uv.lock` и `package-lock.json`. Никакого `continue-on-error`.

## 8.2 README

1. Что это (2 строки) + GIF демо
2. **Матрица «требование ТЗ → где реализовано»** (каждый пункт ТЗ → файл/сервис)
3. Архитектура: mermaid-диаграмма + «модульный монолит с 4 точками входа»
4. Quickstart из 3 команд, env-таблица
5. Голосовой пайплайн и resilience: ACK, retries, внутренний таймаут, reconciler, ручной retry
6. Таблица решений из 0.2
7. Ограничения и как масштабировать: бот → webhook, worker → реплики, SSE → общий `PSUBSCRIBE`, dual-write → outbox

## 8.3 Финальная приёмка

- [ ] `git clone` в чистую папку → `cp .env.example .env` → вписать токен → `make up` → всё healthy
- [ ] E2E-сценарий из DoD 7
- [ ] `docker compose stop redis` → бот отвечает «перегружен», не падает; `start` → reconciler дорабатывает задачи
- [ ] `docker compose restart postgres` → api и worker переподключаются сами
- [ ] `docker compose kill worker` посреди джобы → после старта reconciler перезапускает задачу
- [ ] Размеры образов: app < 400 МБ (python:3.12-slim + venv; alpine отклонён — риск долгой пересборки wheel'ов asyncpg/pydantic-core под musl), worker < 1.2 ГБ, web < 60 МБ
- [ ] CI зелёный, `pre-commit run -a` зелёный

Коммиты: `Add CI pipeline`, `Add README`
