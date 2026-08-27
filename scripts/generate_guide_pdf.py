#!/usr/bin/env python3
"""Generate a beginner-friendly PDF guide for the Events Platform."""
from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parent / "Events_Platform_Guide.pdf"


class GuidePDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "Events Platform - Student Guide", align="L")
        self.cell(0, 8, f"Page {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, "events-platform  |  Django + DRF + PostgreSQL + SimpleJWT", align="C")

    def h1(self, text):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(20, 40, 80)
        self.multi_cell(0, 10, text)
        self.ln(2)

    def h2(self, text):
        self.ln(3)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(30, 70, 120)
        self.multi_cell(0, 8, text)
        self.ln(1)

    def h3(self, text):
        self.ln(2)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 7, text)
        self.ln(1)

    def body(self, text):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def bullet(self, text):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.5, f"- {text}")

    def code(self, text):
        self.set_x(self.l_margin)
        self.set_fill_color(245, 245, 248)
        self.set_font("Courier", "", 8.5)
        self.set_text_color(20, 20, 20)
        self.multi_cell(0, 4.8, text, fill=True)
        self.ln(2)

    def note(self, text):
        self.set_x(self.l_margin)
        self.set_fill_color(255, 248, 230)
        self.set_font("Helvetica", "I", 9.5)
        self.set_text_color(90, 60, 0)
        self.multi_cell(0, 5.5, f"Note: {text}", fill=True)
        self.ln(2)

    def ok(self, text):
        self.set_x(self.l_margin)
        self.set_fill_color(230, 245, 235)
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(20, 80, 40)
        self.multi_cell(0, 5.5, f"[OK] {text}", fill=True)
        self.ln(2)


def build():
    pdf = GuidePDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 18, 18)
    pdf.add_page()

    # Cover
    pdf.ln(25)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(20, 40, 80)
    pdf.cell(0, 12, "Events Platform API", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 8, "Beginner Guide: How to Run & How It Works", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(
        0,
        6,
        "A simple walkthrough so you can start the server, try the APIs, "
        "understand auth/OTP/events/enrollment, and finish your assignment work.",
        align="C",
    )
    pdf.ln(10)
    pdf.ok("Project folder: ~/events-platform")
    pdf.ok("Stack: Django + DRF + PostgreSQL + SimpleJWT")
    pdf.ok("Docs UI: http://127.0.0.1:8000/api/docs/")

    # 1
    pdf.add_page()
    pdf.h1("1. What is this project?")
    pdf.body(
        "This is a backend API for an Events Platform. There is no fancy website homepage - "
        "clients talk to JSON endpoints. Facilitators create events; Seekers search, enroll, "
        "cancel, and re-enroll. Users sign up with email, verify a 6-digit OTP, then get JWT tokens."
    )
    pdf.h3("Two roles")
    pdf.bullet("Facilitator - create / update / delete own events; see enrollment_count and available_seats")
    pdf.bullet("Seeker - search events; enroll / cancel; list upcoming or past enrollments")
    pdf.h3("Important folders")
    pdf.bullet("accounts/ - signup, login, OTP, Profile (role linked 1-to-1 with Django User)")
    pdf.bullet("events/ - Event + Enrollment models, search, enroll with DB locking")
    pdf.bullet("config/ - Django settings, URLs, standardized error format")
    pdf.bullet("chaos/ - scripts that deliberately break things (for DEBUGGING.md evidence)")
    pdf.bullet("docs/ - API proof instructions (screenshots / recordings)")

    # 2
    pdf.h1("2. Do I need to change .env?")
    pdf.body(
        "For the default local setup with Docker Postgres on port 5433: NO. "
        "Your .env is already correct."
    )
    pdf.h3("Current expected values")
    pdf.code(
        "DJANGO_DEBUG=True\n"
        "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver\n"
        "POSTGRES_HOST=127.0.0.1\n"
        "POSTGRES_PORT=5433\n"
        "POSTGRES_USER=events\n"
        "POSTGRES_PASSWORD=events\n"
        "POSTGRES_DB=events_platform\n"
        "EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend"
    )
    pdf.note(
        "OTP emails are printed in the terminal (console backend). "
        "You do not need Gmail/SMTP for this assignment."
    )
    pdf.body(
        "Change .env only if you use a different Postgres host/port/password, "
        "or when deploying to production (strong SECRET_KEY, DEBUG=False)."
    )

    # 3
    pdf.h1("3. How to run (step by step)")
    pdf.h3("Step A - Start PostgreSQL")
    pdf.code(
        "docker start events-pg\n"
        "# If the container does not exist yet:\n"
        "docker run -d --name events-pg \\\n"
        "  -e POSTGRES_USER=events -e POSTGRES_PASSWORD=events \\\n"
        "  -e POSTGRES_DB=events_platform -p 5433:5432 postgres:16-alpine"
    )
    pdf.h3("Step B - Activate venv and start server")
    pdf.code(
        "cd ~/events-platform\n"
        "source .venv/bin/activate\n"
        "python manage.py migrate\n"
        "python manage.py seed_demo\n"
        "python manage.py runserver"
    )
    pdf.h3("Step C - Open these URLs")
    pdf.bullet("http://127.0.0.1:8000/          -> redirects to Swagger docs")
    pdf.bullet("http://127.0.0.1:8000/api/docs/ -> interactive API explorer")
    pdf.bullet("http://127.0.0.1:8000/admin/    -> Django admin")
    pdf.note(
        "A 404 on http://127.0.0.1:8000/ before the redirect fix was normal - "
        "this is an API project, not a website. Use /api/docs/."
    )

    pdf.h3("Demo accounts (already verified by seed_demo)")
    pdf.code(
        "Facilitator:  facilitator@example.com / Passw0rd!\n"
        "Seeker:       seeker1@example.com     / Passw0rd!\n"
        "              seeker2@example.com ... seeker5@example.com"
    )

    # 4
    pdf.add_page()
    pdf.h1("4. How everything works (big picture)")
    pdf.body(
        "Request flow: Client (Swagger / Postman) -> Django URLs -> Views/Serializers "
        "-> Services (OTP / enrollment locking) -> PostgreSQL"
    )
    pdf.h3("Standard responses")
    pdf.bullet("Pagination shape: { count, next, previous, results }")
    pdf.bullet('Errors: { "detail": "message", "code": "error_code_string" }')
    pdf.bullet("Auth header: Authorization: Bearer <access_token>")

    pdf.h2("4.1 Authentication & OTP")
    pdf.body("Signup does NOT accept username in the body - only email, password, role.")
    pdf.bullet("POST /api/auth/signup/ - creates unverified user + Profile; emails OTP")
    pdf.bullet("OTP stored as SHA-256 hash only (never returned in API JSON)")
    pdf.bullet("POST /api/auth/verify-otp/ - marks email verified")
    pdf.bullet("POST /api/auth/resend-otp/ - revokes old OTP; 60s cooldown; 5 min TTL; max 3 fails")
    pdf.bullet("POST /api/auth/login/ - verified email + password -> access + refresh JWTs")
    pdf.bullet("POST /api/auth/token/refresh/ - new access token")
    pdf.body(
        "Unverified users cannot log in (code: email_not_verified). "
        "Requesting OTP #2 immediately invalidates OTP #1."
    )

    pdf.h2("4.2 Events & search")
    pdf.bullet("Facilitator CRUD: /api/facilitator/events/")
    pdf.bullet("List includes enrollment_count and available_seats (null capacity = unlimited)")
    pdf.bullet("Search: GET /api/events/?q=&location=&language=&starts_after=&starts_before=")
    pdf.bullet("Default order: starts_at ascending (upcoming first)")

    pdf.h2("4.3 Enrollment (the hard parts)")
    pdf.h3("Concurrency (Challenge A)")
    pdf.body(
        "When many seekers enroll at once, the service locks the Event row with "
        "select_for_update() inside transaction.atomic(), then recounts ENROLLED seats. "
        "Active enrollments can never exceed capacity."
    )
    pdf.h3("Cancel & re-enroll (Challenge B)")
    pdf.body(
        "Cancel sets status=CANCELLED (row kept as audit). Re-enroll inserts a NEW ENROLLED row. "
        "A partial unique constraint allows only one ENROLLED row per (event, seeker), "
        "while many CANCELLED rows are allowed."
    )

    # 5
    pdf.add_page()
    pdf.h1("5. What you should do for your work")
    pdf.h3("Checklist")
    pdf.bullet("1. Start Postgres + runserver (Section 3)")
    pdf.bullet("2. Open Swagger; login as facilitator and seeker")
    pdf.bullet("3. Create/list events; enroll; cancel; re-enroll")
    pdf.bullet("4. Trigger capacity_full error (capacity=1 event, two seekers)")
    pdf.bullet("5. Run automated tests (below)")
    pdf.bullet("6. Optional: run chaos scripts and keep logs for DEBUGGING.md")
    pdf.bullet("7. Optional: Postman screenshots + asciinema/vhs (see docs/API_PROOF.md)")

    pdf.h3("Try in Swagger")
    pdf.body(
        "1) Call POST /api/auth/login/ with seeker1 credentials.\n"
        "2) Copy the access token.\n"
        "3) Click Authorize -> paste: Bearer <access>\n"
        "4) Call GET /api/events/ and POST /api/events/{id}/enroll/"
    )

    pdf.h3("Run tests")
    pdf.code("python manage.py test accounts.tests events.tests -v 2\n# Expect: Ran 17 tests ... OK")

    pdf.h3("Chaos experiments (optional but great for understanding)")
    pdf.code(
        "python chaos/chaos_a_concurrency.py\n"
        "# Shows overbooking when locking is removed\n\n"
        "python chaos/chaos_b_unique_together.py\n"
        "# Shows IntegrityError on re-enroll with naive unique_together"
    )
    pdf.body("Read DEBUGGING.md and DECISIONS.md - they explain the real failures and design choices.")

    # 6
    pdf.h1("6. Postman")
    pdf.bullet("Import events_platform.postman_collection.json")
    pdf.bullet("Set baseUrl = http://127.0.0.1:8000")
    pdf.bullet("Login requests auto-save accessToken into collection variables")
    pdf.bullet("Other requests use Authorization: Bearer {{accessToken}}")

    # 7
    pdf.h1("7. Key API map (short)")
    pdf.code(
        "POST /api/auth/signup/\n"
        "POST /api/auth/verify-otp/\n"
        "POST /api/auth/resend-otp/\n"
        "POST /api/auth/login/\n"
        "POST /api/auth/token/refresh/\n"
        "GET  /api/auth/me/\n"
        "GET/POST /api/facilitator/events/\n"
        "GET/PATCH/DELETE /api/facilitator/events/{id}/\n"
        "GET  /api/events/   (search)\n"
        "POST /api/events/{id}/enroll/\n"
        "POST /api/events/{id}/cancel/\n"
        "GET  /api/enrollments/me/?scope=upcoming|past|all"
    )

    # 8
    pdf.h1("8. Common problems")
    pdf.h3("Page not found on /")
    pdf.body("Use /api/docs/. Root now redirects there if you pulled the latest urls.py.")
    pdf.h3("Could not connect to database")
    pdf.body("Start Docker Postgres: docker start events-pg. Confirm PORT=5433 in .env.")
    pdf.h3("Login says email_not_verified")
    pdf.body(
        "New signups must verify OTP from the runserver console. "
        "Seeded demo users are already verified."
    )
    pdf.h3("capacity_full")
    pdf.body("Expected when the event is full - not a crash. Error code proves validation works.")

    # 9
    pdf.h1("9. Docs to read (in this order)")
    pdf.bullet("README.md - setup & route map")
    pdf.bullet("This PDF - your day-to-day guide")
    pdf.bullet("DECISIONS.md - why locking / partial unique / OTP policy")
    pdf.bullet("DEBUGGING.md - real chaos failure traces")
    pdf.bullet("PROMPT_LOG.md - AI interaction log + corrections")
    pdf.bullet("docs/API_PROOF.md - screenshot / recording instructions")

    pdf.ln(8)
    pdf.ok("You are ready: start runserver -> open /api/docs/ -> login -> explore -> run tests.")

    pdf.output(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
