# API Proof — Screenshots & Terminal Recordings

Use this checklist to generate visual evidence for evaluators.

---

## A. Postman screenshot proofs

1. Import `events_platform.postman_collection.json` into Postman.
2. Set collection variable `baseUrl` = `http://127.0.0.1:8000`.
3. Start the server (`python manage.py runserver`) with console email backend.

### Shot 1 — Auth flow (Signup → Console OTP → Verify → Login)

1. **Signup (Seeker)** → capture `201` body (must **not** contain an OTP code).
2. In the Django runserver terminal, capture the console email line containing the
   6-digit code (this is the only allowed plaintext surface).
3. **Verify OTP** with that code → `200`.
4. **Login** → `200` with `access` + `refresh`. Login test script stores
   `{{accessToken}}` automatically.
5. Optional: attempt login **before** verify → expect
   `{"detail":"...","code":"email_not_verified"}`.

### Shot 2 — Facilitator dashboard (`available_seats`)

1. **Login (Facilitator)** (`facilitator@example.com` / `Passw0rd!` after seed).
2. **List My Events** → screenshot JSON showing `enrollment_count` and
   `available_seats` per event.
3. As a seeker, enroll once; refresh facilitator list — `available_seats` must drop by 1.

### Shot 3 — Standardized capacity error

1. Use seeded event **“PostgreSQL Concurrency Deep Dive”** (`capacity=1`) or create
   one with `capacity: 1`.
2. Enroll seeker1 successfully.
3. Login as seeker2 and **Enroll** again → capture `400`:

```json
{"detail": "Event capacity full.", "code": "capacity_full"}
```

### Shot 4 — Cancel → Re-enroll

1. Seeker enrolls → `201` `ENROLLED`.
2. **Cancel Enrollment** → `200` `CANCELLED`.
3. **Re-enroll** → `201` new enrollment id (not an IntegrityError).

---

## B. CLI test recording (asciinema)

```bash
cd events-platform
source .venv/bin/activate
mkdir -p docs/proof

# Record
asciinema rec docs/proof/test_suite.cast \
  -c "python manage.py test accounts.tests events.tests -v 2"

# Optional upload / GIF conversion
# asciinema upload docs/proof/test_suite.cast
# agg docs/proof/test_suite.cast docs/proof/test_suite.gif
```

Capture a second cast for chaos:

```bash
asciinema rec docs/proof/chaos.cast -c "bash chaos/run_all.sh"
```

---

## C. VHS tape (GIF)

Install [vhs](https://github.com/charmbracelet/vhs), then:

```bash
vhs docs/proof/tests.tape
```

`docs/proof/tests.tape` contents:

```tape
Output docs/proof/tests.gif
Set Shell bash
Set FontSize 14
Set Width 1200
Set Height 800
Type "source .venv/bin/activate && python manage.py test accounts.tests events.tests -v 2"
Enter
Sleep 45s
```

---

## D. OpenAPI schema snapshot

```bash
python manage.py spectacular --file docs/openapi.yaml
# or open http://127.0.0.1:8000/api/docs/ and screenshot Swagger UI
```

---

## Evidence folder layout (recommended)

```text
docs/proof/
  auth_signup.png
  auth_console_otp.png
  auth_verify_login.png
  facilitator_seats.png
  capacity_full_400.png
  reenroll_success.png
  test_suite.cast
  tests.gif
  chaos.cast
```
