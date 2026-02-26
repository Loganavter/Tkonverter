from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum, auto

class LinkFilterType(Enum):
    ALL = "all"
    DOMAIN = "domain"
    REGEX = "regex"

class LinkMaskMode(Enum):
    SIMPLE = "simple"
    DOMAIN_ONLY = "domain"
    INDEXED = "indexed"
    CUSTOM = "custom"

@dataclass
class LinkFilter:
    type: LinkFilterType
    value: str = ""
    enabled: bool = True

@dataclass
class FilterPreset:
    name: str
    filters: List[LinkFilter] = field(default_factory=list)

@dataclass
class AnonymizationConfig:
    enabled: bool = False
    hide_links: bool = False
    hide_names: bool = False
    name_mask_format: str = "[ИМЯ {index}]"
    link_mask_mode: LinkMaskMode = LinkMaskMode.SIMPLE
    link_mask_format: str = "[ССЫЛКА {index}]"
    active_preset: Optional[FilterPreset] = None
    custom_filters: List[LinkFilter] = field(default_factory=list)

    custom_names: List[dict] = field(default_factory=list)
