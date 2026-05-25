# linked-field-atomicity

זהה עדכוני atomic חלקיים: קוד נוגע באחד מכמה שדות מקושרים, שוכח את השאר. השדה ה"שכוח" נקרא מאוחר יותר על ידי flow אחר → אי-עקביות שקטה.

## דווח כשמתקיים אחד מהבאים

1. **שינוי status / lifecycle** בלי ה-timestamps המקושרים וערכי ה-activity log באותה טרנזקציה. דוגמאות:
   - `entity.status = "X"` בלי עדכון `entity.last_status_change_at` / `last_activity_type`.
   - מעבר ל-`PROPOSAL_SENT` בלי כתיבת `proposal_sent_at`.
   - מעבר ל-state בסגנון `BOOKED` בלי יצירה / ביטול של שורת הישות הקשורה.

2. **פעולה חיצונית בלתי הפיכה בלי state מקומי מפצה.** `await client.send(...)` או `payment.charge(...)` בלי INSERT קודם ל-DB מקומי (עם `UNIQUE` constraint) מסומן "intent" — ועדכון follow-up על הצלחה/כשל.

3. **state auth מרובה-שדות מתעדכן חלקית.** עדכון `access_token` בלי `refresh_token`. עדכון `localStorage["token"]` בלי `localStorage["refreshToken"]`. השתמש ב-JSON blob יחיד או תמיד כתוב את שניהם atomically.

4. **בקשת mutation חלקית של טופס.** `PATCH /endpoint { hour: 8 }` בלי לשלוח את ה-`enabled` flag — בקשות concurrent דורסות זו את זו.

5. **Audit log רק על נתיב הצלחה.** כש-`UPDATE` הראשי יכול להיכשל (דחיית CAS, race), branch הכשל עדיין חייב לקרוא ל-`log_activity(..., metadata={"applied": False})`. אחרת צרכנים downstream (cron, dashboards) מסיקים שה-event לא קרה.

## False positives

- migrations / scripts של backfill (one-shot, לא touchpoints טרנזקציוניים).
- נתיבים read-only.
- עדכוני שדה יחיד שבאמת עצמאיים (למשל `last_viewed_at` לא קשור לשדות אחרים).

## חומרה

HIGH — שחיתות נתונים שקטה; flows downstream פועלים על state לא עקבי.
