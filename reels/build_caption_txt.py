"""Generate caption.txt for the reel.

Default layout ("pfec", the house structure the user supplied 2026-10-12 from
a published Partner 801 grant post):
    bold title (+ emoji)
    1-2 body paragraphs
    📲 Book a FREE consultation with <name>, PFEC Registered Migration Agent (MARN <n>)
    7-office block (bold city / 📍 address / 📞 phone)
    🌏 website
    hashtags, always led by #askPFEC #PFECGlobal
    plain 3-line disclaimer
No bullet list, no urgency line. The contact line is built from content.json's
name.text + mara.marn unless caption_txt.contact overrides it. Set
caption_txt.layout = "classic" for the older 10-part structure below.

Classic layout: PFEC's 10-part structure.
Topic-specific copy (title/body/bullets/urgency/contact/website/hashtags) comes
from the reel's content.json under "caption_txt"; the shared parts (six-office
block, music credit, verbatim disclaimer) are constants here. Defaults reproduce
the Lakemba reel. Bold-unicode for headers."""
import os, json

from reel_paths import OUT, REEL  # noqa: E402 -- per-reel folders
os.makedirs(OUT, exist_ok=True)


# Mathematical Sans-Serif Bold unicode
def bold(s):
    r = []
    for ch in s:
        o = ord(ch)
        if 65 <= o <= 90:    r.append(chr(0x1D5D4 + o - 65))
        elif 97 <= o <= 122: r.append(chr(0x1D5EE + o - 97))
        elif 48 <= o <= 57:  r.append(chr(0x1D7EC + o - 48))
        else: r.append(ch)
    return "".join(r)


# Verbatim compliance disclaimer — reproduce EXACTLY (see pfec-compliance).
DISCLAIMER = (
"▎ Disclaimer: The information shared by PFEC Global – Education | Migration is intended for general awareness only and reflects migration regulations and policies available at the time of posting. This content is for general informational purposes only, and individual circumstances may lead to different outcomes.\n"
"▎ PFEC Global and its entities does not assure visa outcome, processing time, or specific migration results. All decisions are made by the Department of Home Affairs or the appropriate governing authority.\n"
"▎ Before proceeding with any application or decision, we recommend seeking advice from a Registered Migration Agent or Australian legal practitioner."
)

# The user-supplied 2026-10-12 house layout prints the disclaimer as three
# plain lines with no "▎ " bar prefix; "classic" keeps the barred version.
DISCLAIMER_PLAIN = DISCLAIMER.replace("▎ ", "")

DEFAULT_MUSIC_CREDIT = '\U0001F3B5 Music: "Funky Chunk" — Kevin MacLeod (incompetech.com)'

OFFICES = f"""{bold("Melbourne")}
\U0001F4CD L11, 50 Queen Street, Melbourne VIC 3000
\U0001F4DE (03) 9620 1773

{bold("Sydney")}
\U0001F4CD Suite 402, Level 4/447 Kent St Sydney NSW 2000
\U0001F4DE (02) 8378 4282

{bold("Perth")}
\U0001F4CD Suite A, Level 8th/16 St Georges Terrace, Perth WA 6000
\U0001F4DE (08) 6266 8335

{bold("Brisbane")}
\U0001F4CD Level 18, 324 Queen Street, Brisbane QLD, Australia
\U0001F4DE (07) 3102 1707

{bold("Adelaide")}
\U0001F4CD Level M/90, King William Street Adelaide SA 5000
\U0001F4DE (08) 7099 2258

{bold("Lakemba NSW")}
\U0001F4CD 13/61-67 Haldon Street, Lakemba NSW 2195
\U0001F4DE (02) 8378 4282

{bold("Parramatta")}
\U0001F4CD Suite 1, 21 George Street, Parramatta NSW 2150
\U0001F4DE (02) 8378 4282"""

DEFAULT_CAPTION = {   # Lakemba reel
    "title": "Choosing the Wrong Course Could Cost You Your PR Pathway",
    "body": [
        "Are you an international student unsure which course actually leads to permanent residency in Australia? With so many study pathways to choose from, it's easy to lose track — and picking the wrong course can cost you time, money, and your PR goals.",
        "PFEC Global is hosting a FREE migration seminar to help you plan your study-to-PR pathway with confidence. Whether you're weighing secondary teaching, a Masters by Research, or switching from an IT background, our experts guide your complete pathway — not just your course.",
    ],
    "bullets": [
        "The wrong course can set back your PR plans",
        "Multiple study pathways can lead to permanent residency — but not all are right for you",
        "Our experts look beyond the course to your complete migration pathway",
        "FREE migration seminar — 13th July at Lakemba Senior Citizens' Centre",
    ],
    "urgency": "Seats are limited — don't miss your chance to clear your doubts and plan your future with confidence.",
    "contact": "Book a FREE consultation with a PFEC Registered Migration Agent — [NEED: speaking agent name + MARN]",
    "website": "[NEED: website URL]",
    "hashtags": "#askPFEC #PFECGlobal #StudyInAustralia #PRPathway #MigrationSeminar #AustraliaPR #InternationalStudents #PermanentResidency #RegisteredMigrationAgent",
    # No music credit line in the social caption by default. The track's CC-BY
    # attribution (see assets/music/CREDIT.txt) still has to appear SOMEWHERE the
    # track is used -- in-video, a pinned comment, or the platform's music field --
    # just not in caption.txt. A reel can still opt back in by setting a non-empty
    # caption_txt.music_credit (e.g. DEFAULT_MUSIC_CREDIT) in its content.json.
    "music_credit": "",
    # The 7-office contact block is ON by default (every existing reel keeps
    # rebuilding unchanged). Set caption_txt.offices: false for a reel where a
    # single-agent contact line already covers it and the full branch/phone
    # list would read as unrelated boilerplate (e.g. a compliance/warning
    # reel with no event or office visit being promoted).
    "offices": True,
    "disclaimer": True,
}


def load_caption():
    c = dict(DEFAULT_CAPTION)
    cfg = os.path.join(REEL, "content.json")
    if os.path.isfile(cfg):
        j = json.load(open(cfg, encoding="utf-8"))
        if isinstance(j.get("caption_txt"), dict):
            c.update(j["caption_txt"])
    return c


def build_classic(c):
    body = "\n\n".join(c["body"])
    bullets = "\n".join("✔ " + b for b in c["bullets"])
    # Music credit is opt-in; when empty, drop the line entirely (no dangling gap).
    credit = f"{c['music_credit'].strip()}\n\n" if c.get("music_credit", "").strip() else ""
    offices = f"{OFFICES}\n\n" if c.get("offices", True) else ""
    # Verbatim compliance disclaimer, opt-out exactly the way the offices block
    # is (default True, so every existing reel rebuilds unchanged). Drop it only
    # on a reel that makes no migration claim at all -- a purely social event
    # announcement, say. Independent of build_composite.py's end_cards.disclaimer,
    # so a reel can keep the written notice while losing the on-screen card.
    tail = DISCLAIMER if c.get("disclaimer", True) else ""
    text = f"""{bold(c['title'])}

{body}

{bold("What You Should Know:")}
{bullets}

\U0001F4CC {c['urgency']}

\U0001F4F2 {c['contact']}

{offices}\U0001F30F {c['website']}

{c['hashtags']}

{credit}{tail}
"""
    return text


def _contact_line(c):
    if c.get("contact") and "[NEED" not in c["contact"]:
        return c["contact"]
    cfg = os.path.join(REEL, "content.json")
    j = json.load(open(cfg, encoding="utf-8")) if os.path.isfile(cfg) else {}
    name = (j.get("name") or {}).get("text")
    marn = (j.get("mara") or {}).get("marn")
    if name and marn:
        return (f"Book a FREE consultation with {name}, "
                f"PFEC Registered Migration Agent (MARN {marn})")
    return c["contact"]   # falls through to the [NEED ...] placeholder QA flags


def _hashtags(tags):
    lead = ["#askPFEC", "#PFECGlobal"]
    rest = [t for t in tags.split() if t.lower() not in ("#askpfec", "#pfecglobal")]
    return " ".join(lead + rest)


def build_pfec(c):
    body = "\n\n".join(c["body"])
    credit = f"{c['music_credit'].strip()}\n\n" if c.get("music_credit", "").strip() else ""
    offices = f"{OFFICES}\n\n" if c.get("offices", True) else ""
    tail = DISCLAIMER_PLAIN if c.get("disclaimer", True) else ""
    return f"""{bold(c['title'])}

{body}

📲 {_contact_line(c)}

{offices}🌏 {c['website']}

{_hashtags(c['hashtags'])}

{credit}{tail}
"""


def build():
    c = load_caption()
    text = build_classic(c) if c.get("layout") == "classic" else build_pfec(c)
    path = os.path.join(OUT, "caption.txt")
    open(path, "w", encoding="utf-8").write(text)
    print("wrote", path, f"({len(text)} chars)")


if __name__ == "__main__":
    build()
