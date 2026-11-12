"""Calculation and validation routines for the healthcare project manager.
All time spans use calendar days, with finish timestamps as exclusive endpoints.
"""
from datetime import date, timedelta


def parse_date(value):
    return date.fromisoformat(str(value))


def require_text(value, field):
    value = str(value or '').strip()
    if not value:
        raise ValueError(f'{field} is required.')
    if len(value) > 2000:
        raise ValueError(f'{field} is too long.')
    return value


def bounded_int(value, field, lo, hi):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f'{field} must be a whole number.')
    if not lo <= number <= hi:
        raise ValueError(f'{field} must be between {lo} and {hi}.')
    return number


def nonnegative_money(value, field):
    try:
        x = round(float(value), 2)
    except (TypeError, ValueError):
        raise ValueError(f'{field} must be numeric.')
    if not 0 <= x <= 1_000_000_000_000:
        raise ValueError(f'{field} must be between 0 and 1 trillion.')
    return x


def schedule(tasks, kickoff, include_delays=False):
    """Topological earliest-start finish-to-start schedule with task offsets.

    Returns rows in topological order. Detects missing dependencies and cycles.
    """
    kickoff = parse_date(kickoff)
    by_id = {int(t['id']): dict(t) for t in tasks}
    seen, visiting, ordered = set(), set(), []

    def visit(task_id):
        if task_id not in by_id:
            raise ValueError(f'Missing dependency: task {task_id}.')
        if task_id in visiting:
            raise ValueError('Circular task dependency is not permitted.')
        if task_id in seen:
            return
        visiting.add(task_id)
        prereq = by_id[task_id].get('dependency_id')
        if prereq is not None:
            visit(int(prereq))
        visiting.remove(task_id)
        seen.add(task_id)
        ordered.append(task_id)

    for task_id in by_id:
        visit(task_id)
    result = {}
    for task_id in ordered:
        t = dict(by_id[task_id])
        start = kickoff + timedelta(days=int(t.get('start_offset_days') or 0))
        parent_id = t.get('dependency_id')
        if parent_id is not None:
            start = max(start, result[int(parent_id)]['end'])
        duration = int(t['duration_days']) + (int(t.get('delay_days') or 0) if include_delays else 0)
        if duration <= 0:
            raise ValueError('Duration must be greater than zero.')
        t['start'] = start
        t['end'] = start + timedelta(days=duration)
        t['effective_days'] = duration
        result[task_id] = t
    return list(result.values())


def earned_value(tasks, expenses, as_of):
    """Time-phased planned value (linear across each activity) and actual EV/AC.
    tasks must have baseline 'start', 'end' date fields from schedule(..., False).
    """
    as_of = parse_date(as_of)
    pv = ev = 0.0
    for t in tasks:
        cost = float(t['planned_cost'])
        elapsed = (as_of - t['start']).days
        total_days = (t['end'] - t['start']).days
        planned_fraction = min(1, max(0, elapsed / total_days))
        pv += cost * planned_fraction
        ev += cost * (int(t['progress']) / 100)
    ac = sum(float(expense['amount']) for expense in expenses)
    # Zero denominators do not imply a perfect performance index.
    return {
        'pv': round(pv, 2), 'ev': round(ev, 2), 'ac': round(ac, 2),
        'cpi': round(ev / ac, 3) if ac > 0 else None,
        'spi': round(ev / pv, 3) if pv > 0 else None,
        'cv': round(ev - ac, 2), 'sv': round(ev - pv, 2),
    }


def risk_score(likelihood, impact):
    return bounded_int(likelihood, 'Likelihood', 1, 5) * bounded_int(impact, 'Impact', 1, 5)


def revised_baselines(budget, deadline, cost_impact, schedule_impact):
    return (round(float(budget) + nonnegative_money(cost_impact, 'Cost impact'), 2),
            (parse_date(deadline) + timedelta(days=bounded_int(schedule_impact, 'Schedule impact', 0, 365))).isoformat())
