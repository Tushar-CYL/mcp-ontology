"""Chat routes explain/rules to catalogue ask; data questions go through context."""

from ontology.ask import intent


def test_intent_keeps_explain_and_rules():
    assert intent("What is a Customer Order") == "explain"
    assert intent("Tell me about Customer") == "explain"
    assert intent("What business rules do we have?") == "rules"


def test_intent_sends_counts_to_query():
    assert intent("How many customers are there?") == "query"
    assert intent("Show the top sellers by revenue") == "query"
