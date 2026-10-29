"""The demo app must render, and must not show a stack trace.

AppTest runs app.py in-process, so these are ordinary tests: no browser, no
port, no flakiness. They exist because a demo that crashes in front of
someone is worse than no demo, and "it worked when I tried it" is not a
check anybody can re-run.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from streamlit.testing.v1 import AppTest

TIMEOUT = 120
# Relative paths resolve against THIS file, not the working directory.
APP = str(Path(__file__).resolve().parents[2] / "app.py")


@pytest.fixture(scope="module")
def shop_db(tmp_path_factory):
    p = tmp_path_factory.mktemp("appdata") / "shop.db"
    con = sqlite3.connect(p)
    con.executescript("""
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT,
                                country TEXT);
        CREATE TABLE orders (id INTEGER PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(id),
            placed_at TIMESTAMP, total REAL, status TEXT);
        INSERT INTO customers VALUES (1,'Ada','UK'),(2,'Grace','US');
        INSERT INTO orders VALUES
            (1,1,'2024-01-05 10:00:00',99.5,'paid'),
            (2,1,'2024-01-07 11:00:00',12.0,'paid'),
            (3,2,'2024-02-01 09:30:00',45.25,'refunded');
    """)
    con.commit(); con.close()
    return str(p)


def app_on(source: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.run()
    at.sidebar.text_input[0].set_value(source).run()
    return at


class TestItRuns:
    def test_the_app_starts_without_an_exception(self):
        at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
        assert not at.exception

    def test_a_real_source_renders_a_tab_per_view(self, shop_db):
        at = app_on(shop_db)
        assert not at.exception
        labels = [t.label for t in at.tabs]
        assert labels == ["Your data", "What's in it", "Connections",
                          "Numbers", "Answer"]

    def test_the_headline_numbers_are_there(self, shop_db):
        at = app_on(shop_db)
        labels = [m.label for m in at.metric]
        assert "Tables" in labels
        assert "Kinds of thing" in labels
        assert "Things" in labels

    def test_the_discovered_classes_are_shown(self, shop_db):
        """Assert the CONTENT, not the widget.

        Tables render as st.dataframe where pandas works and as markdown
        where it is blocked, so pinning the element type would make this
        test pass or fail on machine policy rather than on the app being
        right.
        """
        at = app_on(shop_db)
        assert not at.exception
        shown = " ".join(
            [str(d.value) for d in at.dataframe]
            + [m.value for m in at.markdown])
        assert "Customer" in shown and "Order" in shown
        assert "customers" in shown      # the table it came from


class TestItFailsPolitely:
    """A broken source must produce a sentence, never a traceback. This is
    the difference between a demo that survives a wrong path and one that
    ends the meeting."""

    def test_a_missing_path_shows_an_error_not_a_crash(self):
        at = app_on("does/not/exist.db")
        assert not at.exception
        assert at.error, "expected a friendly error message"
        assert "not found" in at.error[0].value.lower()

    def test_an_unreadable_file_type_is_explained(self, tmp_path):
        f = tmp_path / "notes.docx"
        f.write_text("x", encoding="utf-8")
        at = app_on(str(f))
        assert not at.exception
        assert at.error

    def test_an_empty_source_box_asks_for_one(self):
        at = app_on("")
        assert not at.exception
        assert at.info


class TestHonesty:
    """The point of the whole thing: a guess must be visible as a guess."""

    def test_a_csv_source_is_labelled_as_guessed(self, tmp_path):
        d = tmp_path / "csvshop"
        d.mkdir()
        (d / "customers.csv").write_text("customer_id,city\nc1,X\nc2,Y\n",
                                         encoding="utf-8")
        (d / "orders.csv").write_text(
            "order_id,customer_id\no1,c1\no2,c2\n", encoding="utf-8")
        at = app_on(str(d))
        assert not at.exception
        text = " ".join(i.value for i in at.info).lower()
        assert "guessed" in text

    def test_a_database_with_real_keys_is_not_called_a_guess(self, shop_db):
        """SQLite declares its foreign keys, so nothing here is a guess and
        the 'guessed links' warning must NOT appear."""
        at = app_on(shop_db)
        shown = " ".join(
            [str(d.value) for d in at.dataframe]
            + [m.value for m in at.markdown]
            + [i.value for i in at.info]).lower()
        assert "stated" in shown
        assert "were guessed from" not in shown
