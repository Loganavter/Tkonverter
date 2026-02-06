import re
from typing import Dict, List, Optional
from urllib.parse import urlparse
from src.core.domain.anonymization import AnonymizationConfig, LinkFilterType, LinkMaskMode
from src.resources.translations import tr
class AnonymizerService:
    def __init__(self, config: AnonymizationConfig):
        """
        Инициализация сервиса анонимизации.
        Для регистрации пользователей используйте register_user() перед обработкой.
        """
        self.config = config

        self._id_to_index: Dict[str, int] = {}

        self._norm_name_to_index: Dict[str, int] = {}

        self._username_to_index: Dict[str, int] = {}
        self._next_index = 1

        self._url_to_index: Dict[str, int] = {}
        self._next_url_index = 1

        self._url_regex = re.compile(r'(https?://\S+|www\.\S+)')

        self._mention_pattern = re.compile(r'@([a-zA-Z0-9_]{5,32})')

        self._names_regex = None

        self._excluded_names = set()
        if self.config.custom_names:
            for item in self.config.custom_names:
                val = item.get("value", "").strip()
                if not val:
                    continue

                norm_val = self._normalize_name(val)

                if item.get("enabled", True):

                    if norm_val not in self._norm_name_to_index:
                        self.register_user(name=val)
                else:

                    if norm_val:
                        self._excluded_names.add(norm_val)

    def _normalize_name(self, name: str) -> str:
        """
        Удаляет эмодзи, спецсимволы и приводит к нижнему регистру для сравнения.
        Это поможет связать 'Глеб' и 'Глеб 🔥'.
        """
        if not name:
            return ""

        clean = re.sub(r'[^\w\s]', '', name).strip().lower()
        return clean if clean else name.strip().lower()

    def register_user(self, user_id: str = None, name: str = None):
        """
        Главный метод связывания. Вызывается при пред-сканировании.
        Регистрирует пользователя и ищет юзернеймы внутри его имени
        (например "Иван @ivan2000").
        """
        if not user_id and not name:
            return

        index = None
        norm_name = self._normalize_name(name) if name else None

        if user_id and user_id in self._id_to_index:
            index = self._id_to_index[user_id]
        elif norm_name and norm_name in self._norm_name_to_index:
            index = self._norm_name_to_index[norm_name]

        usernames_in_name = []
        if name:
            usernames_in_name = self._mention_pattern.findall(name)
            for uname in usernames_in_name:
                u_key = uname.lower()
                if u_key in self._username_to_index:
                    index = self._username_to_index[u_key]
                    break

        if index is None:
            index = self._next_index
            self._next_index += 1

        if user_id:
            self._id_to_index[user_id] = index
        if norm_name:
            self._norm_name_to_index[norm_name] = index
        for uname in usernames_in_name:
            self._username_to_index[uname.lower()] = index

    def _rebuild_names_regex(self):
        """Пересобирает regex для поиска имен в тексте после регистрации новых пользователей."""
        if not self.config.hide_names:
            return

        all_name_parts = set()

        for name in self._norm_name_to_index.keys():
            parts = [p for p in re.split(r'\s+', name) if len(p) > 2]
            for part in parts:
                all_name_parts.add(re.escape(part))

        if all_name_parts:
            pattern_str = '|'.join(sorted(list(all_name_parts), key=len, reverse=True))
            self._names_regex = re.compile(fr'\b({pattern_str})\b', re.IGNORECASE)
        else:
            self._names_regex = None

    def process_text(self, text: str) -> str:
        """Обрабатывает текст, применяя правила анонимизации."""
        if not self.config.enabled:
            return text

        result = text
        if self.config.hide_links:
            result = self._anonymize_links(result)

        if self.config.hide_names:
            result = self._process_mentions(result)

            if self._names_regex:

                result = self._names_regex.sub(self._replace_name_match, result)

        return result

    def _replace_name_match(self, match) -> str:
        """Callback для regex.sub."""
        found_text = match.group(0)
        norm_name = self._normalize_name(found_text)

        if norm_name in self._excluded_names:
            return found_text

        idx = self._norm_name_to_index.get(norm_name)
        if idx is None:
            return self.config.name_mask_format.format(index="?")

        return self.config.name_mask_format.format(index=idx)

    def _process_mentions(self, text: str) -> str:
        """Заменяет @username на [ИМЯ X]"""
        def replace(match):
            username = match.group(1)
            key = username.lower()

            if key in self._username_to_index:
                idx = self._username_to_index[key]
            else:

                idx = self._next_index
                self._next_index += 1
                self._username_to_index[key] = idx

            return self.config.name_mask_format.format(index=idx)

        return self._mention_pattern.sub(replace, text)

    def get_anonymized_name(self, user_id: str, original_name: str) -> str:
        """Для сообщений с ID."""
        if not self.config.enabled or not self.config.hide_names:
            return original_name

        norm_name = self._normalize_name(original_name)
        if norm_name in self._excluded_names:
            return original_name

        if user_id in self._id_to_index:
            idx = self._id_to_index[user_id]
        else:
            if norm_name in self._norm_name_to_index:
                idx = self._norm_name_to_index[norm_name]
            else:
                self.register_user(user_id, original_name)
                idx = self._id_to_index.get(user_id, self._next_index - 1)
        return self.config.name_mask_format.format(index=idx)

    def anonymize_string_name(self, name: str) -> str:
        """Для строк без ID (truncate_name)."""
        if not self.config.enabled or not self.config.hide_names or not name:
            return name

        norm_name = self._normalize_name(name)

        if norm_name in self._excluded_names:
            return name

        if norm_name in self._norm_name_to_index:
            idx = self._norm_name_to_index[norm_name]
            return self.config.name_mask_format.format(index=idx)

        return name

    def _should_hide_link(self, url: str) -> bool:
        """Проверяет, нужно ли скрывать ссылку по фильтрам."""
        filters = self.config.custom_filters + \
                  (self.config.active_preset.filters if self.config.active_preset else [])
        if not filters:
            return True

        for f in filters:
            if not f.enabled:
                continue

            if f.type == LinkFilterType.ALL:
                return True
            elif f.type == LinkFilterType.DOMAIN:
                if f.value.lower() in url.lower():
                    return True
            elif f.type == LinkFilterType.REGEX:
                try:
                    if re.search(f.value, url):
                        return True
                except re.error:
                    pass
        return False

    def _anonymize_links(self, text: str) -> str:
        """Заменяет ссылки согласно активным фильтрам и режиму маскировки."""

        def replace_match(match):
            url = match.group(0)

            should_hide = self._should_hide_link(url)
            if not should_hide:
                return url

            mode = self.config.link_mask_mode

            if mode == LinkMaskMode.SIMPLE:
                return tr("[ССЫЛКА СКРЫТА]")

            elif mode == LinkMaskMode.DOMAIN_ONLY:
                try:
                    parsed = urlparse(url if "://" in url else "http://" + url)
                    domain = parsed.netloc.replace("www.", "")
                    return f"{domain}/[...]"
                except:
                    return "[URL/[...]]"

            elif mode == LinkMaskMode.INDEXED:
                if url not in self._url_to_index:
                    self._url_to_index[url] = self._next_url_index
                    self._next_url_index += 1
                return self.config.link_mask_format.format(index=self._url_to_index[url])

            elif mode == LinkMaskMode.CUSTOM:

                if "{index}" in self.config.link_mask_format:
                    if url not in self._url_to_index:
                        self._url_to_index[url] = self._next_url_index
                        self._next_url_index += 1
                    return self.config.link_mask_format.format(index=self._url_to_index[url])
                return self.config.link_mask_format

            return tr("[ССЫЛКА СКРЫТА]")

        return self._url_regex.sub(replace_match, text)

    def extract_unique_domains(self, chat) -> List[str]:
        """Сканирует чат и возвращает список уникальных доменов из ссылок."""
        if not chat or not chat.messages:
            return []

        domains = set()

        regex = self._url_regex

        for msg in chat.messages:
            text_sources = []

            if hasattr(msg, 'text'):
                if isinstance(msg.text, str):
                    text_sources.append(msg.text)
                elif isinstance(msg.text, list):
                    for item in msg.text:
                        if isinstance(item, str):
                            text_sources.append(item)
                        elif isinstance(item, dict):
                            text_sources.append(item.get("text", ""))

                            if item.get("type") == "text_link" and "href" in item:
                                text_sources.append(item["href"])

            full_text_to_scan = " ".join(text_sources)

            if not full_text_to_scan:
                continue

            found_urls = regex.findall(full_text_to_scan)
            for url in found_urls:

                if not url.startswith(('http://', 'https://')):
                    url = 'http://' + url

                try:
                    parsed = urlparse(url)
                    domain = parsed.netloc

                    if domain.startswith("www."):
                        domain = domain[4:]

                    if domain:
                        domains.add(domain)
                except Exception:
                    continue

        return sorted(list(domains))

    def reset(self):
        """Сбрасывает состояние сервиса (например, карту пользователей)."""
        self._id_to_index.clear()
        self._norm_name_to_index.clear()
        self._username_to_index.clear()
        self._next_index = 1
        self._url_to_index.clear()
        self._next_url_index = 1
        self._names_regex = None
