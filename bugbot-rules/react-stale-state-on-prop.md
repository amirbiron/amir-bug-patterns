# react-stale-state-on-prop

זהה קומפוננטות React שבהן `useState` מקומי מאותחל מ-prop שיכול להשתנות, בלי מנגנון resync. סימפטום: ה-UI מציג את הערך הישן אחרי refetch של ה-parent; פעולות משתמש מבוצעות מול נתונים ישנים.

## דווח כשמתקיימים כל הבאים

1. `useState` מאותחל עם ערך שמקורו ב-`props.X` או prop מ-destructure.
2. `props.X` הוא mutable באופן סביר (מגיע מתוצאת query של parent, route param, או state חיצוני — לא ערך one-time של mount).
3. אף אחד מהבאים לא נוכח:
   - `key={X}` על הקומפוננטה ב-parent (force remount בשינוי).
   - `useEffect([X], () => setState(X))` שעושה resync.
4. הקומפוננטה שולחת את ה-state המקומי בחזרה לשרת (submit של טופס, mutation), כש-state ישן גורם לשחיתות.

## דווח גם

- כל `useState` / `useEffect` / `useCallback` / `useMemo` שנקרא אחרי `if (...) return null;` / conditional return מוקדם (הפרת Rules of Hooks).
- `useCallback` / `useMemo` שגוף הפונקציה שלהם מתייחס ל-prop/state שלא ב-dependency array שלהם.

## False positives

- state מקומי בלבד (modal פתוח/סגור, theme toggle, tab selection).
- inputs uncontrolled עם `defaultValue`.
- props רק ב-mount (למשל `user.id` שלעולם לא משתנה במהלך חיי הקומפוננטה).
- ה-dep מדלג בכוונה על reference לא יציב (אובייקט mutation של TanStack); הערה צריכה להסביר למה.

## חומרה

MEDIUM — שחיתות נתונים שקטה כשה-state הישן נשלח חזרה לשרת.
