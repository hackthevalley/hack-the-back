import json
from datetime import datetime

from alembic.script import ScriptDirectory

from .conftest import ROOT, db_query


EXPECTED_MEALS = {
    ("friday", "dinner", False),
    ("saturday", "breakfast", False),
    ("saturday", "lunch", False),
    ("saturday", "dinner", False),
    ("sunday", "breakfast", False),
    ("sunday", "lunch", False),
}


def test_seed_contract_matches_source_data(client, admin_headers):
    expected_head = ScriptDirectory(str(ROOT / "alembic")).get_current_head()
    assert expected_head is not None
    assert db_query("SELECT version_num FROM alembic_version") == [expected_head]
    expected_questions = json.loads(
        (ROOT / "app/data/form_questions.json").read_text(encoding="utf-8")
    )
    expected_by_label = {question["label"]: question for question in expected_questions}
    assert expected_by_label["Avatar"]["required"] is True
    assert expected_by_label["Accessory"]["required"] is True
    assert expected_by_label["Devpost"]["required"] is False

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
        (meal["day"], meal["meal_type"], meal["is_active"]) for meal in meals.json()
    }
    assert actual_meals == EXPECTED_MEALS

    form = client.get("/api/forms/registration-timerange")
    assert form.status_code == 200
    assert datetime.fromisoformat(form.json()["start_at"]).year == 2020
    assert datetime.fromisoformat(form.json()["end_at"]).year == 2099
    assert form.json()["rsvp_due_date"] == "2099-01-01"
    assert db_query("SELECT count(*) FROM forms_form") == ["1"]
