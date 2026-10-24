import datetime
import xml.etree.ElementTree as ET

CHANNELS = [
    ("3ABN.us", "3ABN"),
    ("3ABN-DareToDream.us", "3ABN Dare to Dream Network"),
    ("3ABN-International.us", "3ABN International Network"),
    ("3ABN-Proclaim.us", "3ABN Proclaim Network"),
    ("3ABN-Kids.us", "3ABN Kids Network"),
]

PROGRAM_BLOCK = [
    ("3ABN Today", "Daily flagship program featuring interviews, testimonies, and ministry updates."),
    ("Strategies for Strongholds", "Spiritual principles for overcoming personal challenges and strengthening faith."),
    ("Live to Be Well", "Health and wellness insights from a Christian perspective."),
    ("Digging Deeper", "In-depth Bible study exploring foundational doctrines and prophecy."),
    ("Action 4 Life", "Fitness and lifestyle program promoting physical and spiritual health."),
    ("Christ Our Righteousness", "Messages focused on salvation, grace, and living a Christ-centered life."),
    ("Ultimate Prescription", "Medical and lifestyle guidance rooted in biblical principles."),
    ("Body and Spirit", "Exercise routines and health discussions for whole-person wellness."),
    ("Amazing Adventures", "Children’s Bible-based adventure series teaching faith and character."),
    ("Kids Camp", "Fun and educational Christian programming for children."),
    ("It Is Written", "Inspirational Bible teaching and evangelistic messages."),
    ("Mission 360", "Global mission stories highlighting outreach and humanitarian work."),
    ("Breath of Life", "Uplifting sermons and music celebrating hope and faith."),
    ("Eternal Truths Matter", "Biblical messages focusing on prophecy, doctrine, and Christian living."),
]

START_DATE = datetime.date(2026, 10, 24)
DAYS = 7
TZ_OFFSET = "-0400"


def format_dt(date_obj, hour):
    return date_obj.strftime("%Y%m%d") + f"{hour:02d}0000 {TZ_OFFSET}"


def main():
    root = ET.Element("tv", {"generator-info-name": "Michael-ATL-EPG"})

    for channel_id, name in CHANNELS:
        channel = ET.SubElement(root, "channel", {"id": channel_id})
        ET.SubElement(channel, "display-name").text = name
        ET.SubElement(
            channel,
            "icon",
            {"src": "https://3abn.org/assets/img/3abn-logo.png"},
        )

    for channel_id, _ in CHANNELS:
        for day_offset in range(DAYS):
            day = START_DATE + datetime.timedelta(days=day_offset)
            for hour, (title, description) in enumerate(PROGRAM_BLOCK):
                programme = ET.SubElement(
                    root,
                    "programme",
                    {
                        "channel": channel_id,
                        "start": format_dt(day, hour),
                        "stop": format_dt(day, hour + 1),
                    },
                )
                ET.SubElement(programme, "title").text = title
                ET.SubElement(programme, "desc").text = description

    ET.indent(root, space="  ")
    ET.ElementTree(root).write(
        "3abn_full.xml", encoding="utf-8", xml_declaration=True
    )


if __name__ == "__main__":
    main()
