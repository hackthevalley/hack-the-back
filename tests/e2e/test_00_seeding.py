import json
from datetime import datetime

from .conftest import ROOT, db_query, restart_api


EXPECTED_MEALS = {
    ("friday", "dinner", False),
    ("saturday", "breakfast", False),
    ("saturday", "lunch", False),
    ("saturday", "dinner", False),
    ("sunday", "breakfast", False),
    ("sunday", "lunch", False),
}


def test_seed_contract_matches_source_data(client, admin_headers):
    expected_questions = json.loads(
        (ROOT / "app/data/form_questions.json").read_text(encoding="utf-8")
    )
    actual_questions = client.get("/api/forms/questions")
    assert actual_questions.status_code == 200
    actual_questions = actual_questions.json()

    assert len(actual_questions) == len(expected_questions)
    for order, (actual, expected) in enumerate(
        zip(actual_questions, expected_questions, strict=True)
    ):
        assert actual["question_order"] == order
        assert actual["label"] == expected["label"]
        assert actual["required"] == expected["required"]

    meals = client.get("/api/meals", headers=admin_headers)
    assert meals.status_code == 200
    actual_meals = {
        (meal["day"], meal["meal_type"], meal["is_active"])
        for meal in meals.json()
    }
    assert actual_meals == EXPECTED_MEALS

    form = client.get("/api/forms/registration-timerange")
    assert form.status_code == 200
    assert datetime.fromisoformat(form.json()["start_at"]).year == 2020
    assert datetime.fromisoformat(form.json()["end_at"]).year == 2099
    assert db_query("SELECT count(*) FROM forms_form") == ["1"]


def test_seeding_is_idempotent_and_repairs_missing_rows(client, admin_headers):
    question_count = int(db_query("SELECT count(*) FROM forms_question")[0])
    assert question_count > 0
    assert db_query("SELECT count(*) FROM meal") == ["6"]
    assert db_query("SELECT count(*) FROM forms_form") == ["1"]

    restart_api()
    assert db_query("SELECT count(*) FROM forms_question") == [str(question_count)]
    assert db_query("SELECT count(*) FROM meal") == ["6"]
    assert db_query("SELECT count(*) FROM forms_form") == ["1"]

    db_query("DELETE FROM forms_question WHERE question_order = 0")
    db_query("DELETE FROM meal WHERE day = 'FRIDAY' AND meal_type = 'DINNER'")
    db_query("DELETE FROM forms_form")
    assert db_query("SELECT count(*) FROM forms_question") == [str(question_count - 1)]
    assert db_query("SELECT count(*) FROM meal") == ["5"]
    assert db_query("SELECT count(*) FROM forms_form") == ["0"]

    restart_api()
    assert db_query("SELECT count(*) FROM forms_question") == [str(question_count)]
    assert db_query("SELECT count(*) FROM meal") == ["6"]
    assert db_query("SELECT count(*) FROM forms_form") == ["1"]

    labels = db_query(
        "SELECT label FROM forms_question GROUP BY label HAVING count(*) > 1"
    )
    meals = db_query(
        "SELECT day, meal_type FROM meal GROUP BY day, meal_type HAVING count(*) > 1"
    )
    assert labels == []
    assert meals == []

    # The repaired seed data is usable through the public API, not just present in SQL.
    assert len(client.get("/api/forms/questions").json()) == question_count
    assert len(client.get("/api/meals", headers=admin_headers).json()) == 6
