import datetime

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
    return date_obj.strftime("%Y%m%d") + f"T{hour:02d}0000 {TZ_OFFSET}"

def main():
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<tv generator-info-name="Michael-ATL-EPG">')

    for cid, name in CHANNELS:
        lines.append(f'  <channel id="{cid}">')
        lines.append(f'    <display-name>{name}</display-name>')
        lines.append(f'    <icon src="https://3abn.org/assets/img/3abn-logo.png"/>')
        lines.append("  </channel>")

    for cid, _ in CHANNELS:
        for d in range(DAYS):
            day = START_DATE + datetime.timedelta(days=d)
            for i, (title, desc) in enumerate(PROGRAM_BLOCK):
                start = format_dt(day, i)
                stop = format_dt(day, i + 1)
                lines.append(f'  <programme start="{start}" stop="{stop}" channel="{cid}">')
                lines.append(f'    <title>{title}</title>')
                lines.append(f'    <desc>{desc}</desc>')
                lines.append("  </programme>")

    lines.append("</tv>")

    with open("3abn_full.xml", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    main()
