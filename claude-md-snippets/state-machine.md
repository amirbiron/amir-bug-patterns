# דפוסי State-machine (להעתקה ל-CLAUDE.md)

1. **שלמות touchpoint.** כל פונקציה שמעדכנת עמודת status / lifecycle של ישות (`apply_chip`, `mark_*_sent`, `perform_action`) חייבת לעדכן atomically את **רשימת השדות האחים הקנונית** בטרנזקציה אחת:
   - שדה status
   - `last_outbound_at` (UTC)
   - `last_activity_type` (תואם ל-`ActivityType.<X>.value`)
   - סגירת tasks פתוחים ב-`AUTO_CLOSE_TASK_TYPES`
   - יצירת task חדש עם `assigned_to`, `due_at`, `origin_rule` ייחודי
   - `log_activity(...)`
   - `sync_lead_next_action_cache(...)` אחרי flush

2. **Status עם דרישות cascade.** מעבר ל-`BOOKING_PENDING` / `BOOKED` דורש שורת `Booking` או `ValidationError`. מעברים ל-`WON` / `LOST` / `ARCHIVED` עוברים דרך `close_lead(...)`, לא השמה ישירה.

3. **Activity log מתעד intent, לא רק outcome.** כש-CAS / `UPDATE` מחזיר `rowcount=0`, עדיין לוג activity עם `metadata.applied=false`. אחרת צרכנים downstream (cron, dashboard) חושבים שה-event לא קרה.

4. **הערך של עמודת `last_activity_type` חייב להיות שווה ל-`type` שנכתב ב-activity log.** אי-התאמות (למשל `meeting_rejected` מול `MEETING_CANCELED`) שוברות filters downstream.

5. **Pydantic schema defaults הם חוזים strict.** כש-caller משמיט שדה עם default, ה-default חל בשקט. ודא שה-default תואם לכוונה של המקור (אל תקבע default של `preferred_contact=WHATSAPP` ל-flow של email-intake).

6. **הבדל "missing" מ-"None" בסינון dict.** השתמש ב-`if k in d:` לא `if d.get(k) is not None:` כש-`None` הוא ערך חוקי.

7. **משתמשים מרובי-תפקידים:** state transitions בודקים את ה-*target state*, לא רק את התפקיד. משתמש יכול להיות גם driver וגם secretary; routing של menu חייב לבחור target לפי state מפורש, לא תפקיד.

ראה `BY-STACK/state-machine.md` לדוגמאות קוד.
