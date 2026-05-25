# window-open-protocol-handoff

זהה קוד frontend שמפרש בטעות את החזרת `null` של `window.open(url, ...)` כאירוע popup-blocker, כשבאמת ה-URL משתמש ב-protocol מערכת שהדפדפן העביר בכוונה ל-OS (החזרת `null` היא רגילה).

## דווח כשמתקיימים כל הבאים

1. הקוד קורא `window.open(url, ...)` ולאחריו guard כמו `if (!win) { ... }` או `if (win === null) { ... }` שמבטל את הפעולה הנוכחית, מציג שגיאת "popup blocked", או חוזר מוקדם.
2. ה-argument של `url` יכול להשתמש ב-protocol מערכת — כלומר מתחיל ב-`mailto:`, `tel:`, `sms:`, `file:`, או מחושב דינמית ויכול לכלול את ה-schemes האלה.
3. ה-branch של ביטול מייצר כשל גלוי למשתמש שמוותר על state לגיטימי (למשל `markAsSent` לא נקרא, טופס לא הוגש).

## תיקון

ל-protocols מערכת, השתמש באלמנט `<a>` + `.click()`:
```js
const a = document.createElement("a");
a.href = `mailto:${address}`;
a.click();
markAsSent();
```

או זהה לפי scheme לפני שאתה מחיל את הנחת popup-blocker:
```js
const isSystemProtocol = /^(mailto|tel|sms|file):/.test(url);
const win = window.open(url, "_blank");
if (!win && !isSystemProtocol) { showError("Popup blocked"); return; }
markAsSent();
```

## דגלי browser-quirk קשורים (להציע באותה סקירה)

- `navigator.clipboard.writeText(...)` בלי try/catch (נכשל על HTTP).
- `URL.createObjectURL(...)` בלי `URL.revokeObjectURL` מתאים ב-cleanup.
- `setTimeout(fn, delay)` כש-`delay` ממקור חיצוני ולא מוגן ב-`isFinite`.

## False positives

- `window.open` רק ל-URLs של `http(s):` שבהם בדיקת popup-blocker נכונה.
- ה-branch של ביטול רק רושם לוג וממשיך (best-effort, לא מבטל state).

## חומרה

MEDIUM — שובר UX, מדי פעם משחית state כש-branch הביטול מבטל שינויים באמצע.
