import datetime
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo


TIMEZONE = ZoneInfo("America/New_York")
API_BASE = "https://api2-test.3abn.org/sched/daily"
GTN_FEED_BASE = "https://gms.awmws.com/program-guide/json"
GTN_CHANNEL = ("GospelTruthTV.us", "Gospel Truth TV")
TWN_API_BASE = "https://www.titantvguide.com/data/eventspage"
TWN_SITE_ID = "77972"
TWN_CHANNEL_UUID = "bead6bfc-ebc5-43c2-89ee-b67122ff5273"
TWN_CHANNEL_INDEX = "8752"
TWN_CHANNEL = ("The.Word.Network.us2", "The Word Network")
DAYS = 7

# XMLTV channel ID, display name, and network key used by the 3ABN schedule API.
CHANNELS = [
    ("3ABN.us", "3ABN", "main"),
    ("3ABN-Proclaim.us", "3ABN Proclaim Network", "proc"),
    ("3ABN-DareToDream.us", "3ABN Dare to Dream Network", "dare"),
    ("3ABN-International.us", "3ABN International Network", "int"),
    ("3ABN-Kids.us", "3ABN Kids Network", "kids"),
    ("3ABN-PraiseHimMusic.us", "3ABN Praise Him Music Network", "praise"),
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


def parse_fixed_utc_offset(value):
    """Parse the UTC offset published with a GTN day feed."""
    match = re.fullmatch(r"UTC([+-])(\d{1,2}):(\d{2})", value or "")
    if not match:
        raise RuntimeError(f"Unrecognized GTN timezone offset: {value!r}")
    sign = 1 if match.group(1) == "+" else -1
    hours, minutes = int(match.group(2)), int(match.group(3))
    return datetime.timezone(sign * datetime.timedelta(hours=hours, minutes=minutes))


def fetch_gtn_schedule(day):
    url = f"{GTN_FEED_BASE}/{day:%Y%m%d}"
    request = urllib.request.Request(url, headers={"User-Agent": "epg-atlanta-xmltv/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = json.load(response)

    records = payload.get("entry") if isinstance(payload, dict) else None
    if not isinstance(records, list) or not records:
        raise RuntimeError(f"No GTN schedule records returned for {day}: {url}")
    return records, parse_fixed_utc_offset(payload.get("time_zone"))


def parse_gtn_time(value, source_timezone):
    if not value:
        raise RuntimeError("GTN schedule record is missing a start or end time")
    parsed = datetime.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=source_timezone)
    return parsed.astimezone(TIMEZONE)


def fetch_twn_schedule(day):
    # TitanTV returns one full local day when the requested window is 1440 minutes.
    start_time = f"{day:%Y%m%d}0000"
    url = (
        f"{TWN_API_BASE}/{TWN_SITE_ID}/{TWN_CHANNEL_UUID}/"
        f"{start_time}/1440/{TWN_CHANNEL_INDEX}/1"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "epg-atlanta-xmltv/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = json.load(response)

    if payload.get("Status") != "SUCCESS":
        raise RuntimeError(f"TitanTV returned an unsuccessful response for {day}: {url}")
    try:
        records = payload["Json"]["Channels"][0]["Days"][0]["Shows"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError(f"TitanTV schedule response has an unexpected shape for {day}: {url}") from error
    if not isinstance(records, list) or not records:
        raise RuntimeError(f"No The Word Network schedule records returned for {day}: {url}")
    return records


def titantv_text(values):
    """Extract English display text from a TitanTV localized text array."""
    if not isinstance(values, list):
        return None
    for item in values:
        if isinstance(item, dict) and item.get("Text") and item.get("Lang") == "eng":
            return item["Text"]
    for item in values:
        if isinstance(item, dict) and item.get("Text"):
            return item["Text"]
    return None


def parse_twn_time(value):
    if not value:
        raise RuntimeError("The Word Network schedule record is missing a start or end time")
    parsed = datetime.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise RuntimeError(f"TitanTV returned a time without a timezone offset: {value!r}")
    return parsed.astimezone(TIMEZONE)


def xmltv_time(value):
    # Include the Eastern timezone offset, including the correct DST adjustment.
    return value.astimezone(TIMEZONE).strftime("%Y%m%d%H%M%S %z")


def add_text(parent, tag, value):
    if value is not None and str(value).strip():
        ET.SubElement(parent, tag).text = str(value).strip()


def main():
    today = datetime.datetime.now(TIMEZONE).date()
    days = [today + datetime.timedelta(days=index) for index in range(DAYS)]

    root = ET.Element("tv", {"source-info-name": "3ABN, Gospel Truth TV, and The Word Network", "source-info-url": "https://www.thewordnetwork.org/"})
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

    gtn_id, gtn_name = GTN_CHANNEL
    channel = ET.SubElement(root, "channel", {"id": gtn_id})
    ET.SubElement(channel, "display-name").text = gtn_name
    for day in days:
        records, source_timezone = fetch_gtn_schedule(day)
        for record in records:
            extensions = record.get("extensions") or {}
            start = parse_gtn_time(extensions.get("start_time"), source_timezone)
            stop = parse_gtn_time(extensions.get("end_time"), source_timezone)
            if stop <= start:
                raise RuntimeError(f"Invalid GTN programme interval for {day}: {record!r}")
            normalized_record = {
                "series_title": extensions.get("show_title") or record.get("title") or "Unknown program",
                "program_title": record.get("title"),
                "description": record.get("description"),
            }
            all_programmes.append((start, stop - start, gtn_id, normalized_record))

    twn_id, twn_name = TWN_CHANNEL
    channel = ET.SubElement(root, "channel", {"id": twn_id})
    ET.SubElement(channel, "display-name").text = twn_name
    for day in days:
        for record in fetch_twn_schedule(day):
            start = parse_twn_time(record.get("StartTime"))
            stop = parse_twn_time(record.get("EndTime"))
            if stop <= start:
                raise RuntimeError(f"Invalid The Word Network programme interval for {day}: {record!r}")
            normalized_record = {
                "series_title": titantv_text(record.get("Title")) or "Unknown program",
                "program_title": titantv_text(record.get("EpisodeTitle")),
                "description": titantv_text(record.get("Description")),
            }
            all_programmes.append((start, stop - start, twn_id, normalized_record))

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
    print(f"Wrote {output} with {len(all_programmes)} programmes across {len(CHANNELS) + 2} channels")


if __name__ == "__main__":
    main()
