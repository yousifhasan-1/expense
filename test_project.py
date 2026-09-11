import sys

import pytest

from project import (
    Expense,
    ExpenseError,
    ExpenseLedger,
    clean_amount,
    generate_report,
    load_expenses,
    parse_args,
)


def test_clean_amount_plain_number():
    assert clean_amount("12.50") == 12.50


def test_clean_amount_with_dollar_sign():
    assert clean_amount("$45.20") == 45.20


def test_clean_amount_with_thousands_separator():
    assert clean_amount("$2,300.00") == 2300.00


def test_clean_amount_with_whitespace():
    assert clean_amount("  9.75  ") == 9.75


def test_clean_amount_accounting_negative():
    assert clean_amount("(45.00)") == -45.0


def test_clean_amount_invalid_raises_expense_error():
    with pytest.raises(ExpenseError):
        clean_amount("cheap")


def test_clean_amount_empty_string_raises():
    with pytest.raises(ExpenseError):
        clean_amount("")


def test_load_expenses_valid_rows(tmp_path):
    csv_content = (
        "date,category,amount,description\n"
        "2026-03-01,Food,$45.20,Weekly groceries\n"
        "2026-03-02,Transport,25.00,Gas\n"
    )
    csv_path = tmp_path / "expenses.csv"
    csv_path.write_text(csv_content)

    ledger = load_expenses(str(csv_path))

    assert len(ledger) == 2
    assert ledger.total() == pytest.approx(70.20)


def test_load_expenses_skips_malformed_rows_and_warns(tmp_path, capsys):
    csv_content = (
        "date,category,amount,description\n"
        "2026-03-01,Food,45.20,Weekly groceries\n"
        "not-a-date,Food,15.00,Bad date row\n"
        "2026-03-10,Entertainment,cheap,Non-numeric amount row\n"
    )
    csv_path = tmp_path / "expenses.csv"
    csv_path.write_text(csv_content)

    ledger = load_expenses(str(csv_path))
    captured = capsys.readouterr()

    assert len(ledger) == 1
    assert "Skipping line 3" in captured.err
    assert "Skipping line 4" in captured.err


def test_load_expenses_empty_file(tmp_path):
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("date,category,amount,description\n")

    ledger = load_expenses(str(csv_path))

    assert len(ledger) == 0
    assert bool(ledger) is False


def test_load_expenses_normalizes_category_case_and_blank(tmp_path):
    csv_content = (
        "date,category,amount,description\n"
        "2026-03-01,transport,10.00,Bus\n"
        "2026-03-02,,5.00,Unlabeled\n"
    )
    csv_path = tmp_path / "expenses.csv"
    csv_path.write_text(csv_content)

    ledger = load_expenses(str(csv_path))
    categories = {e.category for e in ledger}

    assert categories == {"Transport", "Uncategorized"}


def test_load_expenses_handles_quoted_thousands_separator(tmp_path):
    csv_content = (
        'date, category, amount, description\n'
        '2026-03-02, transport, "$2,300.00", Rent payment\n'
    )
    csv_path = tmp_path / "expenses.csv"
    csv_path.write_text(csv_content)

    ledger = load_expenses(str(csv_path))

    assert len(ledger) == 1
    assert list(ledger)[0].amount == pytest.approx(2300.00)


def test_ledger_category_totals():
    import datetime
    ledger = ExpenseLedger([
        Expense(datetime.date(2026, 3, 1), "Food", 10.0, "a"),
        Expense(datetime.date(2026, 3, 2), "Food", 5.0, "b"),
        Expense(datetime.date(2026, 3, 3), "Transport", 20.0, "c"),
    ])

    totals = ledger.category_totals()

    assert totals == {"Food": 15.0, "Transport": 20.0}


def test_ledger_top_expenses():
    import datetime
    ledger = ExpenseLedger([
        Expense(datetime.date(2026, 3, 1), "Food", 10.0, "a"),
        Expense(datetime.date(2026, 3, 2), "Transport", 100.0, "b"),
        Expense(datetime.date(2026, 3, 3), "Entertainment", 50.0, "c"),
    ])

    top = ledger.top_expenses(2)

    assert [e.amount for e in top] == [100.0, 50.0]


def test_ledger_filter_by_month():
    import datetime
    ledger = ExpenseLedger([
        Expense(datetime.date(2026, 3, 1), "Food", 10.0, "a"),
        Expense(datetime.date(2026, 4, 1), "Food", 20.0, "b"),
    ])

    march_only = ledger.filter_by_month("2026-03")

    assert len(march_only) == 1
    assert list(march_only)[0].amount == 10.0


def test_ledger_detect_anomalies_flags_outlier():
    import datetime
    ledger = ExpenseLedger([
        Expense(datetime.date(2026, 3, 1), "Food", 10.0, "a"),
        Expense(datetime.date(2026, 3, 2), "Food", 12.0, "b"),
        Expense(datetime.date(2026, 3, 3), "Food", 9.0, "c"),
        Expense(datetime.date(2026, 3, 4), "Transport", 2000.0, "outlier"),
    ])

    anomalies = ledger.detect_anomalies(threshold=1.0)

    assert len(anomalies) == 1
    assert anomalies[0].amount == 2000.0


def test_ledger_detect_anomalies_empty_ledger_returns_empty_list():
    ledger = ExpenseLedger()
    assert ledger.detect_anomalies() == []


def test_expense_equality():
    import datetime
    a = Expense(datetime.date(2026, 3, 1), "Food", 10.0, "lunch")
    b = Expense(datetime.date(2026, 3, 1), "Food", 10.0, "lunch")
    c = Expense(datetime.date(2026, 3, 1), "Food", 11.0, "lunch")

    assert a == b
    assert a != c


def test_parse_args_defaults():
    args = parse_args(["expenses.csv"])

    assert args.input == "expenses.csv"
    assert args.output == "report.md"
    assert args.month is None
    assert args.threshold == 2.0


def test_parse_args_custom_values():
    args = parse_args([
        "expenses.csv", "-o", "out.md", "-m", "2026-03", "--threshold", "3.5",
    ])

    assert args.output == "out.md"
    assert args.month == "2026-03"
    assert args.threshold == 3.5


def test_generate_report_writes_markdown_file(tmp_path):
    import datetime
    ledger = ExpenseLedger([
        Expense(datetime.date(2026, 3, 1), "Food", 10.0, "lunch"),
    ])
    output_path = tmp_path / "out.md"

    generate_report(ledger, [], str(output_path))

    content = output_path.read_text()
    assert "# Expense Report" in content
    assert "Food" in content
    assert "Expenses checked:** 1" in content


def test_generate_report_no_anomalies_section_says_none():
    import datetime
    ledger = ExpenseLedger([
        Expense(datetime.date(2026, 3, 1), "Food", 10.0, "lunch"),
    ])
    from project import ExpenseReport
    report = ExpenseReport(ledger, [])
    rendered = report.render()

    assert "No unusual expenses found." in rendered
