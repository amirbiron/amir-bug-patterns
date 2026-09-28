# load-by-path-without-import-bookkeeping

זהה טעינה של מודול לפי נתיב — `importlib.util.spec_from_file_location` ← `module_from_spec` ← `loader.exec_module` — שחסר בה אחד משני הדברים ש-`import` רגיל עושה. ולפני שכותבים טוען כזה: האם אפשר ייבוא רגיל? ואם לא — טוען משותף אחד, ולא עותק לכל קובץ (R6).

## דווח כשחסר אחד מהבאים

1. **`sys.modules[name] = module` לפני `exec_module`.** בלעדיו, `@dataclass` במודול עם `from __future__ import annotations` נופל ב-`AttributeError` (נמדד), וכך גם כל קוד שמחפש את המודול לפי `__module__` — וזו מחלקה ולא השערה: גם pydantic פותר דרך `sys.modules` את ההפניות של מודל (ראה "ראיות"). המתכון "Importing a source file directly" בתיעוד של `importlib` כולל את השורה הזאת.

2. **הסרה כשההרצה נכשלת.** המתכון בתיעוד **אינו** כולל אותה, ובלעדיה נשאר ב-`sys.modules` מודול חצי-בנוי. הנזק מתחיל רק כשמישהו מייבא את השם הרשום, ואז הוא מקבל את המודול החצי-בנוי בשקט. שתי צורות לניקוי, לפי המקום: מחוץ ל-pytest — `try` / `except BaseException: del sys.modules[name]; raise`; בתוך טסט — `monkeypatch.setitem(sys.modules, name, module)`, שמסיר לבד ב-teardown. הסעיף הזה הוא ממצא ריוויו (SUGG-006) ולא תקלה שקרתה; הסימוכין — `import` רגיל מסיר מודול שנכשל, כמו שההערה בקוד המתוקן אומרת.

## False positives

- רישום עם שחזור או הסרה ב-`finally`, או דרך `monkeypatch` — עומד בכלל גם בלי הצורה המדויקת של `except BaseException` (אחרת `test_config.py` מדוגל).

## חומרה

סעיף 2, לפי השם שנרשם: **LOW** לשם מקומי ייחודי, שהטוען הבא דורס. **HIGH** לשם שמצל על מודול אמיתי (`config`, `tests._telegram_stubs`) — מודול שבור יושב ב-`sys.modules` לשארית הסשן, וכל ייבוא מאוחר מקבל אותו בשקט.

סעיף 1 נכשל בקול, בזמן הטעינה — אבל רק כשהמודול הנטען משתנה ולא כשהטוען נכתב, ובהודעה שמצביעה על המחלקה ולא על הטוען. טוען בלי רישום עובר עד שמישהו מוסיף למודול שהוא טוען `@dataclass`, או כל קוד אחר שמחפש את המודול לפי שמו.

## ראיות

CodeBot:

- **PR #3465** (`507ba0b2`, מיזוג ה-squash; ההצעה ציטטה את `8584d7c` ואת `92de553`, שנשארו בענף ואינם ב-main) — הטוען `_load_oracle` ב-`scripts/compare_md_parser_to_cmark.py` תוקן פעמיים באותו PR, פעם על כל סעיף: הרישום, אחרי שטבלה של `@dataclass(frozen=True)` נכנסה לאורקל והטעינה נפלה ב-`AttributeError: 'NoneType' object has no attribute '__dict__'`; וההסרה, בסקירת הקוד (SUGG-006), עם הטסט `test_a_broken_oracle_is_not_left_half_built_in_sys_modules`.
- **`tests/_save_layer_harness.py`** — רושם לפני ההרצה, כי pydantic פותר את ההפניות של `BotConfig` דרך `sys.modules`; בלי הרישום — `PydanticUserError: BotConfig is not fully defined` (נמדד, לפי ההערה שם). ושם גם הצורה של הניקוי בתוך טסט: `monkeypatch.setitem`.
