

from __future__ import annotations

import copy
import re
import uuid
from dataclasses import replace
from typing import Any, Dict, Iterable, List
from urllib.parse import urlparse

from src.core.domain.models import Chat, Message, Reaction, ServiceMessage, User

URL_PATTERN = re.compile(r"(https?://[^\s]+|www\.[^\s]+)")

class AnonymizerService:

    def get_default_presets(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "default",
                "name": "Default",
                "name_template": "User {index}",
                "link_placeholder": "<link>",
                "chat_name_placeholder": "Anonymized chat",
            }
        ]

    def create_preset(
        self,
        name: str,
        name_template: str = "User {index}",
        link_placeholder: str = "<link>",
        chat_name_placeholder: str = "Anonymized chat",
    ) -> Dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "name": name.strip() or "Preset",
            "name_template": name_template,
            "link_placeholder": link_placeholder,
            "chat_name_placeholder": chat_name_placeholder,
        }

    def normalize_presets(self, presets: Iterable[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
        defaults = self.get_default_presets()
        if not presets:
            return defaults

        normalized: List[Dict[str, str]] = []
        for preset in presets:
            preset_id = str(preset.get("id", "")).strip() or str(uuid.uuid4())
            normalized_preset: Dict[str, Any] = {
                "id": preset_id,
                "name": str(preset.get("name", "Preset")).strip() or "Preset",
                "name_template": str(
                    preset.get("name_template", "User {index}")
                ).strip()
                or "User {index}",
                "link_placeholder": str(
                    preset.get("link_placeholder", "<link>")
                ).strip()
                or "<link>",
                "chat_name_placeholder": str(
                    preset.get("chat_name_placeholder", "Anonymized chat")
                ).strip()
                or "Anonymized chat",
            }

            if "hide_links" in preset:
                normalized_preset["hide_links"] = bool(preset.get("hide_links"))
            if "hide_names" in preset:
                normalized_preset["hide_names"] = bool(preset.get("hide_names"))
            if "name_mask_format" in preset:
                normalized_preset["name_mask_format"] = (
                    str(preset.get("name_mask_format", "")).strip() or "[ИМЯ {index}]"
                )
            if "link_mask_mode" in preset:
                normalized_preset["link_mask_mode"] = (
                    str(preset.get("link_mask_mode", "")).strip() or "simple"
                )
            if "link_mask_format" in preset:
                normalized_preset["link_mask_format"] = (
                    str(preset.get("link_mask_format", "")).strip() or "[ССЫЛКА {index}]"
                )
            if "custom_filters" in preset:
                normalized_preset["custom_filters"] = list(preset.get("custom_filters") or [])
            if "custom_names" in preset:
                normalized_preset["custom_names"] = list(preset.get("custom_names") or [])

            normalized.append(normalized_preset)
        return normalized or defaults

    def get_preset_by_id(
        self, presets: Iterable[Dict[str, Any]] | None, preset_id: str | None
    ) -> Dict[str, Any]:
        if preset_id == "default":
            return dict(self.get_default_presets()[0])
        normalized = self.normalize_presets(presets)
        if preset_id:
            for preset in normalized:
                if preset["id"] == preset_id:
                    return preset
        return normalized[0]

    def anonymize_chat(self, chat: Chat, preset: Dict[str, Any]) -> Chat:
        link_placeholder = str(preset.get("link_placeholder", "<link>"))
        name_template = str(preset.get("name_template", "User {index}"))
        chat_name_placeholder = str(
            preset.get("chat_name_placeholder", "Anonymized chat")
        )

        name_map: Dict[str, str] = {}

        def to_alias(original_name: str) -> str:
            original_key = (original_name or "").strip()
            if not original_key:
                return "User"
            if original_key not in name_map:
                alias_index = len(name_map) + 1
                name_map[original_key] = name_template.format(index=alias_index)
            return name_map[original_key]

        anonymized_messages = []
        for msg in chat.messages:
            if isinstance(msg, Message):
                anonymized_messages.append(
                    self._anonymize_regular_message(msg, to_alias, link_placeholder)
                )
            elif isinstance(msg, ServiceMessage):
                anonymized_messages.append(self._anonymize_service_message(msg, to_alias))
            else:
                anonymized_messages.append(copy.deepcopy(msg))

        return Chat(
            name=chat_name_placeholder or chat.name,
            type=chat.type,
            messages=anonymized_messages,
        )

    def anonymize_text(self, text: str, link_placeholder: str = "<link>") -> str:
        return URL_PATTERN.sub(link_placeholder, text or "")

    def extract_unique_domains(self, chat: Chat) -> List[str]:
        if not chat or not getattr(chat, "messages", None):
            return []

        seen: set[str] = set()
        domains: List[str] = []
        for msg in chat.messages:
            for domain in self._extract_domains_from_text_data(getattr(msg, "text", None)):
                if domain and domain not in seen:
                    seen.add(domain)
                    domains.append(domain)
        return domains

    def _anonymize_regular_message(
        self,
        message: Message,
        alias_factory,
        link_placeholder: str,
    ) -> Message:
        anonymized_author = replace(message.author, name=alias_factory(message.author.name))

        anonymized_reactions: List[Reaction] = []
        for reaction in message.reactions:
            anonymized_authors = [
                replace(author, name=alias_factory(author.name)) for author in reaction.authors
            ]
            anonymized_reactions.append(replace(reaction, authors=anonymized_authors))

        anonymized_forwarded_from = (
            alias_factory(message.forwarded_from) if message.forwarded_from else None
        )

        anonymized_text = self._anonymize_text_data(message.text, link_placeholder)

        return replace(
            message,
            author=anonymized_author,
            reactions=anonymized_reactions,
            forwarded_from=anonymized_forwarded_from,
            text=anonymized_text,
        )

    def _anonymize_service_message(self, message: ServiceMessage, alias_factory) -> ServiceMessage:
        anonymized_actor = alias_factory(message.actor) if message.actor else None
        anonymized_members = [alias_factory(member) for member in message.members]
        return replace(message, actor=anonymized_actor, members=anonymized_members)

    def _anonymize_text_data(self, text_data: Any, link_placeholder: str) -> Any:
        if isinstance(text_data, str):
            return self.anonymize_text(text_data, link_placeholder)

        if not isinstance(text_data, list):
            return text_data

        sanitized: List[Any] = []
        for item in text_data:
            if isinstance(item, str):
                sanitized.append(self.anonymize_text(item, link_placeholder))
                continue

            if isinstance(item, dict):
                item_copy = dict(item)
                item_type = item_copy.get("type")
                text_value = item_copy.get("text")
                if isinstance(text_value, str):
                    item_copy["text"] = self.anonymize_text(text_value, link_placeholder)
                if item_type == "text_link":
                    item_copy["href"] = link_placeholder
                sanitized.append(item_copy)
                continue

            sanitized.append(item)

        return sanitized

    def _extract_domains_from_text_data(self, text_data: Any) -> List[str]:
        if isinstance(text_data, str):
            return self._extract_domains_from_text(text_data)

        if not isinstance(text_data, list):
            return []

        domains: List[str] = []
        for item in text_data:
            if isinstance(item, str):
                domains.extend(self._extract_domains_from_text(item))
                continue
            if isinstance(item, dict):
                text_value = item.get("text")
                if isinstance(text_value, str):
                    domains.extend(self._extract_domains_from_text(text_value))
                href_value = item.get("href")
                if isinstance(href_value, str):
                    domains.extend(self._extract_domains_from_text(href_value))
        return domains

    def _extract_domains_from_text(self, text: str) -> List[str]:
        if not text:
            return []

        domains: List[str] = []
        for raw_url in URL_PATTERN.findall(text):
            candidate_url = raw_url if raw_url.startswith(("http://", "https://")) else f"http://{raw_url}"
            parsed = urlparse(candidate_url)
            host = (parsed.netloc or "").strip().lower()
            if host.startswith("www."):
                host = host[4:]
            if host:
                domains.append(host)
        return domains
