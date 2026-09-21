"""משווה את בלוק העץ שב-README.md לקבצים שבמעקב של git, בשני הכיוונים.

העץ הוא עותק של עובדה שהבעלים שלה הוא התיקייה עצמה. זה R6 של הריפו הזה
("עותק שני של כלל — והם נסחפים"), והמצב המומלץ שם הוא בדיוק מה שהקובץ הזה
עושה: כשהשכפול בלתי נמנע — בדיקה שקוראת את שני המקורות ומשווה. העץ שווה את
השכפול, כי הוא המפה של הריפו למי שפותח אותו; מה שהוא לא שווה הוא סחיפה.

הנתיבים נפתרים מול שורש הריפו ולא מול תיקיית העבודה, כדי שהרצה מכל מקום —
‏CI, ‏hook, או שורת פקודה מתוך תת-תיקייה — תבדוק את אותו דבר.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

readme = (ROOT / "README.md").read_text(encoding="utf-8")
block = re.search(r"## מבנה הריפו.*?```text\n(.*?)```", readme, re.S)
if not block:
    sys.exit("לא נמצא בלוק העץ תחת '## מבנה הריפו' ב-README.md — הבדיקה לא יכולה לרוץ.")

listed, dirs = set(), []                      # dirs: (עומק ההזחה, שם התיקייה)
for line in block.group(1).splitlines()[1:]:  # השורה הראשונה היא שורש הריפו, לא נתיב
    m = re.match(r"^([│ ]*)[├└]── (\S+)", line)
    if not m:
        continue
    depth, name = len(m.group(1)), m.group(2)  # רק המילה הראשונה — אחריה באות הערות (# CRITICAL)
    while dirs and dirs[-1][0] >= depth:
        dirs.pop()
    if name.endswith("/"):
        dirs.append((depth, name))            # גם 'docs/source-projects/' — שתי רמות בשורה אחת
    else:
        listed.add("".join(d for _, d in dirs) + name)

out = subprocess.run(["git", "-C", str(ROOT), "ls-files"],
                     capture_output=True, text=True, check=True).stdout
tracked = {p for p in out.splitlines() if p and not p.startswith(".")}

problems = [f"קיים בריפו ואינו בעץ: {p} — הוסף שורה לעץ ב-README.md תחת {Path(p).parent}/"
            for p in sorted(tracked - listed)]
problems += [f"מופיע בעץ ואין מאחוריו קובץ: {p} — השם שונה או נמחק? עדכן את העץ ב-README.md"
             for p in sorted(listed - tracked)]
if problems:
    sys.exit("\n".join(problems))
print(f"העץ ב-README.md תואם לריפו ({len(listed)} קבצים).")
