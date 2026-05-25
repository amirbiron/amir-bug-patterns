# xss-innerhtml

**CRITICAL — DOM XSS**

זהה הכנסת מחרוזות ממקור חיצוני ל-DOM דרך sinks לא בטוחים (`innerHTML`, `dangerouslySetInnerHTML`, `v-html`, `outerHTML`, `document.write`, jQuery `.html(...)`).

## דווח כשמתקיימים כל הבאים

1. הקוד משייך לאחד מה-sinks האלה:
   - `.innerHTML = ...`
   - `.outerHTML = ...`
   - JSX `dangerouslySetInnerHTML={{ __html: ... }}`
   - Vue `v-html="..."`
   - jQuery `.html(...)`, `.before/after(...)` עם args של מחרוזת
   - `document.write(...)`
2. הצד הימני מורכב (concatenation, template literal) עם ערך שמקורו ב:
   - תגובת API (`response.json()`, נתוני `useQuery`)
   - שורת DB (server-rendered ל-template)
   - URL parameters / hash / search
   - `localStorage` / `sessionStorage` / cookies
   - payload של postmessage / WebSocket / SSE
   - קלט משתמש מכל טופס / input
   - שמות / display names של ספקים חיצוניים (Facebook, Google, OAuth profile)
3. הערך *אינו* עובר דרך `DOMPurify.sanitize(...)` (או `sanitize-html`, או שווה ערך ב-framework) מיד לפני ההשמה, באותו expression / שורה.

## דפוסי תיקון

- ברירת מחדל ל-`textContent` / טקסט ב-JSX.
- אם HTML באמת נדרש, sanitize ב-inline:
  ```js
  element.innerHTML = DOMPurify.sanitize(externalValue, { ALLOWED_TAGS: ["b","i","em","strong"] });
  ```
- לרשימות React: רנדר עם text nodes, לא `dangerouslySetInnerHTML`.

## תזכורת הגנה

"רק admins רואים את הפאנל הזה" *אינה* הגנה — admins הם בדיוק היעדים שתוקפים רוצים.

## False positives

- מחרוזות HTML סטטיות / קשיחות בלי משתנים של template substitution.
- Markdown שמרונדר על ידי ספרייה בדוקה (למשל `marked` עם `breaks: true, sanitize: true`) — ודא שה-sanitizer פעיל.
- כתיבות `innerText` / `textContent` (בטוחות).

## חומרה

CRITICAL — DOM XSS מלא בפאנלי admin יכול להוביל לגניבת session, שימוש בהרשאות, ו-CSRF.
