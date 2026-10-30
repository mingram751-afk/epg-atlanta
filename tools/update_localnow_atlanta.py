#!/usr/bin/env python3
"""Refresh the Atlanta LocalNow playlist and build an XMLTV guide from LocalNow pages."""
from __future__ import annotations

import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLAYLIST = ROOT / "localnow_atlanta.m3u"
GUIDE = ROOT / "localnow_atlanta_epg.xml"
PLAYLIST_URL = "https://www.apsattv.com/localnow.m3u"
PAGES = [
    "https://localnow.com/channels/epg-local-now-atlanta",
    "https://localnow.com/channels/wanf-hyperlocal",
]
CHANNELS = {
    "locked": ("Locked On Sports Atlanta", ("locked on sports atlanta",)),
    "wsb": ("WSB (ABC) News 2 Atlanta GA", ("wsb", "atlanta")),
    "waga": ("WAGA FOX 5 Atlanta GA", ("waga", "atlanta")),
    "wxia": ("WXIA NBC 11Alive Atlanta GA", ("wxia", "11alive")),
    "wanf": ("WANF Atlanta News First", ("wanf", "atlanta news first")),
}
CHANNEL_IDS = {
    "locked": "LN_AF8A0869-F746-4CC3-8254-CD48E24F4F70",
    "wsb": "LN_F62DE179-6022-485E-9D40-F4A77B179215",
    "waga": "LN_0F9F3A85-2CAD-4492-BFE7-C809E79489CB",
    "wxia": "LN_BD90ADE3-F2E3-4760-82C9-4BAFB5107E40",
    "wanf": "LN_A6C04409-CBA8-4DD8-84F3-03CA01450CBD",
}
FALLBACK_URLS = {
    "wanf": "https://localnow.com/channels/wanf-hyperlocal",
}
USER_AGENT = "Mozilla/5.0 (compatible; LocalNowAtlantaEPG/1.0; +https://github.com/)"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def channel_key(text: str) -> str | None:
    value = normalize(text)
    for key, (_, aliases) in CHANNELS.items():
        if all(normalize(alias) in value for alias in aliases):
            return key
    return None


def parse_m3u(text: str) -> dict[str, tuple[str, str]]:
    lines = text.lstrip("\ufeff").splitlines()
    result: dict[str, tuple[str, str]] = {}
    info = None
    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF:"):
            info = line
        elif line and not line.startswith("#") and info:
            name = info.rsplit(",", 1)[-1].strip()
            key = channel_key(name)
            if key:
                result[key] = (info, line)
            info = None
    return result


def refresh_playlist() -> None:
    current = parse_m3u(PLAYLIST.read_text(encoding="utf-8")) if PLAYLIST.exists() else {}
    try:
        latest = parse_m3u(fetch(PLAYLIST_URL).decode("utf-8", errors="replace"))
    except Exception as exc:
        print(f"Playlist source unavailable; retaining checked-in entries: {exc}", file=sys.stderr)
        latest = {}
    for key in CHANNELS:
        if key in latest:
            current[key] = latest[key]
        elif key not in current:
            raise RuntimeError(f"No playlist entry for required channel {CHANNELS[key][0]}")
    lines = [
        '#EXTM3U url-tvg="localnow_atlanta_epg.xml" x-tvg-url="localnow_atlanta_epg.xml"'
    ]
    for key in CHANNELS:
        info, url = current[key]
        info = re.sub(r'tvg-id="[^"]*"', f'tvg-id="{CHANNEL_IDS[key]}"', info)
        if "tvg-id=" not in info:
            info = info.replace("#EXTINF:-1", f'#EXTINF:-1 tvg-id="{CHANNEL_IDS[key]}"', 1)
        lines.extend((info, url))
    PLAYLIST.write_text("\n".join(lines) + "\n", encoding="utf-8")


def find_next_data(html: str) -> dict[str, Any]:
    match = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.S)
    if not match:
        raise RuntimeError("LocalNow page did not contain __NEXT_DATA__")
    return json.loads(match.group(1))


def walk(value: Any, path: tuple[str, ...] = ()):
    if isinstance(value, dict):
        yield value, path
        for key, child in value.items():
            yield from walk(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, path + (str(index),))


def first_text(item: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def parse_time(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        try:
            return datetime.fromtimestamp(seconds, timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    raw = value.strip()
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def programme_rows(item: dict[str, Any]):
    fields = ("schedule", "programs", "programmes", "program", "events", "listings")
    for field in fields:
        value = item.get(field)
        if isinstance(value, list):
            for row in value:
                if isinstance(row, dict):
                    yield row
        elif isinstance(value, dict):
            for row in value.values():
                if isinstance(row, dict):
                    yield row
                elif isinstance(row, list):
                    yield from (x for x in row if isinstance(x, dict))


def collect_guide() -> ET.Element:
    found: dict[str, list[tuple[datetime, datetime, str, str]]] = {key: [] for key in CHANNELS}
    for page_url in PAGES:
        payload = find_next_data(fetch(page_url).decode("utf-8", errors="replace"))
        props = payload.get("props", {}).get("pageProps", {})
        for item, path in walk(props):
            context = " ".join([*path, *(str(v) for v in item.values() if isinstance(v, str))])
            key = channel_key(context)
            if key is None and page_url.endswith("/wanf-hyperlocal") and (not path or "schedule" in path):
                key = "wanf"
            if not key:
                continue
            for row in programme_rows(item):
                title = first_text(row, ("title", "name", "programName", "program_name"))
                start = end = None
                for start_key in ("start", "startTime", "start_time", "startDate", "startDateTime", "startsAt", "airingStart", "begin"):
                    if start_key in row:
                        start = parse_time(row[start_key]);
                        if start: break
                for end_key in ("end", "endTime", "end_time", "endDate", "endDateTime", "endsAt", "airingEnd", "stop"):
                    if end_key in row:
                        end = parse_time(row[end_key]);
                        if end: break
                if not title or not start or not end or end <= start:
                    continue
                description = first_text(row, ("description", "summary", "synopsis")) or ""
                found[key].append((start, end, title, description))
    missing = [CHANNELS[key][0] for key, rows in found.items() if not rows]
    if missing:
        raise RuntimeError("No schedule data found for: " + ", ".join(missing))
    tv = ET.Element("tv", {"generator-info-name": "LocalNow Atlanta guide builder"})
    current = parse_m3u(PLAYLIST.read_text(encoding="utf-8"))
    for key, (display, _) in CHANNELS.items():
        info = current[key][0]
        logo = re.search(r'tvg-logo="([^"]+)"', info)
        chan = ET.SubElement(tv, "channel", {"id": CHANNEL_IDS[key]})
        ET.SubElement(chan, "display-name").text = display
        if logo:
            ET.SubElement(chan, "icon", {"src": logo.group(1)})
        unique = sorted(set(found[key]), key=lambda row: row[0])
        for start, end, title, desc in unique:
            programme = ET.SubElement(tv, "programme", {
                "start": start.strftime("%Y%m%d%H%M%S +0000"),
                "stop": end.strftime("%Y%m%d%H%M%S +0000"),
                "channel": CHANNEL_IDS[key],
            })
            ET.SubElement(programme, "title", {"lang": "en"}).text = title
            if desc:
                ET.SubElement(programme, "desc", {"lang": "en"}).text = desc
    ET.indent(tv, space="  ")
    return tv


def main() -> None:
    refresh_playlist()
    guide = collect_guide()
    ET.ElementTree(guide).write(GUIDE, encoding="utf-8", xml_declaration=True)
    print(f"Wrote {PLAYLIST.name} and {GUIDE.name}")


if __name__ == "__main__":
    main()
