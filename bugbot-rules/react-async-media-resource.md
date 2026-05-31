# react-async-media-resource

זהה קומפוננטות React עם משאב async חיצוני (microphone, camera, WebSocket, EventSource, MediaRecorder, AudioContext, ה-stream של `getUserMedia`) שלא מגנות על שלושת הסיכונים שתמיד מתקיימים יחד: double-action, setState אחרי `await` על component שכבר unmounted, ו-cleanup חסר במסלול יציאה אחד או יותר.

**זה לא `react-stale-state-on-prop`** (זה על state מ-prop שמשתנה). **זה לא רק "cancellation flag אחרי await"** (ה-snippet ב-`claude-md-snippets/react.md` סעיף 4) — הכלל הזה תלוי בקיום משאב חיצוני שדורש release אקטיבי. בלי המשאב החיצוני, fetch רגיל מסתיים בשקט; עם משאב, כשלון cleanup = LED של מיקרופון דולק / socket פתוח / streams מקבילים.

## דווח כשמתקיים אחד מהבאים

1. **משאב חיצוני שדורש release ידני, בלי cleanup ב-`useEffect`.** הקומפוננטה קוראת ל-אחד מאלה: `navigator.mediaDevices.getUserMedia(...)`, `new MediaRecorder(...)`, `new WebSocket(...)`, `new EventSource(...)`, `new AudioContext(...)`, `new AbortController()` שמועבר ל-fetch ארוך. דרוש `return () => { resource.stop() / .close() / .disconnect() / .abort(); stream.getTracks().forEach(t => t.stop()); }` ב-`useEffect`. **בנוסף:** ב-`finally` / `catch` של handler שמטפל במשאב — ה-release חייב להופיע גם שם, לא רק במסלול ה-success.

2. **Double-action בלי in-flight guard.** handler שמתחיל פעולה async (`onClick={async () => { const stream = await getUserMedia(...); startRecording(stream); }}`) בלי `useRef` / `useState` שמסמן "in-flight" — לחיצה כפולה תיצור שני streams מקבילים. דרוש:
   ```js
   const startingRef = useRef(false);
   async function onClick() {
     if (startingRef.current) return;
     startingRef.current = true;
     try { /* await ... */ } finally { startingRef.current = false; }
   }
   ```

3. **`setState` אחרי `await` בלי mounted guard בקומפוננטה שמחזיקה משאב פעיל.** הסיכון פה גדול יותר מ-fetch רגיל: ה-async resource (recording, socket) ממשיך לרוץ אחרי unmount, ו-`setState` עליו = React warning + side effects שלא בוטלו. דרוש: `let cancelled = false; ... if (!cancelled) setState(...); return () => { cancelled = true; resource.stop(); }`.

4. **Cleanup רק במסלול אחד.** הקומפוננטה מטפלת ב-`stop` רגיל (button click) אבל לא בשגיאה (`upload failed`) או ב-unmount באמצע (`modal closed`). הסימן: שלוש פונקציות שונות (`handleStop`, `handleError`, useEffect cleanup) שכל אחת עושה release נפרד וחלקי. **פתרון נכון:** פונקציה אחת `releaseResource()` שנקראת משלושת המסלולים, idempotent (בודקת אם המשאב כבר שוחרר).

5. **Upload / network call שממשיך אחרי unmount.** קומפוננטה שולחת `await fetch('/upload', { body: blob })` ולא יוצרת `AbortController` עם cleanup. כשהמודאל נסגר באמצע, ה-upload ממשיך, ובסיומו מנסה לעדכן state של component שכבר אינו mounted. דרוש `AbortController` שמועבר ל-fetch + `.abort()` ב-cleanup של ה-effect.

## False positives

- **fetch קצר אחד בלי side effects** (`useEffect(() => { fetch(...).then(setData); }, [])`) — לא צריך AbortController; ה-promise פוקע בשקט. הכלל רלוונטי רק לקומפוננטות עם משאב חיצוני שדורש release אקטיבי.
- **משאב singleton ברמת ה-app** (e.g., `AudioContext` שנוצר פעם אחת ב-context provider, או socket גלובלי ב-zustand store) — מנוהל מחוץ ל-component lifecycle.
- **קומפוננטה ש-mount-only ולא תופסת unmount באמצע** — single-shot recorder במסך מלא שלא מאפשר navigation תוך כדי.
- **Web Workers / Service Workers** — lifecycle נפרד; הכלל הזה לא רלוונטי.
- **Hooks custom שעוטפים את המשאב** (`useMicrophone`, `useSocket`) ומיישמים את ה-cleanup פנימית — בדוק את ה-hook עצמו פעם אחת; ה-callers לא צריכים לחזור על ההגנות.

## חומרה

MEDIUM-HIGH — דליפת hardware (LED מיקרופון / מצלמה דולק אחרי שהמשתמש סיים), פעולות במקביל (שני recordings, שני uploads), state corruption (setState על unmounted component → React warnings + לוגיקה שלא נכבית). פגיעה ב-UX, ועלולה לפגוע באמון משתמש בהיבט פרטיות — מיקרופון פתוח אחרי שהמודאל נסגר. ב-CRM / מערכות עם קלט voice / video — מסוכן לקבל את התלונה הזאת מהמשתמש.
