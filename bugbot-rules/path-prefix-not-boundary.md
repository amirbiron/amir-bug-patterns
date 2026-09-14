# path-prefix-not-boundary

**CRITICAL — מחיקה או גישה מחוץ ל-allowlist**

זהה בדיקת **גבול** היררכי — נתיב, URL, דומיין, מרחב-שמות — שנכתבה כהשוואת **תווים**. מחרוזת אחת יכולה להתחיל בשנייה בלי ששום קשר היררכי מתקיים ביניהן, ולכן הבדיקה עוברת על ערך שהיא נועדה לחסום.

## דווח כשמתקיים אחד מהבאים

1. **`startswith` על נתיב, כשהתוצאה שולטת בפעולה בלתי הפיכה.**
   ```python
   if not str(p).startswith(str(base)):   # ❌ /tmp/app-test-evil עובר מול /tmp/app-test
       raise ValueError
   shutil.rmtree(p)
   ```
   הצורה הנכונה: `p == base or base in p.parents`, אחרי `resolve()` על **שני** הצדדים.

2. **בדיקת נתיב בלי `resolve()` / `realpath()`.** בלעדיו `base/../../etc` עובר את אותה בדיקה, גם כשהיא כתובה נכון.

3. **`url.startswith("https://api.example.com")`** — `https://api.example.com.evil.net` עובר.
   מפרקים ומשווים רכיב-רכיב, ו**מה משווים תלוי בשאלה**: ל-allowlist של
   מארחים — `urlsplit(url).hostname` מול ערך מלא; להחלטת **origin**
   (הפניה, בקשה יוצאת, בדיקת `Origin`/`Referer`, `postMessage`) —
   ‏**scheme + hostname + פורט אפקטיבי**, כי `hostname` לבדו מקבל `http://`
   במקום `https://` ופורט אחר לגמרי.

4. **`host.endswith("example.com")`** — `notexample.com` עובר. נדרש `host == d or host.endswith("." + d)`.

5. **קידומת של מפתח בלי מפריד בסופה** — `key.startswith(f"user:{uid}")` תופס את `user:123` כשביקשת `user:12`. להוסיף את המפריד: `f"user:{uid}:"`.

6. **כל אחד מהנ"ל כשהתוצאה שולטת בהחלטת הרשאה**, לא רק בפעולה על קבצים.

## False positives

- קידומת שהיא באמת טקסטואלית: `name.startswith("tmp_")`, `url.startswith("https://")`, ניתוב לפי prefix בשכבת תצוגה.
- ערך פנימי קבוע שאינו מגיע מקלט ואינו נגזר ממנו.

## חומרה

HIGH כשהתוצאה שולטת במחיקה, בכתיבה או בהרשאה — הכשל בלתי הפיך והקוד נראה כמו בדיקת בטיחות תקינה. MEDIUM אחרת.
