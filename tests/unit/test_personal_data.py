"""Which ontology fields hold personal data (shown on screen, in Excel and to agents)."""

import pytest

from ontology.simple import personal_kind


@pytest.mark.parametrize("name, kind", [
    ("email", "Email"), ("customer_email", "Email"), ("Email Address", "Email"),
    ("phone_number", "Phone number"), ("contact phone", "Phone number"),
    ("ssn", "Government id"), ("passport_no", "Government id"),
    ("credit_card_number", "Payment card"), ("iban", "Payment card"),
    ("date_of_birth", "Date of birth"), ("DOB", "Date of birth"),
    ("client_ip", "IP address"), ("street_address", "Home address"),
])
def test_personal_columns_are_named(name, kind):
    assert personal_kind(name) == kind


@pytest.mark.parametrize("name", [
    "email_verified", "phone_brand", "mobile", "zip", "ship_date", "tip",
    "customer_name", "company", "order_id", "description", "", None,
])
def test_ordinary_columns_are_not_flagged(name):
    assert personal_kind(name) is None


def test_the_label_catches_a_vaguely_named_column():
    assert personal_kind("contact", "Email address") == "Email"
