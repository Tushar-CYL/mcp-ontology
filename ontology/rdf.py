"""RDF and other graph-shaped sources.

A `.nt` file is 4 GB of one triple per line. Loading it into Python would be a
mistake; DuckDB can read it as one line-column and the regexes below turn it
into two relational tables without copying the file:

    entities(id, label, type)      one row per subject/IRI object
    links(source, predicate, target)  one row per object property

`links` declares both foreign keys to `entities`, so the normal discovery and
build pipeline turns it into Entity nodes and typed links — no special build
code, no per-file mapping.

.ttl / .rdf / .jsonld need an RDF parser; rdflib is used when installed, with a
clear message otherwise. `.nq` is read like `.nt` (the graph term is ignored).
"""

from __future__ import annotations

from pathlib import Path

from ontology.schema import Column, ForeignKey, Table

RDF_TYPES = {".nt", ".nq", ".ttl", ".rdf", ".jsonld", ".trig"}


def is_rdf(path: str | Path) -> bool:
    return Path(path).suffix.lower() in RDF_TYPES


def _escape(value: str) -> str:
    return str(value).replace("'", "''")


def _lines(path: Path) -> str:
    """One VARCHAR column, one row per line, via an impossible delimiter."""
    return (
        "read_csv('" + _escape(str(path)) + "', delim=chr(1), header=false, "
        "quote='', escape='', columns={'line': 'VARCHAR'})"
    )


def triples_sql(path: Path) -> str:
    """The N-Triples/N-Quads shape: subject, predicate, object, is_iri."""
    return f"""
    SELECT
      regexp_extract(line, '^<([^>]*)>', 1) AS subject,
      regexp_extract(line, '^<[^>]*>[ \\t]+<([^>]*)>', 1) AS predicate,
      CASE WHEN regexp_matches(
                line, '^<[^>]*>[ \\t]+<[^>]*>[ \\t]+<')
           THEN regexp_extract(
                line, '^<[^>]*>[ \\t]+<[^>]*>[ \\t]+<([^>]*)>', 1)
           ELSE regexp_extract(line, '"(.*)"', 1) END AS object,
      regexp_matches(line, '^<[^>]*>[ \\t]+<[^>]*>[ \\t]+<') AS is_iri
    FROM {_lines(path)}
    WHERE line LIKE '<%'
    """


def _entities_sql(path: Path) -> str:
    triples = triples_sql(path)
    return f"""
    WITH t AS ({triples}),
         ids AS (
           SELECT subject AS id FROM t WHERE subject <> ''
           UNION
           SELECT object AS id FROM t WHERE is_iri AND object <> ''
         )
    SELECT i.id AS id,
      max(CASE WHEN t.predicate LIKE '%#label'
                 OR t.predicate LIKE '%/label'
                 OR t.predicate LIKE '%label' THEN t.object END) AS label,
      max(CASE WHEN t.predicate LIKE '%#type'
                 OR t.predicate LIKE '%/type'
                 OR t.predicate LIKE '%type' THEN
             regexp_extract(t.object, '([^/#]+)$', 1) END) AS type
    FROM ids i LEFT JOIN t ON t.subject = i.id
    WHERE i.id <> ''
    GROUP BY i.id
    """


def _links_sql(path: Path) -> str:
    triples = triples_sql(path)
    return f"""
    SELECT subject AS source,
           regexp_extract(predicate, '([^/#]+)$', 1) AS predicate,
           object AS target
    FROM ({triples})
    WHERE is_iri AND subject <> '' AND object <> ''
      AND predicate NOT LIKE '%#label'
      AND predicate NOT LIKE '%/label'
      AND predicate NOT LIKE '%#type'
      AND predicate NOT LIKE '%/type'
    """


def tables_for(path: str | Path, prefix: str = "") -> tuple[list[Table], dict]:
    """Two tables plus the SQL readers, with keys declared.

    A prefix is used when a folder mixes RDF with other files, so the class
    names stay distinguishable. No row count is computed here: counting a 4 GB
    file once per stage is already enough.
    """
    path = Path(path)
    if path.suffix.lower() in {".ttl", ".rdf", ".jsonld", ".trig"}:
        return _rdflib_tables(path, prefix)
    name = f"{prefix}_" if prefix else ""
    entities = f"{name}entities"
    links = f"{name}links"
    tables = [
        Table(
            name=entities,
            columns=[Column("id", "VARCHAR", nullable=False),
                     Column("label", "VARCHAR"),
                     Column("type", "VARCHAR")],
            primary_key=["id"],
            foreign_keys=[],
            row_count=None,
        ),
        Table(
            name=links,
            columns=[Column("source", "VARCHAR"),
                     Column("predicate", "VARCHAR"),
                     Column("target", "VARCHAR")],
            primary_key=[],
            foreign_keys=[ForeignKey("source", entities, "id"),
                          ForeignKey("target", entities, "id")],
            row_count=None,
        ),
    ]
    readers = {entities: _entities_sql(path), links: _links_sql(path)}
    return tables, readers


def _rdflib_tables(path: Path, prefix: str) -> tuple[list[Table], dict]:
    try:
        import rdflib  # noqa: F401
    except ImportError as exc:                    # pragma: no cover - env
        raise ValueError(
            f"reading {path.suffix} needs rdflib; run "
            f"`python -m pip install rdflib`, or convert the file to "
            f"N-Triples (.nt) with any RDF tool\n"
            f"({type(exc).__name__}: {exc})") from exc
    from rdflib import Graph, RDF

    graph = Graph()
    graph.parse(str(path))
    rows = []
    for subject, predicate, obj in graph:
        s = str(subject)
        p = str(predicate)
        is_iri = not isinstance(obj, rdflib.Literal)
        o = str(obj)
        rows.append((s, p, o, is_iri))
    # Materialise to a small CSV so the generic pipeline can read it.
    import csv
    import tempfile
    folder = Path(tempfile.mkdtemp(prefix="ml_rdf_"))
    csv_path = folder / "triples.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["subject", "predicate", "object", "is_iri"])
        writer.writerows(rows)
    name = f"{prefix}_" if prefix else ""
    entities = f"{name}entities"
    links = f"{name}links"
    reader = f"read_csv('{_escape(str(csv_path))}')"
    entities_sql = f"""
    WITH t AS (SELECT subject, predicate, object, is_iri FROM {reader}),
         ids AS (
           SELECT subject AS id FROM t WHERE subject <> ''
           UNION SELECT object AS id FROM t WHERE is_iri AND object <> ''
         )
    SELECT i.id AS id,
      max(CASE WHEN t.predicate LIKE '%label' THEN t.object END) AS label,
      max(CASE WHEN t.predicate LIKE '%type' THEN
          regexp_extract(t.object, '([^/#]+)$', 1) END) AS type
    FROM ids i LEFT JOIN t ON t.subject = i.id
    WHERE i.id <> '' GROUP BY i.id
    """
    links_sql = f"""
    SELECT subject AS source,
           regexp_extract(predicate, '([^/#]+)$', 1) AS predicate,
           object AS target
    FROM {reader}
    WHERE is_iri AND subject <> '' AND object <> ''
      AND predicate NOT LIKE '%label' AND predicate NOT LIKE '%type'
    """
    tables = [
        Table(name=entities,
              columns=[Column("id", "VARCHAR", nullable=False),
                       Column("label", "VARCHAR"), Column("type", "VARCHAR")],
              primary_key=["id"], foreign_keys=[], row_count=len(rows)),
        Table(name=links,
              columns=[Column("source", "VARCHAR"),
                       Column("predicate", "VARCHAR"),
                       Column("target", "VARCHAR")],
              primary_key=[],
              foreign_keys=[ForeignKey("source", entities, "id"),
                            ForeignKey("target", entities, "id")],
              row_count=None),
    ]
    return tables, {entities: entities_sql, links: links_sql}
