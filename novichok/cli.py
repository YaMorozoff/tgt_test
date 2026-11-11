"""Консольный отчёт по рискам адаптации сотрудников."""

import argparse
import csv
from collections import Counter
from datetime import date
from pathlib import Path

from .risk import assess


BASE_DIR = Path(__file__).resolve().parent
EMPLOYEES_PATH = BASE_DIR / "data" / "employees.csv"
TASKS_PATH = BASE_DIR / "data" / "tasks.csv"
LEVELS = ("зелёный", "жёлтый", "красный")
HEADERS = ("ID", "Сотрудник", "Отдел", "День", "Баллы", "Уровень", "Причины")


def load_csv(path):
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def build_report_rows(employees, tasks, today, department=None, level=None):
    rows = []
    for employee in employees:
        if department is not None and employee["department"] != department:
            continue

        result = assess(employee, tasks, today)
        if level is not None and result["level"] != level:
            continue

        rows.append(
            {
                "employee_id": employee["employee_id"],
                "full_name": employee["full_name"],
                "department": employee["department"],
                "day": (today - date.fromisoformat(employee["hire_date"])).days,
                "score": result["score"],
                "level": result["level"],
                "reasons": result["reasons"],
            }
        )
    return rows


def render_table(rows):
    table_rows = [
        (
            row["employee_id"],
            row["full_name"],
            row["department"],
            str(row["day"]),
            str(row["score"]),
            row["level"],
            "; ".join(row["reasons"]) if row["reasons"] else "—",
        )
        for row in rows
    ]
    widths = [
        max(len(HEADERS[column]), *(len(row[column]) for row in table_rows))
        if table_rows
        else len(HEADERS[column])
        for column in range(len(HEADERS))
    ]

    def format_row(row):
        return " | ".join(
            value.ljust(widths[column]) for column, value in enumerate(row)
        )

    lines = [format_row(HEADERS)]
    lines.append("-+-".join("-" * width for width in widths))
    lines.extend(format_row(row) for row in table_rows)
    return "\n".join(lines)


def render_summary(rows):
    counts = Counter(row["level"] for row in rows)
    return (
        f"Всего: {len(rows)}; "
        f"зелёный: {counts['зелёный']}; "
        f"жёлтый: {counts['жёлтый']}; "
        f"красный: {counts['красный']}"
    )


def build_parser():
    parser = argparse.ArgumentParser(
        description="Консольный дашборд адаптации новых сотрудников"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    report_parser = subparsers.add_parser("report", help="Показать отчёт по рискам")
    report_parser.add_argument("--department", help="Фильтр по точному названию отдела")
    report_parser.add_argument("--level", choices=LEVELS, help="Фильтр по уровню риска")
    return parser


def main(argv=None, today=None):
    args = build_parser().parse_args(argv)
    employees = load_csv(EMPLOYEES_PATH)
    tasks = load_csv(TASKS_PATH)
    rows = build_report_rows(
        employees,
        tasks,
        today or date.today(),
        department=args.department,
        level=args.level,
    )
    print(render_table(rows))
    print()
    print(render_summary(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
