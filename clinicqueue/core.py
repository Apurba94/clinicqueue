"""Queue rules and queue science for a clinic.

Priority keeps urgent patients moving, while ageing stops anyone from waiting forever. The theory
part (Erlang C) and a simulator answer a planning question: how many staff keep waits short?
"""
import heapq
import math
import random
from dataclasses import dataclass, field

LEVELS = {1: "Emergency", 2: "Urgent", 3: "Standard"}
AGE_MINUTES = {1: 0, 2: 15, 3: 30}       # minutes of waiting worth one priority step


@dataclass
class Ticket:
    number: int
    level: int
    arrived: float
    label: str = ""


def effective_level(t, now):
    """A patient's level rises as they wait, so a long queue cannot starve the lowest level."""
    per = AGE_MINUTES[t.level]
    if per == 0:
        return float(t.level)
    return max(1.5, t.level - (now - t.arrived) / per)


def order(tickets, now):
    """Who is next: an emergency always first, then by aged level, then by arrival."""
    return sorted(tickets, key=lambda t: (effective_level(t, now), t.arrived, t.number))


def predict_wait(position, recent_service, staff=1):
    """Estimated minutes until seen. Uses the median of recent visits, as a few long ones distort a mean."""
    if not recent_service:
        return None
    s = sorted(recent_service)
    typical = s[len(s) // 2]
    return position * typical / max(staff, 1)


def erlang_c(arrival_rate, service_rate, servers):
    """Probability that an arrival must wait in an M/M/c queue."""
    a = arrival_rate / service_rate
    rho = a / servers
    if rho >= 1:
        return 1.0
    total = 0.0
    term = 1.0
    for k in range(servers):
        total += term
        term *= a / (k + 1)
    last = term / (1 - rho)
    return last / (total + last)


def mean_wait(arrival_rate, service_rate, servers):
    """Mean wait in the queue, in the same unit as the rates. Infinite if staff cannot keep up."""
    if arrival_rate >= service_rate * servers:
        return math.inf
    return erlang_c(arrival_rate, service_rate, servers) / (servers * service_rate - arrival_rate)


def staff_needed(arrival_rate, service_rate, target_wait, maximum=200):
    """The fewest staff that keep the mean wait under a target."""
    for c in range(1, maximum + 1):
        if mean_wait(arrival_rate, service_rate, c) <= target_wait:
            return c
    return None


def simulate(arrival_rate, service_rate, servers, patients=20000, seed=0, priorities=None):
    """Discrete-event simulation of a clinic queue. priorities: shares of level 1, 2 and 3.
    Returns mean wait overall and by level, and the 90th percentile."""
    rng = random.Random(seed)
    shares = priorities or {3: 1.0}
    levels, weights = zip(*shares.items())
    t = 0.0
    free_at = [0.0] * servers
    heapq.heapify(free_at)
    arrivals = []
    for i in range(patients):
        t += rng.expovariate(arrival_rate)
        arrivals.append((t, i, rng.choices(levels, weights)[0]))
    waiting = []
    waits = {lv: [] for lv in levels}
    i = 0
    n = len(arrivals)
    while i < n or waiting:
        clock = free_at[0]
        while i < n and (arrivals[i][0] <= clock or not waiting):
            at, num, lv = arrivals[i]
            heapq.heappush(waiting, (lv, at, num))
            i += 1
            if len(waiting) == 1 and at > clock:
                clock = at
        lv, at, num = heapq.heappop(waiting)
        start = max(heapq.heappop(free_at), at)
        waits[lv].append(start - at)
        heapq.heappush(free_at, start + rng.expovariate(service_rate))
    every = sorted(w for v in waits.values() for w in v)
    return {"mean": sum(every) / len(every), "p90": every[int(len(every) * 0.9)], "by_level": {k: sum(v) / len(v) for k, v in waits.items() if v}}


def day_plan(hourly_arrivals, service_minutes, target_wait):
    """Staff needed each hour, for planning a roster against the usual busy times."""
    rate = 60 / service_minutes
    return [(h, staff_needed(n, rate, target_wait / 60)) for h, n in hourly_arrivals]
