"""Прозрачные правила оценки риска адаптации новичка."""

from datetime import date, datetime
from typing import Any, Iterable, Mapping


PARAMS = {
    "window_first_day": 0,
    "window_last_day": 90,
    "mentor_grace_day": 3,
    "no_mentor_score": 2,
    "overdue_task_score": 1,
    "overdue_tasks_score_cap": 3,
    "missed_checkpoint_score": 3,
    "checkpoint_days": (7, 30, 60, 90),
    "first_week_last_day": 7,
    "first_week_completion_threshold": 0.5,
    "first_week_score": 2,
    "yellow_min_score": 3,
    "red_min_score": 5,
}


def _as_date(value: Any, field_name: str) -> date:
    """Преобразует date/datetime или ISO-строку без обращения к системным часам."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise ValueError(
                f"{field_name}: ожидалась дата в формате ГГГГ-ММ-ДД, получено {value!r}"
            ) from exc
    raise ValueError(f"{field_name}: дата не задана или имеет неверный тип")


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        return bool(value != value)  # Поддерживает NaN без зависимости от pandas.
    except (TypeError, ValueError):
        return False


def _day_word(number: int) -> str:
    if number % 10 == 1 and number % 100 != 11:
        return "день"
    if 2 <= number % 10 <= 4 and not 12 <= number % 100 <= 14:
        return "дня"
    return "дней"


def _task_word(number: int) -> str:
    if number % 10 == 1 and number % 100 != 11:
        return "задача"
    if 2 <= number % 10 <= 4 and not 12 <= number % 100 <= 14:
        return "задачи"
    return "задач"


def _neutral_result() -> dict[str, Any]:
    return {"score": 0, "level": "зелёный", "reasons": [], "actions": []}


def assess(
    employee: Mapping[str, Any],
    tasks: Iterable[Mapping[str, Any]],
    today: date | str,
) -> dict[str, Any]:
    """Возвращает балл, уровень риска, причины и действия для одного новичка.

    Функция не читает файлы, не изменяет входные данные и не использует системную дату.
    Для left и сотрудников вне дней 0–90 возвращается нейтральный результат.
    Контрольная беседа является задачей адаптации, поэтому при просрочке участвует
    и в общем правиле (+1 с учётом общего капа), и в специальном правиле (+3).
    """
    if employee.get("status") != "active":
        return _neutral_result()

    today_date = _as_date(today, "today")
    hire_date = _as_date(employee.get("hire_date"), "hire_date")
    employee_day = (today_date - hire_date).days
    if not PARAMS["window_first_day"] <= employee_day <= PARAMS["window_last_day"]:
        return _neutral_result()

    employee_id = employee.get("employee_id")
    own_tasks = [task for task in tasks if task.get("employee_id") == employee_id]
    score = 0
    reasons: list[str] = []
    actions: list[str] = []

    def add_action(action: str) -> None:
        if action not in actions:
            actions.append(action)

    if employee_day > PARAMS["mentor_grace_day"] and _is_blank(employee.get("mentor_id")):
        score += PARAMS["no_mentor_score"]
        reasons.append(f"На {employee_day}-й день адаптации не назначен наставник")
        add_action("Назначить наставника сегодня")

    overdue_tasks: list[tuple[Mapping[str, Any], date]] = []
    for task in own_tasks:
        if task.get("status") != "open":
            continue
        due_date = _as_date(task.get("due_date"), "due_date")
        if due_date < today_date:
            overdue_tasks.append((task, due_date))

    if overdue_tasks:
        overdue_count = len(overdue_tasks)
        points = min(
            overdue_count * PARAMS["overdue_task_score"],
            PARAMS["overdue_tasks_score_cap"],
        )
        score += points
        reasons.append(
            f"Просрочено {overdue_count} {_task_word(overdue_count)} адаптации; "
            f"начислено {points} из {PARAMS['overdue_tasks_score_cap']} возможных баллов"
        )
        add_action("Согласовать план закрытия просроченных задач адаптации на сегодня")

    for task, due_date in overdue_tasks:
        if task.get("category") != "контрольная беседа":
            continue
        try:
            checkpoint_day = int(task.get("checkpoint_day"))
        except (TypeError, ValueError):
            continue
        if checkpoint_day not in PARAMS["checkpoint_days"]:
            continue
        delay = (today_date - due_date).days
        score += PARAMS["missed_checkpoint_score"]
        reasons.append(
            f"Не проведена беседа {checkpoint_day} дня, просрочена на "
            f"{delay} {_day_word(delay)}"
        )
        add_action("Назначить беседу с руководителем на этой неделе")

    if employee_day >= PARAMS["first_week_last_day"]:
        first_week_tasks = []
        for task in own_tasks:
            due_date = _as_date(task.get("due_date"), "due_date")
            if 0 <= (due_date - hire_date).days <= PARAMS["first_week_last_day"]:
                first_week_tasks.append(task)

        if first_week_tasks:
            completed = sum(task.get("status") == "done" for task in first_week_tasks)
            completion_rate = completed / len(first_week_tasks)
            if completion_rate < PARAMS["first_week_completion_threshold"]:
                score += PARAMS["first_week_score"]
                reasons.append(
                    f"За первые 7 дней закрыто {completed} из {len(first_week_tasks)} "
                    f"задач с дедлайном в этот период "
                    f"({completion_rate:.0%}, меньше 50%)"
                )
                add_action("Разобрать невыполненные задачи первой недели с руководителем")

    if score >= PARAMS["red_min_score"]:
        level = "красный"
    elif score >= PARAMS["yellow_min_score"]:
        level = "жёлтый"
    else:
        level = "зелёный"

    return {"score": score, "level": level, "reasons": reasons, "actions": actions}
