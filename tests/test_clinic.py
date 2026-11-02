import math
import unittest

from clinicqueue import core, create_app
from clinicqueue.core import Ticket, day_plan, effective_level, erlang_c, mean_wait, order, predict_wait, simulate, staff_needed


class TestPriority(unittest.TestCase):
    def test_emergency_goes_first(self):
        q = order([Ticket(1, 3, 0), Ticket(2, 1, 50)], 50)
        self.assertEqual(q[0].number, 2)

    def test_same_level_is_first_come_first_served(self):
        self.assertEqual([t.number for t in order([Ticket(2, 3, 5), Ticket(1, 3, 1)], 6)], [1, 2])

    def test_a_long_wait_lifts_a_standard_patient_above_a_new_urgent_one(self):
        q = order([Ticket(1, 3, 0), Ticket(2, 2, 60)], 60)
        self.assertEqual(q[0].number, 1)

    def test_ageing_never_passes_an_emergency(self):
        self.assertGreater(effective_level(Ticket(1, 3, 0), 10 ** 6), 1)
        self.assertEqual(order([Ticket(1, 3, 0), Ticket(2, 1, 9999)], 9999)[0].number, 2)

    def test_prediction(self):
        self.assertEqual(predict_wait(3, [10, 10, 100]), 30)
        self.assertEqual(predict_wait(4, [10], 2), 20)
        self.assertIsNone(predict_wait(3, []))


class TestTheory(unittest.TestCase):
    def test_one_server_matches_the_simple_formula(self):
        lam, mu = 3.0, 5.0
        self.assertAlmostEqual(erlang_c(lam, mu, 1), lam / mu)
        self.assertAlmostEqual(mean_wait(lam, mu, 1), lam / (mu * (mu - lam)))

    def test_published_value(self):
        # a = 8 erlangs on 10 servers gives a wait probability of about 0.409
        self.assertAlmostEqual(erlang_c(8, 1, 10), 0.4092, places=3)

    def test_overload(self):
        self.assertEqual(erlang_c(10, 1, 5), 1)
        self.assertEqual(mean_wait(10, 1, 5), math.inf)

    def test_staff_needed(self):
        self.assertEqual(staff_needed(4, 1, 1), 5)
        self.assertGreaterEqual(staff_needed(4, 1, 0.1), 6)

    def test_more_staff_never_makes_waits_longer(self):
        waits = [mean_wait(8, 1, c) for c in range(9, 20)]
        self.assertEqual(waits, sorted(waits, reverse=True))

    def test_day_plan(self):
        plan = day_plan([(9, 20), (13, 5)], 6, 10)
        self.assertGreater(plan[0][1], plan[1][1])


class TestSimulation(unittest.TestCase):
    def test_simulation_agrees_with_erlang_c(self):
        for lam, mu, c in ((3.0, 5.0, 1), (4.0, 1.5, 3), (8.0, 1.0, 10)):
            s = simulate(lam, mu, c, 60000, 1)
            self.assertAlmostEqual(s["mean"], mean_wait(lam, mu, c), delta=max(0.12 * mean_wait(lam, mu, c), 0.02))

    def test_priorities_shorten_urgent_waits(self):
        s = simulate(4.0, 1.5, 3, 30000, 2, {1: 0.1, 2: 0.2, 3: 0.7})
        b = s["by_level"]
        self.assertLess(b[1], b[2])
        self.assertLess(b[2], b[3])

    def test_same_seed_same_result(self):
        self.assertEqual(simulate(3, 5, 1, 1000, 3), simulate(3, 5, 1, 1000, 3))


class Clock:
    def __init__(self):
        self.t = 1_800_000_000.0

    def __call__(self):
        return self.t


class TestApp(unittest.TestCase):
    def setUp(self):
        self.c = Clock()
        self.a = create_app(":memory:", self.c)

    def text(self, url="/"):
        return self.a.get(url).body.decode()

    def test_token_call_finish(self):
        self.a.post("/token", level=3, label="Dressing")
        self.a.post("/token", level=1)
        self.a.post("/call", room="Room 2")
        self.assertEqual(self.a.one("SELECT number FROM tickets WHERE called IS NOT NULL"), 2)
        self.assertIn("Go to Room 2", self.text("/display"))
        self.c.t += 600
        self.assertEqual(self.a.post("/finish/2").status, 303)
        self.assertEqual(self.a.post("/finish/2").status, 409)
        self.assertIn("10 min", self.text("/"))

    def test_nobody_waiting(self):
        self.assertEqual(self.a.post("/call", room="1").status, 400)

    def test_numbers_restart_each_day(self):
        self.a.post("/token", level=3)
        self.c.t += 86400
        self.a.post("/token", level=3)
        self.assertEqual([r["number"] for r in self.a.rows("SELECT number FROM tickets")], [1, 1])

    def test_planning(self):
        page = self.a.post("/plan", arrivals=12, minutes=8, target=15).body.decode()
        self.assertIn("You need at least 2 staff", page)
        self.assertIn("grows without limit", self.a.post("/plan", arrivals=30, minutes=8, target=15).body.decode())

    def test_bad_inputs(self):
        self.assertEqual(self.a.post("/token", level=9).status, 400)


if __name__ == "__main__":
    unittest.main()
