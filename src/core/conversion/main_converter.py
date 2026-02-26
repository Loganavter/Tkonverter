import logging
import re
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse

from src.core.conversion.context import ConversionContext

logger = logging.getLogger(__name__)
from src.core.conversion.formatters.service_formatter import format_service_message
from src.core.conversion.message_formatter import format_message
from src.core.conversion.utils import format_date_separator
from src.core.domain.anonymization import (
    AnonymizationConfig,
    FilterPreset,
    LinkFilter,
    LinkFilterType,
    LinkMaskMode,
)
from src.resources.translations import tr

class _LegacyAnonymizerAdapter:

    _url_regex = re.compile(r"(https?://\S+|www\.\S+)")
    _mention_regex = re.compile(r"@([a-zA-Z0-9_]{3,32})")

    def __init__(self, config: AnonymizationConfig):
        self.config = config
        self._id_to_index: dict[str, int] = {}
        self._name_to_index: dict[str, int] = {}
        self._next_index = 1
        self._url_to_index: dict[str, int] = {}
        self._next_url_index = 1
        self._names_regex = None

    def _normalize_name(self, name: str | None) -> str:
        if not name:
            return ""
        return re.sub(r"[^\w\s]", "", name).strip().lower()

    def register_user(self, user_id: str | None = None, name: str | None = None):
        if not user_id and not name:
            return

        index = None
        normalized = self._normalize_name(name)
        if user_id and user_id in self._id_to_index:
            index = self._id_to_index[user_id]
        elif normalized and normalized in self._name_to_index:
            index = self._name_to_index[normalized]

        if index is None:
            index = self._next_index
            self._next_index += 1

        if user_id:
            self._id_to_index[user_id] = index
        if normalized:
            self._name_to_index[normalized] = index

    def _format_name(self, index: int) -> str:
        return self.config.name_mask_format.format(index=index)

    def anonymize_string_name(self, name: str) -> str:
        if not self.config.enabled or not self.config.hide_names:
            return name
        normalized = self._normalize_name(name)
        if normalized in self._name_to_index:
            out = self._format_name(self._name_to_index[normalized])
            return out
        self.register_user(name=name)
        out = self._format_name(self._name_to_index.get(normalized, 1))
        return out

    def get_anonymized_name(self, user_id: str, original_name: str) -> str:
        if not self.config.enabled or not self.config.hide_names:
            return original_name
        if user_id and user_id in self._id_to_index:
            return self._format_name(self._id_to_index[user_id])
        return self.anonymize_string_name(original_name)

    def _extract_domain(self, url: str) -> str:
        s = (url or "").strip()
        if not s:
            return ""
        if not s.startswith(("http://", "https://")):
            s = "https://" + s
        parsed = urlparse(s)
        host = (parsed.netloc or "").strip().lower()
        if host.startswith("www."):
            host = host[4:]
        return host or url

    def _mask_url(self, url: str) -> str:
        mode = self.config.link_mask_mode
        if mode == LinkMaskMode.CUSTOM:
            return self.config.link_mask_format
        if mode == LinkMaskMode.INDEXED:
            if url not in self._url_to_index:
                self._url_to_index[url] = self._next_url_index
                self._next_url_index += 1
            return self.config.link_mask_format.format(index=self._url_to_index[url])
        if mode == LinkMaskMode.DOMAIN_ONLY:
            return self._extract_domain(url)
        return tr("[СКРЫТО]")

    def _process_mentions(self, text: str) -> str:
        def repl(match):
            username = match.group(1)
            self.register_user(name=username)
            normalized = self._normalize_name(username)
            return self._format_name(self._name_to_index.get(normalized, 1))

        return self._mention_regex.sub(repl, text)

    def _rebuild_names_regex(self):
        if not self.config.hide_names or not self._name_to_index:
            self._names_regex = None
            return
        parts = [re.escape(name) for name in self._name_to_index.keys() if name]
        self._names_regex = re.compile(rf"\b({'|'.join(sorted(parts, key=len, reverse=True))})\b", re.IGNORECASE) if parts else None

    def process_text(self, text: str) -> str:
        if not self.config.enabled or not isinstance(text, str):
            return text
        result = text
        if self.config.hide_links:
            result = self._url_regex.sub(lambda m: self._mask_url(m.group(0)), result)
        if self.config.hide_names:
            result = self._process_mentions(result)
            if self._names_regex:
                result = self._names_regex.sub(
                    lambda m: self._format_name(
                        self._name_to_index.get(self._normalize_name(m.group(0)), 1)
                    ),
                    result,
                )
        return result

def _filter_messages_by_disabled_nodes(
    messages: list, disabled_nodes: set | None = None
) -> list:
    if not disabled_nodes:
        return messages

    real_years = set()
    for msg in messages:
        try:
            msg_date_str = msg["date"][:4]
            if msg_date_str.isdigit():
                real_years.add(int(msg_date_str))
        except (KeyError, IndexError, TypeError):
            continue

    real_years = sorted(real_years) if real_years else [2024]

    disabled_date_strings = set()

    def _get_descendant_day_nodes(node) -> list:

        children_to_scan = []
        if hasattr(node, "children") and node.children:
            children_to_scan.extend(node.children)
        if hasattr(node, "aggregated_children") and node.aggregated_children:
            children_to_scan.extend(node.aggregated_children)

        if not children_to_scan:

            if hasattr(node, "name") and node.name.isdigit() and hasattr(node, "date_level") and node.date_level == "day":
                return [node]
            return []

        day_nodes = []
        for child in children_to_scan:
            day_nodes.extend(_get_descendant_day_nodes(child))
        return day_nodes

    def _get_date_path(node) -> tuple:
        path_parts = []
        current = node
        depth = 0

        while current and hasattr(current, "parent") and current.parent and depth < 10:
            if hasattr(current, "date_level") and current.date_level in ("day", "month", "year"):
                path_parts.insert(0, (current.name, current.date_level))
            current = current.parent
            depth += 1
        return path_parts

    def _generate_date_patterns_for_node(node, available_years) -> set:
        node_name = getattr(node, 'name', 'UNKNOWN')
        node_level = getattr(node, "date_level", None)

        date_patterns = set()
        path_info = _get_date_path(node)

        if not path_info:
            return date_patterns

        year_val = month_val = day_val = None
        for name, level in path_info:
            if level == "year" and name.isdigit():
                year_val = int(name)
            elif level == "month" and name.isdigit():
                month_val = int(name)
            elif level == "day" and name.isdigit():
                day_val = int(name)

        def generate_patterns_for_incomplete_hierarchy():
            import calendar

            real_months = set()
            real_days = set()
            for msg in messages:
                try:
                    date_parts = msg["date"][:10].split('-')
                    if len(date_parts) == 3:
                        real_months.add(int(date_parts[1]))
                        real_days.add(int(date_parts[2]))
                except (KeyError, IndexError, ValueError):
                    continue

            real_months = sorted(real_months) if real_months else list(range(1, 13))
            real_days = sorted(real_days) if real_days else list(range(1, 32))

            patterns = set()

            if node_level == "day":
                if year_val and month_val and day_val:

                    return set()
                elif month_val and day_val:

                    for year in available_years:
                        patterns.add(f"{year}-{month_val:02d}-{day_val:02d}")
                elif year_val and day_val:

                    for month in real_months:
                        patterns.add(f"{year_val}-{month:02d}-{day_val:02d}")
                elif day_val:

                    for year in available_years:
                        for month in real_months:
                            patterns.add(f"{year}-{month:02d}-{day_val:02d}")

            elif node_level == "month":
                if year_val and month_val:

                    return set()
                elif month_val:

                    for year in available_years:
                        try:
                            days_in_month = calendar.monthrange(year, month_val)[1]
                            for day in range(1, days_in_month + 1):
                                patterns.add(f"{year}-{month_val:02d}-{day:02d}")
                        except (ValueError, calendar.IllegalMonthError):
                            for day in range(1, 32):
                                patterns.add(f"{year}-{month_val:02d}-{day:02d}")
                elif year_val:

                    for month in real_months:
                        try:
                            days_in_month = calendar.monthrange(year_val, month)[1]
                            for day in range(1, days_in_month + 1):
                                patterns.add(f"{year_val}-{month:02d}-{day:02d}")
                        except (ValueError, calendar.IllegalMonthError):
                            for day in range(1, 32):
                                patterns.add(f"{year_val}-{month:02d}-{day:02d}")

            elif node_level == "year":
                if year_val:

                    return set()
                else:

                    for year in available_years:
                        for month in real_months:
                            try:
                                days_in_month = calendar.monthrange(year, month)[1]
                                for day in range(1, days_in_month + 1):
                                    patterns.add(f"{year}-{month:02d}-{day:02d}")
                            except (ValueError, calendar.IllegalMonthError):
                                for day in range(1, 32):
                                    patterns.add(f"{year}-{month:02d}-{day:02d}")

            return patterns

        is_incomplete_hierarchy = (
            (not year_val and (month_val is not None or day_val is not None)) or
            (not month_val and (year_val is not None or day_val is not None)) or
            (not day_val and node_level == "day")
        )

        if is_incomplete_hierarchy:
            incomplete_patterns = generate_patterns_for_incomplete_hierarchy()
            if incomplete_patterns:
                date_patterns.update(incomplete_patterns)

        elif node_level == "day" and year_val and month_val and day_val:

            pattern = f"{year_val}-{month_val:02d}-{day_val:02d}"
            date_patterns.add(pattern)

        elif node_level == "month" and year_val and month_val:

            import calendar
            try:
                days_in_month = calendar.monthrange(year_val, month_val)[1]
                for day in range(1, days_in_month + 1):
                    pattern = f"{year_val}-{month_val:02d}-{day:02d}"
                    date_patterns.add(pattern)
            except (ValueError, calendar.IllegalMonthError):

                for day in range(1, 32):
                    pattern = f"{year_val}-{month_val:02d}-{day:02d}"
                    date_patterns.add(pattern)

        elif node_level == "year" and year_val:

            import calendar
            pattern_count = 0
            for month in range(1, 13):
                try:
                    days_in_month = calendar.monthrange(year_val, month)[1]
                    for day in range(1, days_in_month + 1):
                        pattern = f"{year_val}-{month:02d}-{day:02d}"
                        date_patterns.add(pattern)
                        pattern_count += 1
                except (ValueError, calendar.IllegalMonthError):

                    for day in range(1, 32):
                        pattern = f"{year_val}-{month:02d}-{day:02d}"
                        date_patterns.add(pattern)
                        pattern_count += 1

        return date_patterns

    for i, node in enumerate(disabled_nodes):
        node_level = getattr(node, "date_level", None)
        node_name = getattr(node, 'name', 'UNKNOWN')

        if node_level == "day":

            patterns = _generate_date_patterns_for_node(node, real_years)
            disabled_date_strings.update(patterns)
        else:

            day_nodes = _get_descendant_day_nodes(node)

            for day_node in day_nodes:
                day_patterns = _generate_date_patterns_for_node(day_node, real_years)
                disabled_date_strings.update(day_patterns)

            patterns = _generate_date_patterns_for_node(node, real_years)
            disabled_date_strings.update(patterns)

    if not disabled_date_strings:
        return messages

    original_count = len(messages)
    filtered_messages = []

    for msg in messages:
        try:
            msg_date_str = msg["date"][:10]
            if msg_date_str not in disabled_date_strings:
                filtered_messages.append(msg)
        except (KeyError, IndexError, TypeError):

            filtered_messages.append(msg)

    return filtered_messages

def _create_anonymization_config(config_dict: dict) -> AnonymizationConfig:
    enabled = bool(config_dict.get("enabled", False))
    hide_links = bool(config_dict.get("hide_links", False))
    hide_names = bool(config_dict.get("hide_names", False))
    name_mask_format = config_dict.get("name_mask_format", "[ИМЯ {index}]")

    raw_mode = config_dict.get("link_mask_mode", "simple")
    try:
        link_mask_mode = LinkMaskMode(raw_mode)
    except ValueError:
        link_mask_mode = LinkMaskMode.SIMPLE

    link_mask_format = config_dict.get("link_mask_format", "[ССЫЛКА {index}]")

    active_preset = None
    preset_dict = config_dict.get("active_preset")

    if isinstance(preset_dict, dict):
        preset_filters = []
        for f_dict in preset_dict.get("filters", []):
            if not isinstance(f_dict, dict):
                continue
            filter_type = LinkFilterType(f_dict.get("type", "domain"))
            filter_value = f_dict.get("value", "")
            filter_enabled = f_dict.get("enabled", True)
            preset_filters.append(LinkFilter(type=filter_type, value=filter_value, enabled=filter_enabled))
        active_preset = FilterPreset(name=preset_dict.get("name", ""), filters=preset_filters)

    custom_filters = []
    for f_dict in config_dict.get("custom_filters", []):
        if not isinstance(f_dict, dict):
            continue
        filter_type = LinkFilterType(f_dict.get("type", "domain"))
        filter_value = f_dict.get("value", "")
        filter_enabled = f_dict.get("enabled", True)
        custom_filters.append(LinkFilter(type=filter_type, value=filter_value, enabled=filter_enabled))

    custom_names = config_dict.get("custom_names", [])

    return AnonymizationConfig(
        enabled=enabled,
        hide_links=hide_links,
        hide_names=hide_names,
        name_mask_format=name_mask_format,
        link_mask_mode=link_mask_mode,
        link_mask_format=link_mask_format,
        active_preset=active_preset,
        custom_filters=custom_filters,
        custom_names=custom_names
    )

def _initialize_context(data: dict, config: dict) -> ConversionContext:
    chat_name = data.get("name", tr("common.unknown_chat"))
    message_map = {msg["id"]: msg for msg in data.get("messages", []) if "id" in msg}

    context = ConversionContext(
        config=config, message_map=message_map, chat_name=chat_name
    )

    anonymization_config_dict = config.get("anonymization", {})
    if isinstance(anonymization_config_dict, dict) and anonymization_config_dict:
        anonymization_config = _create_anonymization_config(anonymization_config_dict)
        if anonymization_config.enabled:

            context.anonymizer = _LegacyAnonymizerAdapter(anonymization_config)

            my_name_cfg = config.get("my_name")
            if my_name_cfg:
                context.anonymizer.register_user(name=my_name_cfg)

            partner_name_cfg = config.get("partner_name")
            if partner_name_cfg:
                context.anonymizer.register_user(name=partner_name_cfg)

            messages = data.get("messages", [])

            for msg in messages:
                if msg.get("from"):
                    context.anonymizer.register_user(name=msg.get("from"))
                if msg.get("forwarded_from"):
                    context.anonymizer.register_user(name=msg.get("forwarded_from"))
                if msg.get("type") == "service":
                    actor = msg.get("actor")
                    if actor:
                        context.anonymizer.register_user(name=actor)
                    for m in msg.get("members", []):
                        context.anonymizer.register_user(name=m)
                if "reactions" in msg:
                    for reaction in msg["reactions"]:
                        for recent in reaction.get("recent", []):
                            if recent.get("from"):
                                context.anonymizer.register_user(name=recent.get("from"))

            context.anonymizer._rebuild_names_regex()

    if config.get("profile") == "personal":
        authors = {}
        for msg in data.get("messages", []):
            if msg.get("type") == "message" and msg.get("from") and msg.get("from_id"):
                author_id = msg["from_id"]
                if author_id not in authors:
                    authors[author_id] = msg["from"]

        partner_full_name = data.get("name", "")
        detected_partner_id = None
        for author_id, author_name in authors.items():
            if author_name == partner_full_name:
                detected_partner_id = author_id
                break

        if detected_partner_id and len(authors) == 2:
            context.partner_id = detected_partner_id
            context.partner_full_name = partner_full_name

            my_id_list = [aid for aid in authors if aid != detected_partner_id]
            if my_id_list:
                context.my_id = my_id_list[0]
                context.my_full_name = authors.get(context.my_id)
        else:

            author_counts = Counter(
                msg["from_id"]
                for msg in data.get("messages", [])
                if msg.get("type") == "message" and msg.get("from_id")
            )
            top_two = author_counts.most_common(2)
            if len(top_two) >= 1:
                context.my_id = top_two[0][0]
                context.my_full_name = authors.get(context.my_id)
            if len(top_two) >= 2:
                context.partner_id = top_two[1][0]
                context.partner_full_name = authors.get(context.partner_id)

    elif config.get("profile") == "posts":
        first_message = next(
            (msg for msg in data.get("messages", []) if msg.get("type") == "message"),
            None,
        )
        if first_message:
            channel_name = first_message.get("forwarded_from") or first_message.get(
                "from"
            )
            if channel_name:
                context.chat_name = channel_name
            context.main_post_id = first_message.get("id")

    if context.anonymizer and context.chat_name:
        if context.anonymizer.config.hide_links:
            context.chat_name = context.anonymizer.process_text(context.chat_name)
        if context.anonymizer.config.hide_names:
            context.chat_name = context.anonymizer.anonymize_string_name(context.chat_name)

    return context

def generate_plain_text(
    data: dict, config: dict, html_mode: bool = False, disabled_nodes: set | None = None
) -> str:
    segments, _ = _build_plain_text_segments(
        data=data,
        config=config,
        html_mode=html_mode,
        disabled_nodes=disabled_nodes,
    )
    result = "".join(part for _, part in segments).strip() + "\n"
    return result

def _build_plain_text_segments(
    data: dict, config: dict, html_mode: bool = False, disabled_nodes: set | None = None
) -> tuple[list[tuple[str | None, str]], list[dict]]:

    all_messages = data.get("messages", [])
    messages = _filter_messages_by_disabled_nodes(all_messages, disabled_nodes)

    filtered_data = data.copy()
    filtered_data["messages"] = messages

    context = _initialize_context(filtered_data, config)

    output_parts: list[tuple[str | None, str]] = []

    profile = context.config.get("profile", "group")

    if profile == "personal":
        title_text = tr("profile.personal")
    elif profile == "posts":
        title_text = tr("profile.channel")
    elif profile == "channel":
        title_text = tr("profile.channel")
    else:
        title_text = tr("profile.group_chat")

    output_parts.append((None, f"{title_text}: {context.chat_name}\n"))
    output_parts.append((None, "========================================\n\n"))

    if context.config["profile"] == "personal" and context.my_id and context.partner_id:
        my_name_cfg = context.config["my_name"]
        my_full_name = context.my_full_name or tr("common.unknown")
        partner_name_cfg = context.config["partner_name"]
        partner_full_name = context.partner_full_name or tr("common.unknown")

        if context.anonymizer:
            my_full_name = context.anonymizer.get_anonymized_name(context.my_id, my_full_name)
            partner_full_name = context.anonymizer.get_anonymized_name(context.partner_id, partner_full_name)
            my_name_cfg = context.anonymizer.get_anonymized_name(context.my_id, my_name_cfg)
            partner_name_cfg = context.anonymizer.get_anonymized_name(context.partner_id, partner_name_cfg)

        output_parts.append((None, f"{tr('export.participants')}:\n"))
        output_parts.append((None, f"- {my_full_name}: {my_name_cfg}\n"))
        output_parts.append((None, f"- {partner_full_name}: {partner_name_cfg}\n\n"))

        output_parts.append((None, f"{tr('export.reaction_notation')}:\n"))
        if html_mode:
            output_parts.append((None, f"- &gt;&gt; {tr('export.from_label')} '{my_name_cfg}'\n"))
            output_parts.append((None, f"- &lt;&lt; {tr('export.from_label')} '{partner_name_cfg}'\n"))
        else:
            output_parts.append((None, f"- >> {tr('export.from_label')} '{my_name_cfg}'\n"))
            output_parts.append((None, f"- << {tr('export.from_label')} '{partner_name_cfg}'\n"))
        output_parts.append((None, "========================================\n\n"))

    previous_message = None

    if messages:
        try:
            first_msg_dt = datetime.fromisoformat(messages[0]["date"])
            separator = format_date_separator(first_msg_dt)
            current_date_key = str(messages[0].get("date", ""))[:10] or None
            output_parts.append((current_date_key, f"{separator}\n"))
        except (KeyError, ValueError) as e:
            pass

    processed_count = 0

    for i, msg in enumerate(messages):
        current_date_key = str(msg.get("date", ""))[:10] or None
        if previous_message:
            try:
                current_dt = datetime.fromisoformat(msg["date"])
                prev_dt = datetime.fromisoformat(previous_message["date"])

                if current_dt.date() > prev_dt.date():
                    separator = format_date_separator(current_dt)
                    output_parts.append((current_date_key, f"\n{separator}\n"))
            except (KeyError, ValueError) as e:
                pass

        msg_type = msg.get("type")
        formatted_text = None

        if msg_type == "service":
            formatted_text = format_service_message(msg, context)

        elif msg_type == "message":
            formatted_text = format_message(msg, previous_message, context, html_mode)

        if formatted_text:
            output_parts.append((current_date_key, formatted_text))
            processed_count += 1

        previous_message = msg

    return output_parts, messages
