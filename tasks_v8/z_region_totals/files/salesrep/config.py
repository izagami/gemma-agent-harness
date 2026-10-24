"""Report configuration.

config/base.ini holds the defaults; every file in config/regions.d/ (sorted by name) is read on top of it,
so a later file can override [report] settings as well as define regions.  A region is a section
`[region:<name>]` with a `label` and a `stores` list (comma and/or newline separated store ids).
"""
import configparser
import os
from dataclasses import dataclass, field


@dataclass
class Region:
    name: str
    label: str
    stores: list


@dataclass
class Config:
    title: str = "売上レポート"
    currency: str = "JPY"
    column_width: int = 12
    sales_dir: str = "sales"
    refunds_dir: str = "refunds"
    stores_file: str = "stores.csv"
    aliases_file: str = "store_aliases.csv"
    regions: dict = field(default_factory=dict)


def split_list(text):
    out = []
    for line in text.splitlines():
        line = line.split("#", 1)[0]
        out.extend(x.strip() for x in line.split(",") if x.strip())
    return out


def load_config(config_dir):
    cp = configparser.ConfigParser(inline_comment_prefixes=("#",), interpolation=None)
    files = [os.path.join(config_dir, "base.ini")]
    rd = os.path.join(config_dir, "regions.d")
    if os.path.isdir(rd):
        files += [os.path.join(rd, f) for f in sorted(os.listdir(rd)) if f.endswith(".ini")]
    for f in files:
        with open(f, encoding="utf-8") as fh:
            cp.read_file(fh, source=f)
    cfg = Config()
    if cp.has_section("report"):
        r = cp["report"]
        cfg.title = r.get("title", cfg.title)
        cfg.currency = r.get("currency", cfg.currency)
        cfg.column_width = r.getint("column_width", cfg.column_width)
    if cp.has_section("data"):
        d = cp["data"]
        for key in ("sales_dir", "refunds_dir", "stores_file", "aliases_file"):
            setattr(cfg, key, d.get(key, getattr(cfg, key)))
    for sec in cp.sections():
        if sec.startswith("region:"):
            name = sec.split(":", 1)[1].strip()
            s = cp[sec]
            cfg.regions[name] = Region(name, s.get("label", name), split_list(s.get("stores", "")))
    return cfg
