# דפוסי React frontend (להעתקה ל-CLAUDE.md)

1. **`useState` מ-prop שמשתנה חייב resync.** בחר אחד לכל הפרויקט:
   - `<Child key={props.id} ...>` (force remount, הכי פשוט)
   - `useEffect(() => setX(props.x), [props.x])` (resync)
   - Derived state (קרא prop ישירות, בלי עותק מקומי)

   ❌ `const [s, setS] = useState(props.id);` לבד — ישן ב-prop change.

   לא חל על prop שנקבע רק ב-mount, state מקומי בלבד (modal פתוח/סגור), או input לא-מבוקר עם `defaultValue` — שם אין מה לסנכרן, ו-`key` רק יאפס את מה שהמשתמש הקליד.

2. **כל ה-hooks לפני כל early return.** אסור `if (!data) return null;` ולאחריו `useState(...)`.

3. **deps של `useCallback` / `useMemo` חייבים לכלול כל prop/state בגוף.** Stale closures (למשל `activeChildId` חסר) גורמות לפעולות להשפיע על הבחירה הקודמת. שמור על `react-hooks/exhaustive-deps` של ESLint ב-`error`.

4. **`setState` אחרי `await` חייב לבדוק cancellation flag** (`let cancelled = false; return () => { cancelled = true; }` ב-`useEffect`).

5. **לעולם אל תכלול identity לא יציב ב-deps** (אובייקטים של TanStack Query mutation, literals טריים של `{}`). במקומו — `mutation.mutate` (identity יציב), או השמטה עם הערת eslint-disable שאומרת למה. זה לא סותר את כלל 3.

6. **Cleanup ל-`URL.createObjectURL` / event listeners** ב-return של `useEffect`.

7. **state auth מרובה-שדות הוא atomic.** עדכן access token + refresh token יחד (JSON blob אחד ב-`localStorage`, או שתי כתיבות עטופות ב-try block שעושה rollback בכשל).

8. **`setTimeout(fn, delay)` / `new Date(value)` עם input ממקור חיצוני דורש הגנת `isFinite()`.** וב-`setTimeout` גם `> 0`, ואחרת ערך ברירת מחדל — `0` בלולאת polling הוא לולאה הדוקה.

9. **השתמש ב-`textContent`, לא `innerHTML`, עם מחרוזות שמקורן בקלט משתמש** (XSS — ראה CRITICAL K4).

10. **`* { margin: 0; padding: 0 }` לצד Tailwind v4 מבטל את כל ה-utilities של margin / padding.** ב-v4 ה-utilities יושבות ב-`@layer utilities`, וכלל שאינו בשכבה גובר עליהן בלי קשר ל-specificity. להסתמך על Preflight; reset שחייב להישאר — בתוך `@layer base`. (ב-v3 אותו reset מפסיד ל-utilities ואינו הבאג.)

11. **Tooltip / dropdown שנסגר על click מבפנים — event bubbling.** `e.stopPropagation()` באלמנט הפנימי, או hook של "click outside" שבודק `ref.current.contains(event.target)`.

ראה `BY-STACK/react-frontend.md` בריפו amir-bug-patterns לדוגמאות קוד.
