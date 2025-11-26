from html import unescape
from html.parser import HTMLParser
from typing import Union
from moz.l10n.message import serialize_message
from moz.l10n.model import (
    CatchallKey,
    Entry,
    Message,
    PatternMessage,
    Resource,
    SelectMessage,
)


def parse_file(
    resource: Resource,
    storage: dict[str, dict[str, str]],
    filename: str,
    id_base: str,
) -> None:
    def get_entry_value(value: Message) -> str:
        entry_value = serialize_message(resource.format, value)
        # Unescape literal quotes
        entry_value = entry_value.replace('\\"', '"').replace("\\'", "'")

        return entry_value

    def serialize_select_variants(entry: Entry) -> str:
        msg: SelectMessage = entry.value
        lines: list[str] = []
        for key_tuple, pattern in msg.variants.items():
            key: Union[str, CatchallKey] = key_tuple[0] if key_tuple else "other"
            default = "*" if isinstance(key, CatchallKey) else ""
            label: str | None = key.value if isinstance(key, CatchallKey) else str(key)
            lines.append(
                f"{default}[{label}] {serialize_message(resource.format, PatternMessage(pattern))}"
            )
        return "\n".join(lines)

    try:
        for section in resource.sections:
            for entry in section.entries:
                if isinstance(entry, Entry):
                    string_id = ".".join(section.id + entry.id)
                    string_id = f"{id_base}:{string_id}"

                    # If it's a plural string in Android, each variant
                    # is stored within the message, following a format
                    # similar to Fluent.
                    if hasattr(entry.value, "variants"):
                        storage[string_id] = {
                            "value": serialize_select_variants(entry),
                            "comment": entry.comment,
                        }
                    else:
                        storage[string_id] = {
                            "value": get_entry_value(entry.value),
                            "comment": entry.comment,
                        }
    except Exception as e:
        print(f"Error parsing file: {filename}")
        print(e)


class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []

    def clear(self):
        self.reset()
        self.fed = []

    def handle_data(self, data):
        self.fed.append(data)

    def get_data(self):
        return " ".join(self.fed)


def strip_html(html: str) -> str:
    html = unescape(html)

    stripper = HTMLStripper()
    stripper.feed(html)
    return stripper.get_data()
