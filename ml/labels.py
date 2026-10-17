"""Reads data/open/open_labels.xlsx without extra dependencies (xlsx is a zip of XML)."""
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def norm_name(name: str) -> str:
    """'Х-4' (Cyrillic), '#U0425-4', 'X-4.mov' -> 'X-4'."""
    name = os.path.splitext(os.path.basename(name))[0]
    name = name.replace("#U0425", "X").replace("Х", "X").replace("х", "X")
    return unicodedata.normalize("NFC", name).strip().upper()


def parse_ts(text: str) -> float | None:
    """'22 секунда' -> 22, '1минута 8 секунда' -> 68, 'без нарушения' -> None."""
    m = re.search(r"(\d+)\s*мин", text)
    s = re.search(r"(\d+)\s*сек", text)
    if not m and not s:
        return None
    return (int(m.group(1)) * 60 if m else 0) + (int(s.group(1)) if s else 0)


def _rows(xlsx_path):
    z = zipfile.ZipFile(xlsx_path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(NS + "si"):
            shared.append("".join(t.text or "" for t in si.iter(NS + "t")))
    sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    for r in sheet.iter(NS + "row"):
        vals = []
        for c in r.findall(NS + "c"):
            v, t = c.find(NS + "v"), c.get("t")
            if t == "s":
                vals.append(shared[int(v.text)])
            elif t == "inlineStr":
                vals.append("".join(x.text or "" for x in c.iter(NS + "t")))
            else:
                vals.append(v.text if v is not None else "")
        yield vals


def load_labels(xlsx_path: str) -> dict[str, dict]:
    """{'X-4': {'violation': True, 'times': [57.0]}, ...}"""
    out = {}
    for i, vals in enumerate(_rows(xlsx_path)):
        if i == 0 or not vals or not vals[0].strip():
            continue
        name = norm_name(vals[0])
        text = " ".join(vals[1:]).lower()
        ts = parse_ts(" ".join(vals[1:-1]) if len(vals) > 2 else "")
        violation = "без" not in text and "нарушение" in text
        out[name] = {"violation": violation, "times": [float(ts)] if ts is not None else []}
    return out


def find_videos(video_dir: str) -> dict[str, str]:
    return {norm_name(f): os.path.join(video_dir, f) for f in sorted(os.listdir(video_dir))
            if f.lower().endswith((".mov", ".mp4"))}
