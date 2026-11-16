"""Ask must join things a question names through things it does not name."""

from ontology.ask import _bridges


def view(*pairs):
    return {"links": [{"from_thing": a, "to_thing": b} for a, b in pairs]}


OLIST = view(("Review", "Order"), ("Item", "Order"), ("Item", "Seller"),
             ("Item", "Product"), ("Order", "Customer"), ("Payment", "Order"))


def test_review_and_seller_meet_through_order_and_item():
    assert sorted(_bridges(OLIST, ["Review", "Seller"])) == ["Item", "Order"]


def test_nothing_added_when_already_linked():
    assert _bridges(OLIST, ["Item", "Seller"]) == []


def test_three_named_things_get_one_shared_bridge():
    assert _bridges(OLIST, ["Review", "Payment", "Customer"]) == ["Order"]


def test_no_path_adds_nothing():
    v = view(("A", "B"), ("C", "D"))
    assert _bridges(v, ["A", "D"]) == []


def test_a_long_detour_is_not_taken():
    chain = view(("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "F"))
    assert _bridges(chain, ["A", "F"]) == []          # 4 bridges > MAX_BRIDGES
    assert sorted(_bridges(chain, ["A", "D"])) == ["B", "C"]


def test_unlinked_or_single_things_need_nothing():
    assert _bridges(OLIST, ["Review"]) == []
    assert _bridges(OLIST, ["Review", "Nowhere"]) == []
    assert _bridges({"links": []}, ["A", "B"]) == []
