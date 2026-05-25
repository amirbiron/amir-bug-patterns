# BY-STACK: State machines

## רלוונטיות — העתק את הקובץ הזה אם בפרויקט יש...
- ✅ Status enums שמובילים lifecycle (`Lead.status`, `Order.status`, `Booking.status`, `Conversation.state`)
- ✅ פעולות "touchpoint": פעולה אחת שחייבת לעדכן atomically כמה שדות מקושרים (status + last_outbound_at + last_activity_type + סגירת task קשור + log-activity)
- ✅ Activity / audit logs שצרכנים downstream (cron / dashboards) תלויים בהם
- ✅ state transitions עם דרישות cascade (status → side effects על שורות קשורות)
- ⏭ דלג אם: CRUD טהור בלי סמנטיקת lifecycle

---

## דפוס 1 — שינוי status שוכח side-effects מקושרים (CORE U5)

**חומרה:** HIGH — שחיתות נתונים שקטה; cron / UI downstream נשברים

### איך זה נראה
```python
def apply_chip(lead, target_status):
  lead.status = target_status  # ❌ מה עוד צריך להתעדכן?
  await session.commit()
```

שינוי status ב-codebase הזה דורש בדרך כלל:
1. `lead.status` = ערך חדש
2. `lead.last_outbound_at` = UTC עכשיו (אם זה touchpoint יוצא)
3. `lead.last_activity_type` = `ActivityType.<X>.value` תואם
4. סגירת tasks פתוחים ב-`AUTO_CLOSE_TASK_TYPES`
5. יצירת task חדש עם `assigned_to = lead.owner_id`, `due_at` ב-UTC, `origin_rule` ייחודי
6. שורת `log_activity(...)`
7. `sync_lead_next_action_cache(...)` אחרי flush

### כלל לזיהוי
שמור **רשימת אחים קנונית** ברמת הפרויקט לכל status / לכל סוג touchpoint. לכל פונקציה שמעדכנת עמודת status / lifecycle, ודא שגם רשימת האחים נוגעת באותה טרנזקציה.

שמות דפוס שיש לדווח עליהם: `apply_chip`, `mark_*_sent`, `perform_action`, כל דבר שיוצר activities סופיות כמו `TEMPLATE_MARKED_SENT` / `PROPOSAL_SENT` / דומה.

### Commits אמיתיים
- Noa `bd2b105` — chip קבע `PROPOSAL_SENT` ועקף את `ProposalSentConfirmModal`.
- Noa `75b430a` — chip קבע `PROPOSAL_SENT` בלי `proposal_sent_at` → `check_stuck_proposals` נשבר.
- Noa `df530f3` — `apply_chip` שכח `last_outbound_at` + `last_activity_type`.
- Noa `4cc5a09` — `apply_chip` לא סגר tasks ישנים ב-`AUTO_CLOSE_TASK_TYPES`.
- Noa `3312957` — task שנוצר מ-chip חסר `assigned_to` → לא נראה ב-views של owner-scoped.
- Noa `c99a47a` — `LECTURE_INQUIRY` חסר מהרשימה הקנונית `AUTO_CLOSE`.

### False positives
- migrations / scripts של backfill.
- views read-only.
- עדכוני שדה יחיד שבאמת עצמאיים (למשל `last_viewed_at`).

### מצב מומלץ
**strict** לפונקציות touchpoint ידועות; **warning** במקומות אחרים.

---

## דפוס 2 — Transition שדורש יצירה/מחיקה של שורה cascading

`Lead.status = BOOKING_PENDING` או `BOOKED` אמור להיות מקושר 1:1 עם שורת `Booking`. הצבת ה-status בלי ליצור/לנהל את שורת ה-booking משאירה את המערכת ב-state בלתי אפשרי.

### כלל לזיהוי
לכל יעד status ב-`{BOOKING_PENDING, BOOKED}`: שורת `Booking` חייבת להתקיים או `ValidationError` חייב להיזרק.

ל-`{WON, LOST, ARCHIVED}`: חייב לעבור דרך `close_lead(...)`, לא השמה ישירה.

ל-`{BOOKING_PENDING, BOOKED}` → status אחר: `Booking` פעיל קיים חייב לעשות cascade (`REJECT` / `CANCEL`) או שצריך להודיע למשתמש.

### Commits אמיתיים
- Noa `3312957` — chip קבע `BOOKING_PENDING`/`BOOKED` בלי שורת `Booking` → תקוע.
- Noa `75b384a` — `apply_chip` לא חסם `BOOKED` + booking מאושר → orphan Calendar event.

---

## דפוס 3 — Activity log כמקור אמת (Noa P9)

**מקור:** ייחודי ל-Noa, אבל העקרון מכליל (EmailFlow P1 audit-log-lifecycle זה אותו רעיון).

כש-UPDATE יכול להיכשל (דחיית CAS, race, דחיית filter), ה-activity log עדיין חייב לתעד את ה-*intent* עם `metadata.applied=false`. אחרת צרכנים downstream (cron, dashboard, מיון) חושבים שה-event מעולם לא קרה.

```python
result = await session.execute(update(Lead).where(...).values(...))
if result.rowcount == 0:
  await log_activity(type="rescheduled", metadata={"applied": False, "reason": "race"})
else:
  await log_activity(type="rescheduled", metadata={"applied": True})
```

גם: `last_activity_type` על הישות חייב להתאים ל-`type` שנכתב ב-activity log (שוויון מחרוזת אחרי `.value`). אם activity log כותב `MEETING_CANCELED` אבל העמודה קוראת `meeting_rejected`, filters downstream נשברים.

### Commits אמיתיים
- Noa `04cb101` — `_apply_reschedule` rowcount=0 → cron יצר task מוקדם.
- Noa `0aff4a1` — webhook עם changes ריקים, sync_token לא נשמר → לולאה אינסופית.
- Noa `0aff4a1` (וריאציה) — `last_activity_type` לא תאם ל-`type` של activity log.

---

## דפוס 4 — Pydantic schema default דורס את הכוונה של ה-caller (Noa P4)

**מקור:** ייחודי ל-Noa (Pydantic-heavy). סיגנל חד-מקורי — החל אם הפרויקט שלך משתמש ב-Pydantic בגבולות API.

```python
class LeadCreate(BaseModel):
  preferred_contact: ContactChannel = ContactChannel.WHATSAPP  # default ❌
  ...

# Flow של email intake:
lead = await create_lead(LeadCreate(full_name=..., phone=...))  # ה-caller השמיט preferred_contact
# → ה-lead מקבל WHATSAPP default, למרות שהמקור היה email
```

### כלל לזיהוי
לכל Pydantic `BaseModel` עם default:
1. מצא את כל ה-callers שיוצרים instances **בלי** השדה.
2. לכל caller, ודא שה-default תואם לכוונה של המקור (default של WhatsApp UI ≠ default של email-intake).
3. לשדות enum nullable ב-DB אבל non-nullable ב-Pydantic: דווח על אי-התאמת schema.
4. ל-enum ממקור חיצוני (AI, webhook): שקול אם דחיית ערכים לא מוכרים = אובדן נתונים. לפעמים `str | None` + ולידציה idempotent ב-caller עדיף מ-enum strict.
5. Walrus + truthy על env: השתמש ב-`is not None` מפורש ו-`.strip()` כדי להבחין `""` מ-`None`.

### Commits אמיתיים
- Noa `3203410` — `LeadCreate.preferred_contact` default WHATSAPP הוחל על lead שמקורו email.
- Noa `7001892` — `LeadDraft.service_category` `StrEnum` דחה ערך לא מוכר → אובדן full_name + phone.
- Noa `f6293e3` — `LeadDraft.full_name` נדרש; AI החזיר `null` → manual review מיותר.
- Noa `dc24922` — `TodayActionItem.service_category` נדרש אבל Lead nullable → ולידציה נכשלת ב-`/dashboard`.
- Noa `236b072` — walrus `if override := env.get(...)` התייחס ל-`""` כ-falsy.

---

## דפוס 5 — לולאות routing של state-machine

כשמשתמשים יש תפקידים מרובים או כש-"back" navigation לא קשור ל-state מפורש, לולאות אינסופיות מתפתחות.

### Commits אמיתיים
- Shipment-bot `ea648a0` — "back to driver menu" של driver-secretary זיהה תפקיד secretary → חזר ל-secretary menu → לולאה אינסופית.
- Shipment-bot `9bd99c1` — בדיקת state ישן סיננה `user.role != SENDER` → admins עם state `SENDER.*` נכנסו ללולאת reset.
- Shipment-bot `9bd99c1` (וריאציה) — dict comprehension סיננה ערכי `None` (`if admin_ctx.get(k) is not None`) → `original_approval_status=None` לגיטימי נמחק, שובר backtrack.

### כלל לזיהוי
לכל handler של menu / state-transition שמסתעף לפי תפקיד משתמש:
1. בדוק את ה-*target state*, לא רק את התפקיד (משתמש יכול להיות ב-`SENDER.SHIPPING_FORM` תוך כדי שהוא גם admin).
2. הבדל "missing" מ-"None" — השתמש ב-`k in d:` מפורש, לא `is not None`, כש-None הוא ערך תקף.

---

## דפוס 6 — עדכון state חלקי על ישות multi-field

נגיעה בשדה אחד של אובייקט state שלוגית atomic.

### Commits אמיתיים
- Web `2e5c480` — רק `token` עודכן ב-localStorage; `refreshToken` נשאר ישן.
- routine `01c61ac` — `handleMorningTimeChange` שלח רק `hour`, לא את ה-`enabled` flag → בקשות concurrent דרסו זו את זו.
- routine `259c2a3` (token balance) — query גלובלי במקום per-child → כל הילדים שיתפו balance אחד.

### כלל
Token pairs, תפקיד + הרשאות, status + last_*_at, וכו', חייבים להתעדכן יחד. השתמש ב-JSON blob יחיד ב-localStorage, body יחיד של API request, או עטוף עדכוני multi-field בטרנזקציה.

---

## הפניות צולבות

- **CORE U5** — partial atomic updates (הקובץ הזה הוא ה-deep-dive)
- **CORE U1** — race conditions משפיעים גם על state machines (CAS על עמודת status)
- **BY-STACK/async-orm.md** — תבנית CAS + דפוס audit-log-on-failure
- **`bugbot-rules/linked-field-atomicity.md`**
