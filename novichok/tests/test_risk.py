from copy import deepcopy
from datetime import date, timedelta

import pytest

from novichok.risk import assess


TODAY = date(2026, 11, 11)


def make_employee(day=30, status="active", mentor_id="mentor-1"):
    return {
        "employee_id": "employee-1",
        "hire_date": (TODAY - timedelta(days=day)).isoformat(),
        "mentor_id": mentor_id,
        "status": status,
    }


def make_task(
    employee,
    task_id="task-1",
    due_day=20,
    status="open",
    category="документы",
    checkpoint_day="",
    completed_day=None,
):
    hire_date = date.fromisoformat(employee["hire_date"])
    if status == "done" and completed_day is None:
        completed_day = due_day
    completed_date = (
        (hire_date + timedelta(days=completed_day)).isoformat()
        if completed_day is not None
        else ""
    )
    return {
        "task_id": task_id,
        "employee_id": employee["employee_id"],
        "title": task_id,
        "category": category,
        "created_date": employee["hire_date"],
        "due_date": (hire_date + timedelta(days=due_day)).isoformat(),
        "status": status,
        "completed_date": completed_date,
        "checkpoint_day": checkpoint_day,
    }


def test_day_3_without_mentor_does_not_trigger():
    employee = make_employee(day=3, mentor_id="")

    result = assess(employee, [], TODAY)

    assert result["score"] == 0
    assert result["reasons"] == []


def test_day_4_without_mentor_adds_2_points():
    employee = make_employee(day=4, mentor_id="")

    result = assess(employee, [], TODAY)

    assert result["score"] == 2
    assert result["level"] == "зелёный"
    assert result["reasons"] == ["На 4-й день адаптации не назначен наставник"]
    assert result["actions"] == ["Назначить наставника сегодня"]


@pytest.mark.parametrize(("count", "expected_score"), [(0, 0), (1, 1), (3, 3), (5, 3)])
def test_overdue_task_scores_and_cap(count, expected_score):
    employee = make_employee()
    tasks = [
        make_task(employee, task_id=f"task-{index}", due_day=20 + index)
        for index in range(count)
    ]

    result = assess(employee, tasks, TODAY)

    assert result["score"] == expected_score


def test_checkpoint_7_completed_on_time_has_no_risk():
    employee = make_employee()
    task = make_task(
        employee,
        due_day=7,
        status="done",
        category="контрольная беседа",
        checkpoint_day=7,
        completed_day=7,
    )

    result = assess(employee, [task], TODAY)

    assert result == {"score": 0, "level": "зелёный", "reasons": [], "actions": []}


def test_checkpoint_7_completed_late_is_not_currently_overdue():
    employee = make_employee()
    task = make_task(
        employee,
        due_day=7,
        status="done",
        category="контрольная беседа",
        checkpoint_day=7,
        completed_day=8,
    )

    result = assess(employee, [task], TODAY)

    assert result["score"] == 0
    assert result["reasons"] == []


def test_open_checkpoint_7_adds_special_score_reason_and_action():
    employee = make_employee()
    completed = make_task(employee, task_id="done", due_day=3, status="done")
    missed = make_task(
        employee,
        task_id="missed",
        due_day=7,
        category="контрольная беседа",
        checkpoint_day=7,
    )

    result = assess(employee, [completed, missed], TODAY)

    assert result["score"] == 4  # Общее правило +1 и правило беседы +3.
    assert "Не проведена беседа 7 дня, просрочена на 23 дня" in result["reasons"]
    assert "Назначить беседу с руководителем на этой неделе" in result["actions"]


def test_day_90_is_inside_assessment_window():
    employee = make_employee(day=90, mentor_id="")

    result = assess(employee, [], TODAY)

    assert result["score"] == 2
    assert result["reasons"] == ["На 90-й день адаптации не назначен наставник"]


def test_day_91_is_outside_assessment_window():
    employee = make_employee(day=91, mentor_id="")
    overdue = make_task(employee)

    result = assess(employee, [overdue], TODAY)

    assert result == {"score": 0, "level": "зелёный", "reasons": [], "actions": []}


def test_left_employee_is_not_assessed():
    employee = make_employee(status="left", mentor_id="")
    tasks = [make_task(employee, task_id=f"task-{index}") for index in range(5)]

    result = assess(employee, tasks, TODAY)

    assert result == {"score": 0, "level": "зелёный", "reasons": [], "actions": []}


def test_other_employees_tasks_do_not_affect_score():
    employee = make_employee()
    tasks = [make_task(employee, task_id=f"task-{index}") for index in range(5)]
    for task in tasks:
        task["employee_id"] = "another-employee"

    result = assess(employee, tasks, TODAY)

    assert result["score"] == 0
    assert result["reasons"] == []


def test_task_due_today_is_not_overdue():
    employee = make_employee()
    task = make_task(employee, due_day=30)

    result = assess(employee, [task], TODAY)

    assert result["score"] == 0


def test_first_week_completion_below_50_percent_adds_2_points():
    employee = make_employee(day=7)
    task = make_task(employee, due_day=7)

    result = assess(employee, [task], TODAY)

    assert result["score"] == 2
    assert result["reasons"] == [
        "За первые 7 дней закрыто 0 из 1 задач с дедлайном в этот период "
        "(0%, меньше 50%)"
    ]


def test_first_week_completion_exactly_50_percent_does_not_trigger():
    employee = make_employee(day=7)
    completed = make_task(employee, task_id="done", due_day=3, status="done")
    open_task = make_task(employee, task_id="open", due_day=7)

    result = assess(employee, [completed, open_task], TODAY)

    assert result["score"] == 0


def test_first_week_rule_does_not_run_before_day_7():
    employee = make_employee(day=6)
    task = make_task(employee, due_day=6)

    result = assess(employee, [task], TODAY)

    assert result["score"] == 0


def test_score_5_has_red_level():
    employee = make_employee(mentor_id="")
    tasks = [make_task(employee, task_id=f"task-{index}") for index in range(5)]

    result = assess(employee, tasks, TODAY)

    assert result["score"] == 5
    assert result["level"] == "красный"


def test_assess_does_not_mutate_inputs_and_accepts_explicit_today():
    employee = make_employee(day=4, mentor_id="")
    tasks = [make_task(employee)]
    employee_before = deepcopy(employee)
    tasks_before = deepcopy(tasks)

    from_string = assess(employee, tasks, "2026-11-11")
    from_date = assess(employee, tasks, TODAY)

    assert employee == employee_before
    assert tasks == tasks_before
    assert from_string == from_date
