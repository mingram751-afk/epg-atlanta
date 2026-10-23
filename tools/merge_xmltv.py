#!/usr/bin/env python3
"""Fetch and merge the configured epg.pw XMLTV feeds."""

from __future__ import annotations

import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

CHANNEL_IDS = (
    "465164", "470415", "465021", "465145", "465179", "465061", "464947", "565869",
    "465004", "467309", "464906", "464958", "465321",
)
BASE_URL = "https://epg.pw/api/epg.xml?channel_id="
OUTPUT = Path(__file__).resolve().parents[1] / "merged.xml"


def main() -> int:
    channels: dict[str, ET.Element] = {}
    programmes: list[ET.Element] = []

    for channel_id in CHANNEL_IDS:
        url = BASE_URL + channel_id
        request = urllib.request.Request(
            url, headers={"User-Agent": "epg-atlanta-xmltv-merger/1.0"}
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read()
            source = ET.fromstring(payload)
            if source.tag != "tv":
                raise ValueError(f"expected <tv>, found <{source.tag}>")
            feed_channels = source.findall("channel")
            feed_programmes = source.findall("programme")
            for channel in feed_channels:
                channel_id_attr = channel.get("id")
                if channel_id_attr:
                    channels.setdefault(channel_id_attr, channel)
            programmes.extend(feed_programmes)
            print(
                f"{channel_id}: {len(feed_channels)} channels, "
                f"{len(feed_programmes)} programmes"
            )
        except Exception as exc:
            print(f"Failed to fetch or parse feed {channel_id}: {exc}", file=sys.stderr)
            return 1

    root = ET.Element(
        "tv",
        {
            "source-info-name": "epg.pw",
            "generator-info-name": "epg-atlanta XMLTV merger",
        },
    )
    root.extend(channels.values())
    root.extend(programmes)
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(OUTPUT, encoding="utf-8", xml_declaration=True)
    print(
        f"Wrote {OUTPUT}: {len(channels)} unique channels, "
        f"{len(programmes)} programmes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
