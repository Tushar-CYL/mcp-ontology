"""A knowledge-graph source (CSKG folder: entities + relations + triples) gets
a real ontology: types from the relations, links between types, a hierarchy -
not "one Entity thing with two fields"."""

from __future__ import annotations

import json

from api.service import MiddleLayer
from ontology import graph_onto, simple


def write_cskg(folder, n=60):
    folder.mkdir(parents=True)
    methods = [f"method_{i}" for i in range(n)]
    tasks = [f"task_{i}" for i in range(n // 3)]
    metrics = [f"metric_{i}" for i in range(n // 4)]
    names = methods + tasks + metrics + ["orphan_thing"]
    ids = {name: i for i, name in enumerate(names)}
    (folder / "entities.txt").write_text(
        "".join(f"{i}\t{name}\n" for name, i in ids.items()), encoding="utf-8")
    relations = ["usesMethod", "solvesTask", "improvesMetric", "skos:broader", "based-onMethod"]
    (folder / "relations.txt").write_text(
        "".join(f"{i}\t{r}\n" for i, r in enumerate(relations)), encoding="utf-8")
    triples = []
    for i, m in enumerate(methods):
        triples.append((ids[m], 0, ids[methods[(i + 1) % n]]))          # Method uses Method
        triples.append((ids[m], 1, ids[tasks[i % len(tasks)]]))          # Method solves Task
        triples.append((ids[m], 4, ids[methods[(i + 7) % n]]))           # based on Method
    for i, t in enumerate(tasks):
        triples.append((ids[t], 2, ids[metrics[i % len(metrics)]]))       # Task improves Metric
    for i in range(1, 10):
        triples.append((ids[methods[i]], 3, ids[methods[0]]))            # is a kind of
    lines = "".join(f"{h}\t{r}\t{t}\n" for h, r, t in triples)
    (folder / "triples.txt").write_text(lines, encoding="utf-8")
    (folder / "train.txt").write_text(lines, encoding="utf-8")
    return folder


def test_relation_names_split_into_verb_and_type():
    assert graph_onto.split_relation("usesMethod") == ("uses", "Method")
    assert graph_onto.split_relation("based-onMethod") == ("based on", "Method")
    assert graph_onto.split_relation("usesOtherEntity") == ("uses", "OtherEntity")
    assert graph_onto.split_relation("http://x.org/ns#interacts-withTask") == \
        ("interacts with", "Task")
    assert graph_onto.split_relation("related") == ("related", None)
    assert graph_onto.hierarchy_kind("skos:broader") is False
    assert graph_onto.hierarchy_kind("rdfs:subClassOf") is False
    assert graph_onto.hierarchy_kind("narrower") is True
    assert graph_onto.hierarchy_kind("usesMethod") is None


class TypeAI:
    mock = False
    model = "fake"

    def __init__(self):
        self.calls = 0

    def complete(self, messages, max_tokens=0):
        self.calls += 1
        facts = json.loads(messages[-1]["content"])
        return json.dumps({"types": [
            {"type": t["type"], "name": t["type"] + "s" if t["type"] != "Unclassified"
             else "Other", "description": f"A {t['type'].lower()} such as "
             f"{t['sample_names'][0] if t['sample_names'] else 'x'}."}
            for t in facts["types"]]})


def test_knowledge_graph_gets_types_links_and_hierarchy(tmp_path):
    layer = MiddleLayer(str(tmp_path / "kg.duckdb"))
    layer.add_source(str(write_cskg(tmp_path / "cskg")), source="kg")
    assert graph_onto.is_graph_source(layer, "kg")
    oid = simple.create_and_build(layer, "Science KG", ["kg"], client=TypeAI())["ontology"]
    v = simple.view(layer.graph, oid)
    things = {t["key"]: t for t in v["things"]}
    assert {"Method", "Task", "Metric", "Unclassified"} <= set(things)
    # Names come from the data (stable); the AI writes the description.
    assert things["Method"]["name"] == "Method" and things["Method"]["by"] == "ai"
    assert things["Method"]["description"].startswith("A method such as")
    assert things["Method"]["records"] == 60 and things["Task"]["records"] == 20
    assert things["Unclassified"]["records"] == 1                   # orphan_thing
    assert things["Unclassified"]["name"] == "Not yet typed"
    labels = {l["label"] for l in v["links"]}
    assert "Method uses Method" in labels
    assert "Method solves Task" in labels
    assert "Task improves Metric" in labels
    assert "Method based on Method" in labels
    assert "Method is a kind of Method" in labels
    solves = next(l for l in v["links"] if l["verb"] == "solves")
    # triples.txt holds every triple; train.txt repeats them and is not counted.
    assert solves["match"] == 1.0 and solves["triples"] == 60
    assert any("100% of typed objects are Task" in p for p in solves["proof"])
    fields = {f["column"] for f in things["Method"]["fields"]}
    assert fields == {"id", "label"}
    name = next(f for f in things["Method"]["fields"] if f["column"] == "label")
    assert "method" in name["proof"]
    # No leftover "Entity" thing from the table reading of the same source.
    assert "Entity" not in things
    assert v["version"] == 1
    # Excel and agents read the same thing.
    data = simple.for_excel(layer.graph, oid)
    assert {r["Thing"] for r in data["things"]} >= {"Method", "Task", "Metric"}
    assert any(r["Meaning"] == "Method solves Task" for r in data["links"])


def test_without_ai_names_come_from_the_relations(tmp_path):
    layer = MiddleLayer(str(tmp_path / "kg.duckdb"))
    layer.add_source(str(write_cskg(tmp_path / "cskg")), source="kg")
    oid = simple.create_and_build(layer, "KG", ["kg"])["ontology"]
    v = simple.view(layer.graph, oid)
    assert {"Method", "Task", "Metric"} <= {t["name"] for t in v["things"]}
    assert all(t["description"] for t in v["things"])
    assert v["summary"]["links"] == 5


def test_several_graph_sources_merge_into_one_ontology(tmp_path):
    """Three benchmark folders in one ontology: one Method, not three; one
    'Method uses Method' link with the triples added up; a rebuild does not
    add them again."""
    layer = MiddleLayer(str(tmp_path / "kg.duckdb"))
    layer.add_source(str(write_cskg(tmp_path / "a")), source="a")
    layer.add_source(str(write_cskg(tmp_path / "b", n=120)), source="b")
    oid = simple.create_and_build(layer, "Both", ["a", "b"])["ontology"]

    def check():
        v = simple.view(layer.graph, oid)
        names = [t["name"] for t in v["things"]]
        assert names.count("Method") == 1
        method = next(t for t in v["things"] if t["name"] == "Method")
        assert method["records"] == 60 + 120
        assert sorted(method["tables"]) == ["a.entities#Method", "b.entities#Method"]
        assert len(method["fields"]) == 2                         # one ID, one Name
        uses = [l for l in v["links"] if l["label"] == "Method uses Method"]
        assert len(uses) == 1 and uses[0]["triples"] == 60 + 120
        assert "across 2 sources" in uses[0]["proof"][0]
        assert v["summary"]["links"] == 5
    check()
    simple.build(layer, oid)
    check()


def test_rdf_with_instance_of_and_labelled_relations(tmp_path):
    """The gptkb shape: relations are opaque ids with a label in the data
    (prop/P0 = "instanceOf", prop/P40 = "locatedIn") and types come from
    instanceOf pointing at labelled concepts - not rdf:type."""
    lab = "<http://www.w3.org/2000/01/rdf-schema#label>"
    kb, prop, con = "https://kb.org/entity/", "https://kb.org/prop/", "https://kb.org/concept/"
    lines = [f'<{prop}P0> {lab} "instanceOf" .', f'<{prop}P40> {lab} "locatedIn" .',
             f'<{prop}P22> {lab} "notableFor" .',
             f'<{con}C0> {lab} "person" .', f'<{con}C1> {lab} "city" .', f'<{con}C2> {lab} "award" .']
    for i in range(30):
        lines += [f'<{kb}P{i}> {lab} "Person {i}" .', f"<{kb}P{i}> <{prop}P0> <{con}C0> .",
                  f"<{kb}P{i}> <{prop}P40> <{kb}T{i % 5}> .", f"<{kb}P{i}> <{prop}P22> <{kb}A{i % 3}> ."]
    for k in range(5):
        lines += [f'<{kb}T{k}> {lab} "Town {k}" .', f"<{kb}T{k}> <{prop}P0> <{con}C1> ."]
    for k in range(3):
        lines += [f'<{kb}A{k}> {lab} "Prize {k}" .', f"<{kb}A{k}> <{prop}P0> <{con}C2> ."]
    nt = tmp_path / "kb.nt"
    nt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    layer = MiddleLayer(str(tmp_path / "kb.duckdb"))
    layer.add_source(str(nt), source="kb")
    found = graph_onto.analyse(layer, "kb")
    assert found["method"] == "instance_of"
    assert {t: found["types"][t]["entities"] for t in found["types"]} == \
        {"person": 30, "city": 5, "award": 3}        # concepts are types, not "untyped"
    oid = simple.create_and_build(layer, "KB", ["kb"])["ontology"]
    v = simple.view(layer.graph, oid)
    assert {t["name"] for t in v["things"]} == {"Person", "City", "Award"}
    labels = {l["label"] for l in v["links"]}
    assert labels == {"Person located in City", "Person notable for Award"}
    assert all("P40" not in l["label"] and "P0" not in l["label"] for l in v["links"])


def test_only_the_most_frequent_relations_are_listed(tmp_path, monkeypatch):
    monkeypatch.setattr(graph_onto, "MAX_LINKS", 2)
    layer = MiddleLayer(str(tmp_path / "kg.duckdb"))
    layer.add_source(str(write_cskg(tmp_path / "cskg")), source="kg")
    oid = simple.create_and_build(layer, "KG", ["kg"])["ontology"]
    v = simple.view(layer.graph, oid)
    assert v["summary"]["links"] == 2
    assert {l["verb"] for l in v["links"]} <= {"uses", "solves", "based on"}   # 60 triples each
    assert v["built"]["hidden_relations"] == 3
    assert v["built"]["hidden_triples"] == 60 + 20 + 9


def test_untyped_things_inherit_the_type_of_their_parent(tmp_path):
    """sub_method_* appear only in 'is a kind of' links to typed methods."""
    folder = write_cskg(tmp_path / "cskg")
    ents = (folder / "entities.txt").read_text(encoding="utf-8").splitlines()
    start = len(ents)
    tab, nl = chr(9), chr(10)
    extra = [f"{start + i}{tab}sub_method_{i}" for i in range(5)]
    (folder / "entities.txt").write_text(nl.join(ents + extra) + nl, encoding="utf-8")
    more = "".join(f"{start + i}{tab}3{tab}1{nl}" for i in range(5))   # broader -> method_1
    with (folder / "triples.txt").open("a", encoding="utf-8") as f:
        f.write(more)
    layer = MiddleLayer(str(tmp_path / "kg.duckdb"))
    layer.add_source(str(folder), source="kg")
    found = graph_onto.analyse(layer, "kg")
    assert found["inherited"] == 5
    assert found["types"]["Method"]["entities"] == 65
    assert found["types"]["Unclassified"]["entities"] == 1
