"""Детерминированный генератор демонстрационных данных проекта «Новичок»."""

import csv
from collections import Counter
from datetime import date, timedelta
from pathlib import Path


TODAY = date(2026, 11, 11)
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
EMPLOYEE_FIELDS = [
    "employee_id",
    "full_name",
    "role",
    "department",
    "hire_date",
    "mentor_id",
    "status",
]
TASK_FIELDS = [
    "task_id",
    "employee_id",
    "title",
    "category",
    "created_date",
    "due_date",
    "status",
    "completed_date",
    "checkpoint_day",
]

FIRST_NAMES = (
    "Александр",
    "Алексей",
    "Андрей",
    "Артём",
    "Дмитрий",
    "Иван",
    "Максим",
    "Михаил",
)
SURNAMES = (
    "Иванов",
    "Петров",
    "Сидоров",
    "Смирнов",
    "Кузнецов",
    "Попов",
    "Волков",
    "Соколов",
    "Лебедев",
    "Морозов",
)
ROLES = (
    "Инженер",
    "Аналитик",
    "Разработчик",
    "Тестировщик",
    "Менеджер продукта",
    "Дизайнер",
    "Специалист поддержки",
    "Системный администратор",
)
DEPARTMENTS = ("Разработка", "Аналитика", "Продукт", "Инфраструктура")
COMMON_TASKS = (
    ("Оформить доступы и оборудование", "документы", 2),
    ("Пройти вводный инструктаж", "обучение", 3),
    ("Познакомиться с командой", "знакомство", 7),
    ("Изучить процессы отдела", "обучение", 14),
    ("Выполнить первую рабочую задачу", "работа", 30),
)
CHECKPOINTS = (7, 30, 60, 90)


class DatasetBuilder:
    def __init__(self):
        self.employees = []
        self.tasks = []
        self.groups = {}
        self._task_number = 1

    def _add_task(
        self,
        employee_id,
        title,
        category,
        hire_date,
        due_offset,
        is_done,
        checkpoint_day="",
    ):
        due_date = hire_date + timedelta(days=due_offset)
        self.tasks.append(
            {
                "task_id": f"t{self._task_number:04d}",
                "employee_id": employee_id,
                "title": title,
                "category": category,
                "created_date": hire_date.isoformat(),
                "due_date": due_date.isoformat(),
                "status": "done" if is_done else "open",
                "completed_date": due_date.isoformat() if is_done else "",
                "checkpoint_day": checkpoint_day,
            }
        )
        self._task_number += 1

    def add_employee(
        self,
        group,
        day,
        mentor=True,
        status="active",
        open_common=(),
        missed_checkpoints=(),
        extra_open=(),
    ):
        index = len(self.employees) + 1
        employee_id = f"e{index:03d}"
        hire_date = TODAY - timedelta(days=day)
        first_name = FIRST_NAMES[(index - 1) // len(SURNAMES)]
        surname = SURNAMES[(index - 1) % len(SURNAMES)]
        self.employees.append(
            {
                "employee_id": employee_id,
                "full_name": f"{surname} {first_name}",
                "role": ROLES[(index - 1) % len(ROLES)],
                "department": DEPARTMENTS[(index - 1) % len(DEPARTMENTS)],
                "hire_date": hire_date.isoformat(),
                "mentor_id": f"m{(index % 8) + 1:02d}" if mentor else "",
                "status": status,
            }
        )
        self.groups[employee_id] = group

        for task_index, (title, category, due_offset) in enumerate(COMMON_TASKS):
            is_done = due_offset <= day and task_index not in open_common
            self._add_task(
                employee_id, title, category, hire_date, due_offset, is_done
            )

        for checkpoint_day in CHECKPOINTS:
            is_done = (
                checkpoint_day <= day and checkpoint_day not in missed_checkpoints
            )
            self._add_task(
                employee_id,
                f"Контрольная беседа {checkpoint_day} дня",
                "контрольная беседа",
                hire_date,
                checkpoint_day,
                is_done,
                checkpoint_day,
            )

        for extra_index, due_offset in enumerate(extra_open, start=1):
            self._add_task(
                employee_id,
                f"Дополнительная рабочая задача {extra_index}",
                "работа",
                hire_date,
                due_offset,
                False,
            )


def build_dataset():
    builder = DatasetBuilder()

    # Зелёные: нет риска либо одна-две обычные просрочки (0–2 балла).
    for index in range(20):
        if index < 15:
            day = (10, 20, 30, 60, 90)[index % 5]
            extra_open = ()
        else:
            day = 45
            extra_open = (14,) if index % 2 else (14, 20)
        builder.add_employee("зелёный", day=day, extra_open=extra_open)

    # Жёлтые: три просрочки либо две просрочки и отсутствие наставника.
    for index in range(10):
        builder.add_employee("жёлтый", day=45, extra_open=(14, 20, 25))
    for index in range(10):
        builder.add_employee(
            "жёлтый", day=45, mentor=False, extra_open=(14, 20)
        )

    # Красные: 5 баллов либо пропущенная беседа и дополнительные просрочки.
    for index in range(10):
        builder.add_employee(
            "красный", day=45, mentor=False, extra_open=(14, 20, 25)
        )
    for index in range(10):
        builder.add_employee(
            "красный",
            day=45,
            missed_checkpoints=(7,),
            extra_open=(14, 20, 25),
        )

    # Пограничные: дни 3/4, 90/91, left, дедлайн сегодня и порог первой недели.
    for index in range(4):
        builder.add_employee("пограничный", day=3, mentor=False)
    for index in range(4):
        builder.add_employee("пограничный", day=4, mentor=False)
    for index in range(2):
        builder.add_employee("пограничный", day=90)
    for index in range(2):
        builder.add_employee(
            "пограничный",
            day=91,
            mentor=False,
            extra_open=(10, 11, 12, 13, 14),
        )
    for index in range(2):
        builder.add_employee(
            "пограничный",
            day=30,
            mentor=False,
            status="left",
            open_common=(0, 1, 2, 3, 4),
            missed_checkpoints=(7, 30),
            extra_open=(10, 11, 12),
        )
    for index in range(2):
        builder.add_employee("пограничный", day=30, extra_open=(30,))
    for index in range(2):
        builder.add_employee(
            "пограничный",
            day=7,
            open_common=(2,),
            missed_checkpoints=(7,),
        )
    for index in range(2):
        builder.add_employee(
            "пограничный",
            day=7,
            open_common=(1, 2),
            missed_checkpoints=(7,),
        )

    return builder.employees, builder.tasks, builder.groups


def validate_dataset(employees, tasks, groups):
    assert len(employees) == 80, "Должно быть ровно 80 сотрудников"
    assert len({row["employee_id"] for row in employees}) == 80
    assert len({row["full_name"] for row in employees}) == 80
    assert all(list(row) == EMPLOYEE_FIELDS for row in employees)
    assert all(list(row) == TASK_FIELDS for row in tasks)
    assert len({row["task_id"] for row in tasks}) == len(tasks)
    employee_ids = {row["employee_id"] for row in employees}
    assert {row["employee_id"] for row in tasks} <= employee_ids
    assert Counter(groups.values()) == {
        "зелёный": 20,
        "жёлтый": 20,
        "красный": 20,
        "пограничный": 20,
    }


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    employees, tasks, groups = build_dataset()
    validate_dataset(employees, tasks, groups)
    employees_path = DATA_DIR / "employees.csv"
    tasks_path = DATA_DIR / "tasks.csv"
    write_csv(employees_path, EMPLOYEE_FIELDS, employees)
    write_csv(tasks_path, TASK_FIELDS, tasks)

    print(f"Сотрудников: {len(employees)}, задач: {len(tasks)}")
    print(f"Сотрудники: {employees_path}")
    print(f"Задачи: {tasks_path}")
    for group in ("зелёный", "жёлтый", "красный", "пограничный"):
        print(f"{group}: {Counter(groups.values())[group]}")


if __name__ == "__main__":
    main()
