"""Streamlit-дашборд адаптации новых сотрудников."""

import csv
from collections import Counter
from datetime import date
from pathlib import Path

import streamlit as st

if __package__:
    from .risk import assess
else:
    from risk import assess


BASE_DIR = Path(__file__).resolve().parent
EMPLOYEES_PATH = BASE_DIR / "data" / "employees.csv"
TASKS_PATH = BASE_DIR / "data" / "tasks.csv"
LEVEL_STYLES = {
    "зелёный": "🟢 зелёный",
    "жёлтый": "🟡 жёлтый",
    "красный": "🔴 красный",
}


def load_csv(path):
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


@st.cache_data(show_spinner=False)
def load_data():
    return load_csv(EMPLOYEES_PATH), load_csv(TASKS_PATH)


def build_records(employees, tasks, today):
    records = []
    for employee in employees:
        result = assess(employee, tasks, today)
        own_tasks = sorted(
            (task for task in tasks if task["employee_id"] == employee["employee_id"]),
            key=lambda task: (task["due_date"], task["task_id"]),
        )
        overdue_count = sum(
            task["status"] == "open" and task["due_date"] < today.isoformat()
            for task in own_tasks
        )
        records.append(
            {
                "employee": employee,
                "day": (today - date.fromisoformat(employee["hire_date"])).days,
                "score": result["score"],
                "level": result["level"],
                "reasons": result["reasons"],
                "actions": result["actions"],
                "tasks": own_tasks,
                "open_count": sum(task["status"] == "open" for task in own_tasks),
                "overdue_count": overdue_count,
            }
        )
    return records


def build_table_rows(records):
    return [
        {
            "ID": record["employee"]["employee_id"],
            "Сотрудник": record["employee"]["full_name"],
            "Роль": record["employee"]["role"],
            "Отдел": record["employee"]["department"],
            "День": record["day"],
            "Статус": record["employee"]["status"],
            "Баллы": record["score"],
            "Риск": LEVEL_STYLES[record["level"]],
            "Причины": "; ".join(record["reasons"]) or "—",
        }
        for record in records
    ]


def deadline_label(task, today):
    if task["status"] == "done":
        return f"✅ Выполнена {task['completed_date']}"

    due_date = date.fromisoformat(task["due_date"])
    days_left = (due_date - today).days
    if days_left < 0:
        return f"🔴 Просрочена на {-days_left} дн."
    if days_left == 0:
        return "🟡 Дедлайн сегодня"
    return f"⏳ Осталось {days_left} дн."


def build_task_rows(record, today):
    return [
        {
            "Задача": task["title"],
            "Категория": task["category"],
            "Дедлайн": task["due_date"],
            "Состояние": deadline_label(task, today),
            "Контрольный день": task["checkpoint_day"] or "—",
        }
        for task in record["tasks"]
    ]


def render_checkpoints(record, today):
    checkpoints = [
        task
        for task in record["tasks"]
        if task["category"] == "контрольная беседа"
        and task["checkpoint_day"] in {"7", "30", "60", "90"}
    ]
    if not checkpoints:
        st.info("Контрольные беседы не запланированы.")
        return

    columns = st.columns(len(checkpoints))
    for column, task in zip(columns, checkpoints):
        with column:
            st.markdown(f"**День {task['checkpoint_day']}**")
            st.caption(f"Дедлайн: {task['due_date']}")
            if task["status"] == "done":
                st.success(f"Проведена {task['completed_date']}")
            elif task["due_date"] < today.isoformat():
                st.error("Беседа просрочена")
            elif task["due_date"] == today.isoformat():
                st.warning("Беседа запланирована на сегодня")
            else:
                st.info("Запланирована")


def render_employee_card(record, today):
    employee = record["employee"]
    st.divider()
    st.subheader(
        f"{employee['full_name']} · {LEVEL_STYLES[record['level']]}"
    )
    st.caption(
        f"{employee['role']} · {employee['department']} · ID {employee['employee_id']}"
    )

    metrics = st.columns(4)
    metrics[0].metric("День адаптации", record["day"])
    metrics[1].metric("Баллы риска", record["score"])
    metrics[2].metric("Открытые задачи", record["open_count"])
    metrics[3].metric("Просрочено", record["overdue_count"])

    st.markdown(
        f"**Дата найма:** {employee['hire_date']}  \n"
        f"**Наставник:** {employee['mentor_id'] or 'Не назначен'}  \n"
        f"**Статус:** {employee['status']}"
    )
    if employee["status"] == "left":
        st.info("Сотрудник выбыл: риск не начисляется, уровень нейтральный.")
    elif not 0 <= record["day"] <= 90:
        st.info("Сотрудник вне окна адаптации 0–90: риск не начисляется.")

    if record["reasons"]:
        st.markdown("**Причины риска**")
        st.markdown("\n".join(f"- {reason}" for reason in record["reasons"]))

    st.markdown("**Рекомендуемые действия**")
    if record["actions"]:
        st.markdown("\n".join(f"- {action}" for action in record["actions"]))
    else:
        st.success("Дополнительные действия по правилам риска не требуются.")

    st.markdown("### Таймлайн контрольных бесед")
    render_checkpoints(record, today)

    with st.expander("Задачи и дедлайны", expanded=True):
        st.dataframe(
            build_task_rows(record, today),
            width="stretch",
            hide_index=True,
        )


def main():
    st.set_page_config(
        page_title="Адаптация новичков",
        page_icon="🟢",
        layout="wide",
    )
    today = date.today()
    employees, tasks = load_data()
    records = build_records(employees, tasks, today)

    st.title("Дашборд адаптации новых сотрудников")
    st.caption(f"Дата расчёта: {today.isoformat()} · окно адаптации: 0–90 дней")

    st.sidebar.header("Фильтры")
    departments = sorted({employee["department"] for employee in employees})
    department = st.sidebar.selectbox("Отдел", ["Все отделы", *departments])
    level = st.sidebar.selectbox(
        "Уровень риска",
        ["Все уровни", *LEVEL_STYLES],
    )
    filtered = [
        record
        for record in records
        if (department == "Все отделы" or record["employee"]["department"] == department)
        and (level == "Все уровни" or record["level"] == level)
    ]

    counts = Counter(record["level"] for record in filtered)
    summary = st.columns(4)
    summary[0].metric("Сотрудники", len(filtered))
    summary[1].metric("🟢 Зелёный", counts["зелёный"])
    summary[2].metric("🟡 Жёлтый", counts["жёлтый"])
    summary[3].metric("🔴 Красный", counts["красный"])

    st.dataframe(
        build_table_rows(filtered),
        width="stretch",
        hide_index=True,
    )
    if not filtered:
        st.warning("По выбранным фильтрам сотрудники не найдены.")
        return

    labels = {
        record["employee"]["employee_id"]: (
            f"{record['employee']['full_name']} · {record['employee']['employee_id']}"
        )
        for record in filtered
    }
    selected_id = st.selectbox(
        "Карточка сотрудника",
        options=list(labels),
        format_func=labels.get,
    )
    selected = next(
        record
        for record in filtered
        if record["employee"]["employee_id"] == selected_id
    )
    render_employee_card(selected, today)


if __name__ == "__main__":
    main()
