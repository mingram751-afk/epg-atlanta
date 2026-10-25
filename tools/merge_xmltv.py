#!/usr/bin/env python3
"""Fetch and merge the configured epg.pw and EPGShare XMLTV feeds."""

from __future__ import annotations

import gzip
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

CHANNEL_IDS = (
    "465164", "465196", "470415", "465021", "465145", "465179", "465061", "464947", "565869",
    "465004", "467309", "464906", "464958", "465321", "465285"
)
BASE_URL = "https://epg.pw/api/epg.xml?channel_id="
OUTPUT = Path(__file__).resolve().parents[1] / "merged.xml"
WATC_URL = "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz"
WATC_CHANNEL_ID = "WATC-DT.us_locals1"
CNN_URL = "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz"
CNN_SOURCE_CHANNEL_ID = "plex.tv.CNN.Originals.plex"
CNN_CHANNEL_ID = "CNNOriginals.us"
WORD_NETWORK_URL = "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz"
WORD_NETWORK_CHANNEL_ID = "The.Word.Network.us2"


def fetch_epgshare_channel(
    url: str, source_channel_id: str, output_channel_id: str
) -> tuple[ET.Element, list[ET.Element]]:
    """Fetch a compressed EPGShare feed and retain one channel and its listings."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; epg-atlanta-xmltv-merger/1.0)",
            "Referer": "https://epgshare01.online/epgshare01/",
        },
    )
    channels: list[ET.Element] = []
    programmes: list[ET.Element] = []
    stack: list[ET.Element] = []
    found_channel = False

    with urllib.request.urlopen(request, timeout=180) as response:
        with gzip.GzipFile(fileobj=response) as source:
            for event, elem in ET.iterparse(source, events=("start", "end")):
                if event == "start":
                    stack.append(elem)
                    continue

                if len(stack) == 2:
                    if elem.tag == "channel" and elem.get("id") == source_channel_id:
                        channel = ET.fromstring(ET.tostring(elem))
                        channel.set("id", output_channel_id)
                        channels.append(channel)
                        found_channel = True
                    elif elem.tag == "programme" and elem.get("channel") == source_channel_id:
                        programme = ET.fromstring(ET.tostring(elem))
                        programme.set("channel", output_channel_id)
                        programmes.append(programme)
                    stack[0].remove(elem)
                    elem.clear()
                stack.pop()

    if not found_channel:
        raise ValueError(f"source does not contain channel {source_channel_id}")
    return channels[0], programmes


def main() -> int:
    channels: dict[str, ET.Element] = {}
    programmes: list[ET.Element] = []
    epg_programmes: dict[tuple[str | None, str | None, str | None], ET.Element] = {}

    today = datetime.now(ZoneInfo("America/New_York")).date()
    feed_dates = (today - timedelta(days=1), today)
    for channel_id in CHANNEL_IDS:
        for feed_date in feed_dates:
            date_text = feed_date.strftime("%Y%m%d")
            url = f"{BASE_URL}{channel_id}&date={date_text}"
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
                # Later dates overwrite overlapping listings from the previous day.
                for programme in feed_programmes:
                    key = (
                        programme.get("channel"),
                        programme.get("start"),
                        programme.get("stop"),
                    )
                    epg_programmes[key] = programme
                print(
                    f"{channel_id} ({date_text}): {len(feed_channels)} channels, "
                    f"{len(feed_programmes)} programmes"
                )
            except Exception as exc:
                print(
                    f"Failed to fetch or parse feed {channel_id} for {date_text}: {exc}",
                    file=sys.stderr,
                )
                return 1

    programmes.extend(epg_programmes.values())

    try:
        watc_channel, watc_programmes = fetch_epgshare_channel(
            WATC_URL, WATC_CHANNEL_ID, WATC_CHANNEL_ID
        )
        channels.setdefault(WATC_CHANNEL_ID, watc_channel)
        programmes.extend(watc_programmes)
        print(f"{WATC_CHANNEL_ID}: 1 channel, {len(watc_programmes)} programmes")
    except Exception as exc:
        print(f"Failed to fetch or parse WATC feed: {exc}", file=sys.stderr)
        return 1

    try:
        cnn_channel, cnn_programmes = fetch_epgshare_channel(
            CNN_URL, CNN_SOURCE_CHANNEL_ID, CNN_CHANNEL_ID
        )
        channels.setdefault(CNN_CHANNEL_ID, cnn_channel)
        programmes.extend(cnn_programmes)
        print(f"{CNN_CHANNEL_ID}: 1 channel, {len(cnn_programmes)} programmes")
    except Exception as exc:
        print(f"Failed to fetch or parse CNN Originals feed: {exc}", file=sys.stderr)
        return 1

    try:
        word_channel, word_programmes = fetch_epgshare_channel(
            WORD_NETWORK_URL, WORD_NETWORK_CHANNEL_ID, WORD_NETWORK_CHANNEL_ID
        )
        channels.setdefault(WORD_NETWORK_CHANNEL_ID, word_channel)
        programmes.extend(word_programmes)
        print(
            f"{WORD_NETWORK_CHANNEL_ID}: 1 channel, "
            f"{len(word_programmes)} programmes"
        )
    except Exception as exc:
        print(
            f"Failed to fetch or parse The Word Network feed: {exc}", file=sys.stderr
        )
        return 1

    root = ET.Element(
        "tv",
        {
            "source-info-name": "epg.pw + epgshare01",
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
