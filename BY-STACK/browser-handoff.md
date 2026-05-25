# BY-STACK: handoff צד-דפדפן (mailto:, tel:, clipboard, DOM quirks)

## רלוונטיות — העתק את הקובץ הזה אם בפרויקט יש...
- ✅ קוד דפדפן שפותח קישורי `mailto:`, `tel:`, `sms:`, או `file:`
- ✅ קוד דפדפן שמשתמש ב-`navigator.clipboard.*`
- ✅ קומפוננטות React עם tooltips, dropdowns, או modals שנסגרים על click מבחוץ
- ✅ CSS resets בפרויקט שמשתמש ב-Tailwind / framework utility-CSS
- ✅ קוד שיוצר blob URLs (`URL.createObjectURL`) ל-previews
- ⏭ דלג אם: server-rendered, בלי JS צד-דפדפן, או React טהור בלי אינטגרציה עם Browser API

> Cross-link: **R3** (quirks של Browser API) הוא דפוס האב. **K4** (XSS) הוא דאגה נפרדת — ראה `react-frontend.md`.

---

## דפוס 1 — `window.open(mailto:)` מחזיר null (Noa P10)

**חומרה:** MEDIUM — פעולה לגיטימית מבוטלת בטעות

### איך זה נראה
```jsx
const win = window.open(`mailto:${address}`, "_blank");
if (!win) {
  showError("Popup blocked");
  return;  // ❌ מבטל flow של mark_sent
}
markAsSent();
```

ב-Chrome, `window.open(url, ...)` מחזיר `null` כש-`url` משתמש ב-protocol מערכת (`mailto:`, `tel:`, `sms:`, `file:`). זה **handoff מכוון ל-OS**, לא פעולה של popup-blocker. הבדיקה למעלה מפרשת handoff כחסימה.

### תיקון
ל-protocols מערכת, השתמש באלמנט `<a>` + `.click()`:
```jsx
const a = document.createElement("a");
a.href = `mailto:${address}`;
a.click();
markAsSent();
```

או זהה לפי URL scheme לפני שאתה מחליט שה-fallback של popup-blocker חל:
```jsx
const isSystemProtocol = /^(mailto|tel|sms|file):/.test(url);
const win = window.open(url, "_blank");
if (!win && !isSystemProtocol) {
  showError("Popup blocked");
  return;
}
markAsSent();
```

### Commits אמיתיים
- Noa `f635304`.

---

## דפוס 2 — `navigator.clipboard.writeText` על HTTP

```js
function copy(text) {
  navigator.clipboard.writeText(text);  // ❌ זורק על HTTP; promise rejection לא נתפס
}
```

ה-Clipboard API דורש secure context (HTTPS, localhost). על HTTP, `navigator.clipboard` עשוי להיות `undefined`, או `writeText` עשוי לדחות.

### תיקון
```js
async function copy(text) {
  try {
    if (!navigator.clipboard) throw new Error("Clipboard API unavailable");
    await navigator.clipboard.writeText(text);
    return { ok: true };
  } catch (err) {
    // Fallback: legacy document.execCommand או הצג שגיאה
    return { ok: false, err };
  }
}
```

### Commits אמיתיים
- Markdown-Academy `b97d3f5`.

---

## דפוס 3 — Tooltip / dropdown נסגר על click בגלל event bubbling

```jsx
<div onClick={closeMenu}>
  <Tooltip>...</Tooltip>  {/* clicks בפנים בועלים → menu נסגר */}
</div>
```

### תיקון
```jsx
<Tooltip onClick={(e) => e.stopPropagation()}>...</Tooltip>
```

או השתמש ב-hook של "click outside" שמתעלם מ-clicks בתוך עץ האלמנט הפנימי (השווה `event.target` מול ref פנימי דרך `.contains()`).

### Commits אמיתיים
- Markdown-Academy `315154e`.

---

## דפוס 4 — CSS reset גלובלי דורס מחלקות utility

```css
/* איפשהו ב-CSS legacy */
* { margin: 0; padding: 0; }
```

בפרויקט Tailwind, `space-y-6` מתורגם ל-margins על ילדים. ה-reset הגלובלי יש לו specificity גבוהה יותר (universal selector + declaration ישיר) ומנצח.

### תיקון
- השתמש ב-`@tailwind base` של Tailwind עצמו ל-reset (Preflight).
- או scope ל-reset: `body > * { margin: 0; padding: 0 }` — אבל זה עדיין שובר utilities.
- הכי טוב: הסר את ה-reset הידני וסמוך על ה-reset המובנה של Tailwind / framework utility-CSS.

### Commits אמיתיים
- Web `c586691`.

---

## דפוס 5 — `URL.createObjectURL` לא משוחרר

```jsx
const url = URL.createObjectURL(blob);  // ❌ לעולם לא משוחרר, דולף בכל render
return <img src={url} />;
```

### תיקון
```jsx
useEffect(() => {
  if (!blob) return;
  const url = URL.createObjectURL(blob);
  setSrc(url);
  return () => URL.revokeObjectURL(url);  // cleanup על unmount או שינוי blob
}, [blob]);
```

### Commits אמיתיים
- Web `f5cbaf9`.

---

## דפוס 6 — `setTimeout(fn, delay)` / `new Date(value)` עם NaN

```js
const delay = parseInt(input);  // ממשתמש
setTimeout(load, delay);  // ❌ אם NaN → שגיאת React / מיידי או לעולם לא
```

### תיקון
```js
const parsed = parseInt(input, 10);
const delay = Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_DELAY;
setTimeout(load, delay);
```

אותו דבר ל-`new Date(value).getTime()` — הגן עם `isFinite`.

### Commits אמיתיים
- EmailFlow `e432866`.

---

## דפוס 7 — עדכון חלקי של state auth מרובה-שדות ב-`localStorage`

```js
localStorage.setItem("token", newToken);  // ❌ refreshToken נשאר מההרשמה
```

`localStorage` פועל per-key; עדכון רק `token` משאיר `refreshToken` ישן.

### תיקון
- שמור כאובייקט JSON אחד: `localStorage.setItem("auth", JSON.stringify({token, refreshToken, expires}))`.
- או תמיד עדכן את שניהם atomically: `localStorage.setItem("token", t); localStorage.setItem("refreshToken", r);` ולעולם אל תכתוב אחד בלי השני.

### Commits אמיתיים
- Web `2e5c480`.

---

## דפוס 8 — כפתור UI מוצג בזמן שגוי יחסית ל-slot

```jsx
const showBooked = nowMs > slot_start + 30 * 60 * 1000;  // ❌ שובר מפגשים קצרים
```

אם הפעולה היא "אחרי שהמפגש מסתיים", חשב מ-`slot_end`, לא `slot_start + estimate`.

### תיקון
```jsx
const showBooked = nowMs > slot_end;
```

### Commits אמיתיים
- Noa `f4769bf`.

---

## דפוס 9 — קומפוננטה עושה unmount לפני שפעולת async מסתיימת

אם המשתמש עובר ל-route אחר תוך כדי `useEffect` באמצע await, ה-`setState` שלאחר מכן רץ על קומפוננטה לא mounted → אזהרה ב-dev, החזקת זיכרון ב-prod.

### תיקון
Cancellation flag:
```jsx
useEffect(() => {
  let cancelled = false;
  async function load() {
    const data = await fetchData();
    if (cancelled) return;
    setData(data);
  }
  load();
  return () => { cancelled = true; };
}, [...]);
```

### Commits אמיתיים
- Noa `b360c66`, `7444dd9`.

---

## הפניות צולבות

- **R3** — quirks של Browser API (הקובץ הזה הוא ה-deep-dive)
- **CORE U2** — סנכרון state ב-React (דפוס 9 כאן הוא וריאציית cancellation-flag)
- **CRITICAL K4** — XSS via innerHTML
- **`bugbot-rules/window-open-protocol-handoff.md`**
