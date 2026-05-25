# filter-too-narrow

Detect filter expressions (`WHERE`, regex, `Array.filter`) that exclude legitimate cases or are applied in the wrong order — producing empty UI lists, blocked emails, or security-bypass via override.

## Flag when ANY apply

1. **Filter on a single channel/source/type** where the entity is documented to have multiple variants. Example: `WHERE channel = 'whatsapp'` in a UI list that should also show email-pref entities.

2. **Domain blacklist using exact match** (`host == "mailchimp.com"`) instead of suffix match (`host.endswith(".mailchimp.com") or host == "mailchimp.com"`).

3. **Regex over email / URL / phone** without handling display-name (`"Alice <alice@example.com>"`), subdomain, or international format variants.

4. **Filter order: business override before security/deny check.** Example:
   ```python
   if message.contains(FORCE_SEND_KEYWORD):
     send(lead, message); return
   if blocked_publishers.contains(lead.publisher_id):
     return  # never reached for force_send
   ```
   Security / deny / block filters must run FIRST.

5. **`Array.filter` followed by `.length === 0` UI** where the filter's predicate doesn't cover all expected entity variants → user sees empty list incorrectly.

## False positives

- Intentional scope reduction (owner-scoped, role-scoped, tenant-scoped) where the filter IS the feature.
- Debug-only / admin-only filters where the narrow scope is intentional.
- Test fixtures.

## Severity

MEDIUM — empty UI / blocked operations (UX-breaking); HIGH if filter order causes a security bypass.
