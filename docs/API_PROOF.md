# API Proof — Screenshots & Terminal Recordings

Visual evidence for evaluators. All committed screenshots use the numbered naming
scheme in `docs/proof/`.

---

## Proof gallery (committed)

### 01 — Auth flow (Signup → Verify OTP → Login)

Seeker signup returns `201` with **no OTP** in the body, verify returns `200`,
login returns JWT `access` + `refresh`.

![01 — Auth flow](proof/01-auth-flow.png)

### 02 — Facilitator event + seat dashboard

Facilitator creates an event (`201`) then lists events showing
`enrollment_count` and `available_seats` after seeker enrollments.

![02 — Facilitator event + available_seats](proof/02-facilitator-event.png)

### 03 — Event search & filtering

Search by `q`, `location`, and `language` returns the matching Kubernetes workshop.

![03 — Event search filtering](proof/03-event-search.png)

### 04 — Enrollment capacity enforcement

Create `capacity=1` event, then second seeker receives standardized `400`:

```json
{"detail": "Event capacity full.", "code": "capacity_full"}
```

![04 — Enrollment capacity](proof/04-enrollment-capacity.png)

### 05 — Cancel → Re-enroll lifecycle

Enroll (`201` `ENROLLED`) → Cancel (`200` `CANCELLED`) → Re-enroll (`201` new id).

![05 — Re-enrollment lifecycle](proof/05-reenrollment.png)

### 06 — Test suite

```bash
python manage.py test accounts.tests events.tests -v 2
```

![06 — 31 tests OK](proof/06-test-suite.png)

---

## How to reproduce (Postman)

1. Import `events_platform.postman_collection.json` into Postman.
2. Set collection variable `baseUrl` = `http://127.0.0.1:8000`.
3. Start the server (`python manage.py runserver`) with console email backend.
4. Run requests in collection order; capture screenshots matching `01`–`06` above.

---

## CLI test recording (asciinema)

```bash
cd events-platform
source .venv/bin/activate
mkdir -p docs/proof

asciinema rec docs/proof/test_suite.cast \
  -c "python manage.py test accounts.tests events.tests -v 2"

asciinema rec docs/proof/chaos.cast -c "bash chaos/run_all.sh"
```

---

## VHS tape (GIF)

Install [vhs](https://github.com/charmbracelet/vhs), then:

```bash
vhs docs/proof/tests.tape
```

---

## OpenAPI schema snapshot

```bash
python manage.py spectacular --file docs/openapi.yaml
# or open http://127.0.0.1:8000/api/docs/ and screenshot Swagger UI
```

---

## Evidence folder layout

```text
docs/proof/
  01-auth-flow.png                 # signup → verify → login
  02-facilitator-event.png         # create event + seat dashboard
  03-event-search.png              # search filtering
  04-enrollment-capacity.png       # capacity=1 + capacity_full error
  05-reenrollment.png              # enroll → cancel → re-enroll
  06-test-suite.png                # 31 tests OK
  chaos_a_overbooking.log          # Chaos A overbooking
  chaos_b_unique_together.log      # Chaos B IntegrityError + fix
  partial_unique_syntax_error.log  # invalid ALTER … WHERE
  tests.tape
  test_suite.cast                  # optional asciinema
  tests.gif                        # optional vhs GIF
  chaos.cast                       # optional chaos recording
```

Committed chaos logs and numbered screenshots ship with the repo/ZIP.
