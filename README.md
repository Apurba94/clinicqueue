# ClinicQueue

An offline token queue for a small clinic, plus a planning tool that answers "how many staff do we need?" with real queueing theory.

```
python -m clinicqueue
```

Then open http://127.0.0.1:8045. Open `/display` on a second screen for the waiting room. It needs Python 3.10 or newer.

## What it does

- **Tokens with three priorities:** emergency, urgent and standard
- **Fairness through ageing:** a standard patient's priority rises as they wait, so nobody waits forever, and nothing ever passes an emergency
- **Expected waits** from the median of recent visits
- **A waiting-room display** that shows who to go where
- **Staff planning:** give patients per hour, minutes per patient and a target wait, and it gives the number of staff

**Priority levels support staff judgement. They are not a medical triage system.** A trained person decides who is an emergency, and anyone who gets worse in the queue must be seen at once.

No names are stored, only token numbers. That is deliberate.

## The planning maths

Waiting grows sharply as staff near their limit. If patients arrive slightly faster than they can be seen, the queue grows all day. The Erlang C formula gives the mean wait for any number of staff, and the tool shows the numbers around the answer.

## How it is tested

The formula reduces to the known single-server result, and it reproduces a published Erlang C value. A separate discrete-event simulator of 60,000 patients must agree with the theory within about 12%, across three clinic sizes. Tests also show that priorities shorten urgent waits, and that ageing cannot pass an emergency.

## Limits

Theory assumes steady arrivals and random visit lengths. Real clinics have morning rushes, so plan hour by hour with `day_plan`. The display refreshes every 10 seconds. It handles one clinic, with no appointments.

## Tests

```
python -m unittest discover -s tests
```

MIT licence.
