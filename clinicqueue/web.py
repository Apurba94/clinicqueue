"""The offline web app. No names are stored: only token numbers."""
import time

from . import core
from .fieldkit import App, Fail, Raw, bar_chart, card, form, h, redirect, stats, table

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY, day TEXT NOT NULL, number INTEGER NOT NULL, level INTEGER NOT NULL, label TEXT NOT NULL DEFAULT '', arrived REAL NOT NULL, called REAL, finished REAL, room TEXT NOT NULL DEFAULT '', UNIQUE (day, number));
"""


def create_app(db="clinic.db", clock=time.time):
    a = App("ClinicQueue", db, SCHEMA, [("Desk", "/"), ("Display", "/display"), ("Planning", "/plan")])

    def now():
        return clock() / 60

    def today():
        return time.strftime("%Y-%m-%d", time.gmtime(clock()))

    def waiting():
        return [core.Ticket(r["number"], r["level"], r["arrived"], r["label"]) for r in a.rows("SELECT * FROM tickets WHERE day = ? AND called IS NULL ORDER BY number", today())]

    def recent():
        return [r["finished"] - r["called"] for r in a.rows("SELECT called, finished FROM tickets WHERE finished IS NOT NULL ORDER BY id DESC LIMIT 20")]

    @a.route("/")
    def home(req):
        t = now()
        q = core.order(waiting(), t)
        rooms = max(1, int(req.number("rooms", 1, 1, 50)))
        rows = [{"t": x, "pos": i + 1, "wait": core.predict_wait(i, recent(), rooms)} for i, x in enumerate(q)]
        body = stats([("Waiting", len(q)), ("Seen today", a.one("SELECT COUNT(*) FROM tickets WHERE day = ? AND called IS NOT NULL", today())), ("Longest wait", f"{max((t - x.arrived for x in q), default=0):.0f} min")])
        body += card("New token", form(a, "/token", [("level", "Priority", "select", [(k, v) for k, v in sorted(core.LEVELS.items(), reverse=True)]), ("label", "Service, such as Dressing or Vaccination")], "Give token"))
        body += card("Call next", form(a, "/call", [("room", "Room")], "Call next patient"))
        body += card("Queue", table(rows, [("Position", "pos"), ("Token", lambda r: r["t"].number), ("Priority", lambda r: core.LEVELS[r["t"].level]), ("Waiting", lambda r: f"{t - r['t'].arrived:.0f} min"), ("Expected", lambda r: "unknown" if r["wait"] is None else f"{r['wait']:.0f} min"), ("Service", lambda r: r["t"].label)], "Nobody is waiting."))
        active = a.rows("SELECT * FROM tickets WHERE day = ? AND called IS NOT NULL AND finished IS NULL ORDER BY called DESC", today())
        body += card("With staff", table(active, [("Token", "number"), ("Room", "room"), ("", lambda r: Raw(f'<form method="post" action="/finish/{r["id"]}" style="display:inline">{a.form_token()}<button>Finished</button></form>'))], "Nobody at the moment."))
        return a.page("Desk", body)

    @a.route("/token", ("POST",))
    def token(req):
        level = int(req.number("level", low=1, high=3))
        n = (a.one("SELECT MAX(number) FROM tickets WHERE day = ?", today()) or 0) + 1
        a.run("INSERT INTO tickets (day, number, level, label, arrived) VALUES (?, ?, ?, ?, ?)", today(), n, level, req.text("label", False, 100), now())
        return redirect("/")

    @a.route("/call", ("POST",))
    def call(req):
        q = core.order(waiting(), now())
        if not q:
            raise Fail("Nobody is waiting")
        a.run("UPDATE tickets SET called = ?, room = ? WHERE day = ? AND number = ?", now(), req.text("room"), today(), q[0].number)
        return redirect("/")

    @a.route("/finish/<id>", ("POST",))
    def finish(req, id):
        cur = a.run("UPDATE tickets SET finished = ? WHERE id = ? AND called IS NOT NULL AND finished IS NULL", now(), id)
        if cur.rowcount == 0:
            raise Fail("That token is not with staff", 409)
        return redirect("/")

    @a.route("/display")
    def display(req):
        rows = a.rows("SELECT number, room FROM tickets WHERE day = ? AND called IS NOT NULL AND finished IS NULL ORDER BY called DESC LIMIT 6", today())
        q = [t.number for t in core.order(waiting(), now())][:8]
        cells = "".join(f'<div class="stat"><b style="font-size:48px">{r["number"]}</b><span>Go to {h(r["room"])}</span></div>' for r in rows)
        body = f'<meta http-equiv="refresh" content="10"><div class="stats">{cells or "<p>Please wait for your number.</p>"}</div>' + card("Next", f"<p style='font-size:28px'>{' · '.join(map(str, q))}</p>")
        return a.page("Now serving", body)

    @a.route("/plan", ("GET", "POST"))
    def plan(req):
        result = ""
        if req.method == "POST":
            per_hour = req.number("arrivals", low=0.1, high=1000)
            minutes = req.number("minutes", low=0.5, high=240)
            target = req.number("target", low=0.5, high=480)
            rate = 60 / minutes
            need = core.staff_needed(per_hour, rate, target / 60)
            if need is None:
                raise Fail("No workable staff number was found")
            rows = [{"c": c, "w": core.mean_wait(per_hour, rate, c) * 60} for c in range(max(1, need - 2), need + 3)]
            result = card(f"You need at least {need} staff", table(rows, [("Staff", "c"), ("Mean wait", lambda r: "the queue grows without limit" if r["w"] == float("inf") else f"{r['w']:.1f} min")]))
        return a.page("Planning", card("How many staff keep waits short?", form(a, "/plan", [("arrivals", "Patients per hour", "number", 12), ("minutes", "Minutes per patient", "number", 8), ("target", "Target mean wait in minutes", "number", 15)], "Calculate")) + result)

    return a
