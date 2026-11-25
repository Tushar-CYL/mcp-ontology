"""Ask chooses explain / rules / query — SQL only for query."""

from ontology.ask import intent


def test_explain_about_a_term():
    assert intent("tell me about geolocation") == "explain"
    assert intent("What is Customer Order?") == "explain"
    assert intent("describe the product tables") == "explain"


def test_rules_questions():
    assert intent("what business rules do we have?") == "rules"
    assert intent("Which rules break on orders?") == "rules"
    assert intent("list our business rules") == "rules"


def test_query_needs_numbers():
    assert intent("What is the total Payment Amount by Order Status?") == "query"
    assert intent("how many Customer Orders are canceled?") == "query"
    assert intent("average review score by seller state") == "query"


def test_short_name_is_explain():
    assert intent("geolocation") == "explain"
