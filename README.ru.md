<p align="center">
  <img src="https://raw.githubusercontent.com/Loganavter/media_archive/1.5.1/Tkonverter/icons/logo.png" alt="Logo" width="100">
</p>

<p align="center">
  <strong>Инструмент с открытым исходным кодом для конвертации и анализа экспортированных чатов Telegram.</strong>
</p>

<p align="center">
  <a href="https://github.com/Loganavter/Tkonverter/releases/latest">
    <img src="https://img.shields.io/github/v/release/Loganavter/Tkonverter?style=flat-square&label=последний%20релиз">
  </a>
  <a href="LICENSE.txt">
    <img src="https://img.shields.io/github/license/Loganavter/Tkonverter?style=flat-square">
  </a>
  <a href="https://github.com/Loganavter/Tkonverter/issues">
    <img src="https://img.shields.io/github/issues/Loganavter/Tkonverter?style=flat-square">
  </a>
</p>

<p align="center">
  Читать на других языках:
  <a href="readme.md">English</a>
</p>

---

## 📸 Предпросмотр

<div align="center">
  <img src="https://raw.githubusercontent.com/Loganavter/media_archive/1.5.2/Tkonverter/screenshots/screenshot_2.png" width="24%">
  <img src="https://raw.githubusercontent.com/Loganavter/media_archive/1.5.2/Tkonverter/screenshots/screenshot_1.png" width="50%">
  <img src="https://raw.githubusercontent.com/Loganavter/media_archive/1.5.2/Tkonverter/screenshots/screenshot_3.png" width="24%">
</div>

---

## 🧭 Быстрые ссылки

- Установка и запуск из исходников: <a href="docs/INSTALL.md">docs/INSTALL.md</a>
- CLI документация: <a href="docs/CLI.md">docs/CLI.md</a>
- Изучить приложение (Справка): <a href="src/resources/help/ru/introduction.md">RU Введение</a> • <a href="src/resources/help/ru/">RU Все разделы</a> • <a href="src/resources/help/en/">EN Docs</a>
- Внести вклад: <a href="CONTRIBUTING.md">CONTRIBUTING.md</a>
- Ещё: <a href="HISTORY.md">История разработки</a> • <a href="VISION.md">Взгляд автора</a>

---

## 🧩 Обзор

Tkonverter — это бесплатное приложение с открытым исходным кодом, предназначенное для конвертации больших JSON-экспортов Telegram в чистый формат `.txt`.

Проект изначально был создан для предобработки данных чатов для использования с большими языковыми моделями (LLM), такими как Gemini. Его функции сосредоточены на эффективном управлении контекстными окнами LLM — либо путем сжатия информации (например, сокращение цитат, обрезание имён) для экономии токенов, либо её обогащения (например, включение реакций, опросов, Markdown) для более качественного анализа.

Хотя основная цель — предобработка для LLM, это универсальный инструмент, который может быть полезен для любых задач архивирования или анализа чатов.

---

## 🚀 Ключевые возможности

### 🔄 Продвинутая конвертация и управление контекстом
- **Гибкие профили**: Поддерживает групповые чаты, личные беседы, каналы и посты. Приложение автоматически определяет правильный профиль в большинстве случаев.
- **Инструменты экономии контекста**: Уменьшите количество токенов с помощью опций автоматического сокращения цитат в ответах и обрезания длинных имён пользователей.
- **Богатые опции контекста**: Выберите включение детальной информации, такой как реакции, результаты опросов, ссылки и полное форматирование Markdown для наивысшего качества входных данных.
- **Точный контроль**: Переключайте видимость временных меток, служебных сообщений и технической информации.
- **Модуль анонимизации**: Перед передачей чата в LLM или третьим лицам можно анонимизировать имена и ссылки: замена имён на маски (например `[ИМЯ 1]` или `User 1`), скрытие или замена URL (один плейсхолдер, только домен или нумерованные ссылки), пресеты и фильтры по доменам/регулярным выражениям. Настраивается через GUI или JSON-конфиг для CLI.

### 📊 Аналитика для предобработки LLM
- **Подсчёт токенов и символов**: Вычислите точное количество токенов (используя токенизаторы Hugging Face) или символов, чтобы понять, как выбор форматирования влияет на итоговый размер данных.
- **Интерактивная диаграмма**: Визуализируйте объём сообщений во времени с помощью sunburst-диаграммы, вдохновлённой KDE Filelight.
- **Фильтрация данных**: Исключите нерелевантные временные периоды из экспорта, кликая по сегментам диаграммы, что позволяет уточнить контекст, отправляемый модели.

### 🤖 Опциональная интеграция с ИИ
- **Поддержка Hugging Face**: Для точного анализа токенов, специфичного для модели.
- **Встроенный установщик**: Установите необходимые Python-библиотеки (`transformers`, `huggingface_hub`) и загрузите модели прямо из UI — терминал не нужен.

### 🧑‍💻 Пользовательский опыт и инструменты
- **Кроссплатформенность**: Построен на Python и PyQt6.
- **Темы**: Поддерживает светлый и тёмный режимы с автоматическим определением системной темы.
- **Мощный лаунчер**: Скрипт `launcher.sh` упрощает управление зависимостями в виртуальном окружении, запуск и отладку.
- **CLI интерфейс**: Полнофункциональный командный интерфейс для автоматизации и интеграции в скрипты.

---

## 🛠 Установка

В настоящее время основной метод установки — запуск из исходного кода.

### 🐍 Из исходников (Linux/macOS)
Скрипт `launcher.sh` автоматически создаст виртуальное окружение и установит зависимости из `requirements-gui.txt`.
```bash
git clone https://github.com/Loganavter/Tkonverter.git
cd Tkonverter
chmod +x launcher.sh
./launcher.sh run
```
Используйте `./launcher.sh --help` для полного списка команд (включая `recreate`, `delete`, `profile`). Зависимости: `requirements-gui.txt` — для GUI и CLI из репозитория; `requirements-cli.txt` — только CLI (без PyQt, например на сервере). Подробнее: [docs/INSTALL.md](docs/INSTALL.md).

### 🪟 Windows, 🐧 Linux, 🍏 macOS
Установщики и пакеты дистрибуции планируются на будущее. Вклады приветствуются!

---

## 🧪 Использование

### Графический интерфейс
1.  **Запустите** приложение: `./launcher.sh run`.
2.  **Перетащите** ваш файл `result.json` (из экспорта Telegram) в окно приложения.
3.  **Настройте** параметры форматирования на левой панели.
4.  **(Опционально)** Откройте **«Анонимизация»**, чтобы скрыть или замаскировать имена и ссылки перед экспортом.
5.  **(Опционально)** Нажмите **"Пересчитать"** для анализа токенов и откройте диаграмму для визуализации.
6.  **Нажмите** **"Сохранить в файл..."** для экспорта результата в виде `.txt` файла.

### Командная строка (CLI)
```bash
# Простая конвертация
./tkonverter-cli.sh convert -i result.json -o output.txt

# Конвертация с настройками
./tkonverter-cli.sh convert -i result.json -o output.txt --profile personal --no-time

# Анализ статистики
./tkonverter-cli.sh analyze -i result.json --chars-only

# Информация о файле
./tkonverter-cli.sh info -i result.json --detailed

# Справка по командам
./tkonverter-cli.sh --help
./tkonverter-cli.sh convert --help
```

---

## 🤝 Вклад

Спасибо за ваш интерес к проекту! Пожалуйста, ознакомьтесь с <a href="CONTRIBUTING.md">CONTRIBUTING.md</a> для настройки окружения разработки и правил оформления PR. Сообщайте о проблемах и предлагайте изменения через Issues/PRs на GitHub.

---

## 📄 Лицензия

Этот проект лицензирован под MIT License. См. <a href="LICENSE.txt">LICENSE.txt</a>.

---

## ⭐ История звёзд

![Star History Chart](https://api.star-history.com/svg?repos=Loganavter/Tkonverter&type=Timeline)

## Telegram-бот Tkonverter (монорепо)

Функциональность (MVP):
- Приём JSON-экспорта Telegram (Document)
- Конвертация в текст/HTML через ядро (без GPU/токенизатора)
- Базовая аналитика по символам с фильтрами по датам
- Ограничения: вход до 20 МБ, выход до 6 МБ

Структура и точка входа:
- Каркас бота: каталог `bot/`
  - Точка входа: `python -m bot.main`
  - Основные файлы:
    - `bot/main.py` — запуск long polling, регистрация команд
    - `bot/handlers/convert.py` — загрузка JSON и команда `/convert`
    - `bot/handlers/analyze.py` — команда `/analyze` (символьная аналитика)
    - `bot/services/integration.py` — DI и интеграция с ядром
    - `bot/services/state.py` — состояние пользователя и каталоги
    - `bot/config.py` — ENV, лимиты, парсинг параметров
    - `bot/requirements.txt` — зависимости бота (без GUI)

Требования и переменные окружения:
- Python 3.10+
- TELEGRAM_BOT_TOKEN — токен вашего бота (обязательно)
- MAX_UPLOAD_MB — лимит входного файла (по умолчанию 20)
- MAX_OUTPUT_MB — лимит веса результата (по умолчанию 6)
- TZ — часовой пояс (по умолчанию Europe/Moscow)
- DEBUG — 1/true для подробных логов

Установка зависимостей (только для бота):
```
pip install -r bot/requirements.txt
```

Локальный запуск:
```
export TELEGRAM_BOT_TOKEN="ваш_токен"
export MAX_UPLOAD_MB=20
export MAX_OUTPUT_MB=6
python -m bot.main
```

Использование в чате:
1) Отправьте JSON экспорт чата как документ (файл .json).
2) Выполните
   - `/convert html=1 from=2023-01-01 to=2023-12-31 exclude=2023-03-08,2023-05-09 profile=group`
     - Параметры:
       - `html=1|0` — HTML или Text
       - `from=YYYY-MM-DD` — нижняя граница даты
       - `to=YYYY-MM-DD` — верхняя граница даты
       - `exclude=YYYY-MM-DD[,YYYY-MM-DD...]` — исключаемые даты
       - `profile=group|personal|posts|channel`
   - `/analyze from=2024-01-01 exclude=2024-03-08,2024-05-09`
     - Возвращает сводку + JSON (если итог не превышает 6 МБ)

Обработка ограничений:
- Если входной файл > 20 МБ — отклоняется до скачивания
- Если результат > 6 МБ — бот предложит сузить диапазон дат/исключить дни

Деплой на Railway (long polling):
1) Импортируйте репозиторий в Railway
2) В настройках сервиса:
   - Укажите команду запуска: `python -m bot.main`
   - Добавьте ENV:
     - `TELEGRAM_BOT_TOKEN`, `MAX_UPLOAD_MB=20`, `MAX_OUTPUT_MB=6`, `TZ=Europe/Moscow`, `DEBUG=0`
   - Для корректной установки зависимостей из `bot/requirements.txt` в монорепо:
     - Установите переменную сборки `NIXPACKS_PYTHON_ROOT=bot`
3) Запустите сервис и проверьте логи

Деплой на Fly.io (вариант):
- Используйте Docker-образ Python (например, python:3.11-slim), установите `bot/requirements.txt`, запускайте `python -m bot.main`
- Проброс портов и HTTP не требуется (long polling)

Ограничения и примечания:
- Бот не использует токенизатор/модели — анализ по символам
- Поддерживается только JSON-экспорт (ZIP можно добавить позже)
- Язык интерфейса: русский
- Для больших чатов рекомендуется фильтровать по датам или месяцам
