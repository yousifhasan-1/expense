import argparse
import csv
import statistics
import sys
from datetime import datetime


class ExpenseError(ValueError):
    pass

class Expense:
    def __init__(self, date, category, amount, description):
        self.date = date
        self.category = category
        self.amount = float(amount)
        self.description = description

    def __str__(self):
        return (
            f"{self.date.isoformat()} **{self.category}** "
            f"${self.amount:.2f} - {self.description}"
        )

    def __repr__(self):
        return (
            f"Expense(date={self.date!r}, category={self.category!r}, "
            f"amount={self.amount!r}, description={self.description!r})"
        )

    def __eq__(self, other):
        if not isinstance(other, Expense):
            return NotImplemented
        return (
            self.date == other.date
            and self.category == other.category
            and self.amount == other.amount
            and self.description == other.description
        )


class ExpenseLedger:
    def __init__(self, expenses=None):
        self._expenses = list(expenses) if expenses else []

    def add(self, expense):
        if not isinstance(expense, Expense):
            raise TypeError("The ledger only accepts expenses")
        self._expenses.append(expense)

    def __iter__(self):
        return iter(self._expenses)

    def __len__(self):
        return len(self._expenses)

    def __bool__(self):
        return len(self._expenses) > 0

    def total(self):
        return sum(expense.amount for expense in self._expenses)

    def category_totals(self):
        totals = {}
        for expense in self._expenses:
            totals[expense.category] = totals.get(expense.category, 0.0) + expense.amount
        return totals

    def top_expenses(self, n=5):
        return sorted(self._expenses, key=lambda e: e.amount, reverse=True)[:n]

    def filter_by_month(self, month):
        matches = [e for e in self._expenses if e.date.strftime("%Y-%m") == month]
        return ExpenseLedger(matches)

    def detect_anomalies(self, threshold=2.0):
        if len(self._expenses) < 2:
            return []

        amounts = [e.amount for e in self._expenses]
        mean = statistics.mean(amounts)
        stdev = statistics.pstdev(amounts)

        if stdev == 0:
            return []

        return [
            e for e in self._expenses
            if abs(e.amount - mean) > threshold * stdev
        ]


class ExpenseReport:
    def __init__(self, ledger, anomalies):
        self.ledger = ledger
        self.anomalies = anomalies

    def _category_section(self):
        totals = self.ledger.category_totals()
        grand_total = self.ledger.total()
        rows = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)

        lines = [
            "## Spending by category",
            "| Category | Total | % of Spend |",
            "|---|---|---|",
        ]
        for category, total in rows:
            pct = (total / grand_total * 100) if grand_total else 0.0
            lines.append(f"| {category} | ${total:.2f} | {pct:.1f}% |")
        return "\n".join(lines)

    def _top_expenses_section(self, n=5):
        lines = [f"## {n} biggest expenses"]
        for expense in self.ledger.top_expenses(n):
            lines.append(f"- {expense}")
        return "\n".join(lines)

    def _anomalies_section(self):
        lines = ["## Unusual expenses"]
        if not self.anomalies:
            lines.append("- No unusual expenses found.")
        else:
            for expense in self.anomalies:
                lines.append(f"- {expense}")
        return "\n".join(lines)

    def render(self):
        parts = [
            "# Expense Report",
            f"- **Expenses checked:** {len(self.ledger)}",
            f"- **Total cost:** ${self.ledger.total():.2f}",
            "",
            self._category_section(),
            "",
            self._top_expenses_section(),
            "",
            self._anomalies_section(),
        ]
        return "\n".join(parts) + "\n"

    def write(self, path):
        with open(path, "w", encoding="utf-8") as report_file:
            report_file.write(self.render())


def clean_amount(raw):
    if raw is None:
        raise ExpenseError("could not read amount from 'None'")

    text = str(raw).strip()
    original = text

    if not text:
        raise ExpenseError(f"could not read amount from '{original}'")

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1].strip()

    text = text.replace("$", "").replace(",", "").strip()

    if not text:
        raise ExpenseError(f"could not read amount from '{original}'")

    try:
        value = float(text)
    except ValueError:
        raise ExpenseError(f"could not read amount from '{original}'")

    return -value if negative else value


def _normalize_category(raw):
    category = (raw or "").strip()
    return category.title() if category else "Uncategorized"


def _parse_date(raw):
    text = (raw or "").strip()
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise ExpenseError(f"bad date '{raw}'")


def load_expenses(path):
    ledger = ExpenseLedger()

    with open(path, newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file, skipinitialspace=True)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]

        for line_num, row in enumerate(reader, start=2):
            try:
                date_value = _parse_date(row.get("date"))
                category = _normalize_category(row.get("category"))
                amount = clean_amount(row.get("amount"))
                description = (row.get("description") or "").strip()

                ledger.add(Expense(date_value, category, amount, description))
            except ExpenseError as error:
                print(f"Skipping line {line_num}: {error}", file=sys.stderr)
                continue

    return ledger


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="project.py",
        description="ExpenseIQ: Expense analyzer",
    )
    parser.add_argument("input", help="Input CSV file.")
    parser.add_argument(
        "-o", "--output",
        default="report.md",
        help="Output report file.",
    )
    parser.add_argument(
        "-m", "--month",
        default=None,
        help="Show one month, like 2026-03.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=2.0,
        help="Number used to find unusual expenses.",
    )
    return parser.parse_args(argv)


def generate_report(ledger, anomalies, output_path):
    report = ExpenseReport(ledger, anomalies)
    report.write(output_path)
    return output_path


def main():
    args = parse_args()

    ledger = load_expenses(args.input)

    if args.month:
        ledger = ledger.filter_by_month(args.month)

    anomalies = ledger.detect_anomalies(threshold=args.threshold)

    print(f"Checked {len(ledger)} expense(s).")
    print(f"Total cost: ${ledger.total():.2f}")
    print("By category:")
    for category, total in sorted(
        ledger.category_totals().items(), key=lambda kv: kv[1], reverse=True
    ):
        print(f"  {category}: ${total:.2f}")
    print(f"{len(anomalies)} unusual expense(s) found. See the report for details.")

    generate_report(ledger, anomalies, args.output)
    print(f"Report saved to {args.output}")


if __name__ == "__main__":
    main()
