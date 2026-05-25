# דפוסי Browser-handoff (להעתקה ל-CLAUDE.md)

1. **`window.open(mailto:|tel:|sms:|file:)` מחזיר `null` ב-Chrome** — זה handoff ל-OS, *לא* popup-blocker. אל תחסום `markAsSent()` על `if (!win)`. השתמש ב-`<a>` + `.click()` ל-protocols מערכת, שמור את בדיקת popup-blocker ל-URLs של `http(s):`.

2. **`navigator.clipboard.writeText` דורש HTTPS / localhost.** עטוף ב-try/catch; בכשל, fallback ל-`document.execCommand` legacy או הצג שגיאה שמאפשרת למשתמש לפעול.

3. **Tooltip / dropdown נסגר על click → בדוק event propagation.** או `e.stopPropagation()` בתוך האלמנט הפנימי, או hook של "click outside" שמשווה `event.target` עם ref פנימי דרך `.contains()`.

4. **`* { margin: 0; padding: 0 }` דורס מחלקות utility של Tailwind.** השתמש ב-`@tailwind base` (Preflight) בלבד; הסר resets ידניים של `*`.

5. **ל-`URL.createObjectURL(blob)` חייב להיות `URL.revokeObjectURL` מתאים ב-cleanup של `useEffect`** — אחרת דליפות blob URL מצטברות.

6. **`setTimeout(fn, delay)` / `new Date(value)` עם מספר ממקור חיצוני דורש הגנת `isFinite(value) && value > 0`.**

7. **`localStorage` הוא per-key; state auth מרובה-שדות חייב להיות atomic** — שמור כ-JSON blob יחיד או תמיד כתוב את שני ה-keys יחד.

8. **UI מבוסס-זמן ("הצג אחרי שהמפגש מסתיים") משתמש ב-`slot_end`, לא `slot_start + estimate`.** מפגשים קצרים שוברים את האחרון.

9. **`useEffect` באמצע await + unmount: השתמש ב-cancellation flag** כך ש-`setState` שלאחר מכן הוא no-op.

ראה `BY-STACK/browser-handoff.md`.
