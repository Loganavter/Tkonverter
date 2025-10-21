from collections import Counter
from datetime import datetime

from src.core.conversion.context import ConversionContext
from src.core.conversion.formatters.service_formatter import format_service_message
from src.core.conversion.message_formatter import format_message
from src.core.conversion.utils import format_date_separator
from src.resources.translations import tr

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
        """Recursively gets all descendant day nodes (tree leaves)."""

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
        """Gets the full path to the root for date construction."""
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
        """Generates date patterns for a node of any level."""
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

def _initialize_context(data: dict, config: dict) -> ConversionContext:
    chat_name = data.get("name", tr("Unknown Chat"))
    message_map = {msg["id"]: msg for msg in data.get("messages", []) if "id" in msg}

    context = ConversionContext(
        config=config, message_map=message_map, chat_name=chat_name
    )

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

    return context

def generate_plain_text(
    data: dict, config: dict, html_mode: bool = False, disabled_nodes: set | None = None
) -> str:

    all_messages = data.get("messages", [])
    messages = _filter_messages_by_disabled_nodes(all_messages, disabled_nodes)

    filtered_data = data.copy()
    filtered_data["messages"] = messages

    context = _initialize_context(filtered_data, config)

    output_parts = []

    profile = context.config.get("profile", "group")

    if profile == "personal":
        title_text = tr("Personal correspondence")
    elif profile == "posts":
        title_text = tr("Channel")
    elif profile == "channel":
        title_text = tr("Channel")
    else:
        title_text = tr("Group chat")

    output_parts.append(f"{title_text}: {context.chat_name}\n")
    output_parts.append("========================================\n\n")

    if context.config["profile"] == "personal" and context.my_id and context.partner_id:
        my_name_cfg = context.config["my_name"]
        my_full_name = context.my_full_name or tr("Unknown")
        partner_name_cfg = context.config["partner_name"]
        partner_full_name = context.partner_full_name or tr("Unknown")

        output_parts.append(f"{tr('Participants')}:\n")
        output_parts.append(f"- {my_full_name}: {my_name_cfg}\n")
        output_parts.append(f"- {partner_full_name}: {partner_name_cfg}\n\n")

        output_parts.append(f"{tr('Reaction notation')}:\n")
        if html_mode:
            output_parts.append(f"- &gt;&gt; {tr('from')} '{my_name_cfg}'\n")
            output_parts.append(f"- &lt;&lt; {tr('from')} '{partner_name_cfg}'\n")
        else:
            output_parts.append(f"- >> {tr('from')} '{my_name_cfg}'\n")
            output_parts.append(f"- << {tr('from')} '{partner_name_cfg}'\n")
        output_parts.append("========================================\n\n")

    previous_message = None

    if messages:
        try:
            first_msg_dt = datetime.fromisoformat(messages[0]["date"])
            separator = format_date_separator(first_msg_dt)
            output_parts.append(f"{separator}\n")
        except (KeyError, ValueError) as e:
            pass

    processed_count = 0

    for i, msg in enumerate(messages):
        if previous_message:
            try:
                current_dt = datetime.fromisoformat(msg["date"])
                prev_dt = datetime.fromisoformat(previous_message["date"])

                if current_dt.date() > prev_dt.date():
                    separator = format_date_separator(current_dt)
                    output_parts.append(f"\n{separator}\n")
            except (KeyError, ValueError) as e:
                pass

        msg_type = msg.get("type")
        formatted_text = None

        if msg_type == "service":
            formatted_text = format_service_message(msg, context)

        elif msg_type == "message":
            formatted_text = format_message(msg, previous_message, context, html_mode)

        if formatted_text:
            output_parts.append(formatted_text)
            processed_count += 1

        previous_message = msg

    result = "".join(output_parts).strip() + "\n"

    return result
