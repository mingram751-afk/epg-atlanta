import datetime
import json
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo


TIMEZONE = ZoneInfo("America/New_York")
API_BASE = "https://api2-test.3abn.org/sched/daily"
DAYS = 7

# XMLTV channel ID, display name, and network key used by the 3ABN schedule API.
CHANNELS = [
    ("3ABN.us", "3ABN", "main"),
    ("3ABN-Proclaim.us", "3ABN Proclaim Network", "proc"),
    ("3ABN-DareToDream.us", "3ABN Dare to Dream Network", "dare"),
    ("3ABN-International.us", "3ABN International Network", "int"),
    ("3ABN-Kids.us", "3ABN Kids Network", "kids"),
]


def offset_minutes(day):
    """Return the local UTC offset for this schedule date, accounting for DST."""
    local_noon = datetime.datetime.combine(day, datetime.time(12), tzinfo=TIMEZONE)
    return int(local_noon.utcoffset().total_seconds() // 60)


def fetch_schedule(network, day):
    url = f"{API_BASE}/{network}/{day.isoformat()}/{offset_minutes(day)}"
    request = urllib.request.Request(url, headers={"User-Agent": "epg-atlanta-xmltv/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = json.load(response)

    records = payload.get("schedule") if isinstance(payload, dict) else None
    if not isinstance(records, list) or not records:
        raise RuntimeError(f"No schedule records returned for {network} on {day}: {url}")
    return records


def parse_start(record):
    value = record.get("date")
    if not value:
        raise RuntimeError(f"Schedule record is missing its date: {record!r}")
    parsed = datetime.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TIMEZONE)
    return parsed.astimezone(TIMEZONE)


def parse_duration(record):
    # The API spells this field "duartion". Its value is HH:MM:SS:FF.
    value = record.get("duartion") or record.get("duration")
    if not value:
        return None
    parts = value.split(":")
    if len(parts) not in (3, 4):
        raise RuntimeError(f"Unrecognized duration {value!r}")
    hours, minutes, seconds = (int(part) for part in parts[:3])
    return datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)


def xmltv_time(value):
    # Preserve the requested XMLTV format without a timezone suffix.
    return value.astimezone(TIMEZONE).strftime("%Y%m%d%H%M%S")


def add_text(parent, tag, value):
    if value is not None and str(value).strip():
        ET.SubElement(parent, tag).text = str(value).strip()


def main():
    today = datetime.datetime.now(TIMEZONE).date()
    days = [today + datetime.timedelta(days=index) for index in range(DAYS)]

    root = ET.Element("tv", {"source-info-name": "3ABN", "source-info-url": "https://3abn.org"})
    all_programmes = []

    for channel_id, display_name, network in CHANNELS:
        channel = ET.SubElement(root, "channel", {"id": channel_id})
        ET.SubElement(channel, "display-name").text = display_name

        records = []
        for day in days:
            records.extend(fetch_schedule(network, day))

        for record in records:
            start = parse_start(record)
            duration = parse_duration(record)
            all_programmes.append((start, duration, channel_id, record))

    all_programmes.sort(key=lambda item: (item[2], item[0]))
    for index, (start, duration, channel_id, record) in enumerate(all_programmes):
        stop = start + duration if duration is not None else None
        if stop is None:
            next_item = next(
                (item for item in all_programmes[index + 1:] if item[2] == channel_id),
                None,
            )
            if next_item is None:
                raise RuntimeError(f"No duration or following programme for {channel_id} at {start}")
            stop = next_item[0]

        programme = ET.SubElement(root, "programme", {
            "start": xmltv_time(start),
            "stop": xmltv_time(stop),
            "channel": channel_id,
        })
        series = record.get("series_title") or record.get("program_title") or "Unknown program"
        add_text(programme, "title", series)
        program_title = record.get("program_title")
        if program_title and program_title.strip() != series.strip():
            add_text(programme, "sub-title", program_title)
        add_text(programme, "desc", record.get("description"))
        if record.get("program_code"):
            episode = ET.SubElement(programme, "episode-num", {"system": "onscreen"})
            episode.text = str(record["program_code"])

    ET.indent(root, space="  ")
    output = "3abn_full.xml"
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
    print(f"Wrote {output} with {len(all_programmes)} programmes across {len(CHANNELS)} channels")


if __name__ == "__main__":
    main()
