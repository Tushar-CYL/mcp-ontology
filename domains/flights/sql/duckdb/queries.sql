-- Flights domain - the questions worth asking (DuckDB)
--
-- Defined ONCE, as macros, so the notebook, the API, the dashboard and the
-- agent all run the same SQL. Three consumers each writing their own version
-- of "how connected is this airport" is the problem this prevents.
--
-- Every one of these takes an `as_of`. The network on 3 January is not the
-- network on 24 January, and both answers are correct - that is the whole
-- reason the edges carry intervals.
--
-- NOTE: the parameter is `as_of`, never `at`. `at` is reserved (AT TIME ZONE)
-- and the parser error it produces does not mention the word.

-- --------------------------------------------------------- blast radius
-- If this airport closes, which airports lose a connection - directly, then
-- one hop further out, and so on? The generic walk lives in core.sql; this
-- names the domain's own relation so a caller never has to know it.
CREATE OR REPLACE MACRO blast_radius(airport, as_of, cap) AS TABLE (
    SELECT node AS affected_airport, hops
    FROM reach_from('Airport', airport, 'flies_to', as_of, cap)
    ORDER BY hops, affected_airport
);

-- ------------------------------------------------------------- neighbours
-- Direct connections only, with how much traffic and how late it ran.
CREATE OR REPLACE MACRO destinations(airport, as_of) AS TABLE (
    SELECT d.nkey        AS destination,
           e.tag         AS carrier,
           e.weight      AS flights,
           e.stat_p50    AS delay_p50,
           e.stat_p99    AS delay_p99
    FROM edges e
    JOIN nodes s ON s.id = e.src
    JOIN nodes d ON d.id = e.dst
    WHERE e.rel = rel_code('flies_to')
      AND s.class = class_code('Airport') AND s.nkey = airport
      AND valid_at(e.valid_from, e.valid_to, as_of)
    ORDER BY e.weight DESC
);

CREATE OR REPLACE MACRO arrivals(airport, as_of) AS TABLE (
    SELECT s.nkey AS origin, e.tag AS carrier, e.weight AS flights,
           e.stat_p50 AS delay_p50, e.stat_p99 AS delay_p99
    FROM edges e
    JOIN nodes s ON s.id = e.src
    JOIN nodes d ON d.id = e.dst
    WHERE e.rel = rel_code('flies_to')
      AND d.class = class_code('Airport') AND d.nkey = airport
      AND valid_at(e.valid_from, e.valid_to, as_of)
    ORDER BY e.weight DESC
);

-- ---------------------------------------------------------- choke points
-- Which airports sit on the most distinct routes. These are the least
-- survivable failures, and they are NOT the same as the busiest airports -
-- a hub with many unique connections matters more than one with many
-- flights on a few routes.
CREATE OR REPLACE MACRO choke_points(as_of, top_n) AS TABLE (
    SELECT n.nkey                        AS airport,
           count(DISTINCT e.dst)         AS destinations,
           count(DISTINCT e.tag)         AS carriers,
           sum(e.weight)                 AS flights
    FROM edges e
    JOIN nodes n ON n.id = e.src
    WHERE e.rel = rel_code('flies_to')
      AND valid_at(e.valid_from, e.valid_to, as_of)
    GROUP BY n.nkey
    ORDER BY destinations DESC, flights DESC
    LIMIT top_n
);

-- ------------------------------------------------------- aircraft history
-- Where one physical aeroplane has been, and who flew it. The flights
-- equivalent of "which machine was this container on at 03:05" - and the
-- reason flown_by is stored as intervals rather than one row per day.
CREATE OR REPLACE MACRO aircraft_history(tail) AS TABLE (
    SELECT al.nkey AS carrier, e.valid_from, e.valid_to,
           e.weight AS days_flown
    FROM edges e
    JOIN nodes ac ON ac.id = e.src
    JOIN nodes al ON al.id = e.dst
    WHERE e.rel = rel_code('flown_by')
      AND ac.class = class_code('Aircraft') AND ac.nkey = tail
    ORDER BY e.valid_from
);

-- --------------------------------------------------------------- carriers
-- Who flies from here, and how reliably. Joins the graph to the facts.
CREATE OR REPLACE MACRO who_flies(airport, as_of) AS TABLE (
    SELECT al.nkey                         AS carrier,
           any_value(al.props ->> 'name')  AS airline_name,
           sum(e.weight)                   AS flights,
           'measured'                      AS provenance
    FROM edges e
    JOIN nodes al ON al.id = e.src
    JOIN nodes ap ON ap.id = e.dst
    WHERE e.rel = rel_code('serves')
      AND ap.class = class_code('Airport') AND ap.nkey = airport
      AND valid_at(e.valid_from, e.valid_to, as_of)
    GROUP BY al.nkey
    ORDER BY flights DESC NULLS LAST
);

-- ----------------------------------------------------------- where is it
-- Airport -> city -> country, the one traversal that needs no timestamp
-- because geography does not move.
CREATE OR REPLACE MACRO locate(airport) AS TABLE (
    SELECT ap.nkey                        AS airport,
           ap.props ->> 'name'            AS name,
           ci.nkey                        AS city,
           co.nkey                        AS country,
           ap.props ->> 'lat'             AS latitude,
           ap.props ->> 'lon'             AS longitude
    FROM nodes ap
    LEFT JOIN edges e1 ON e1.src = ap.id AND e1.rel = rel_code('in_city')
    LEFT JOIN nodes ci ON ci.id = e1.dst
    LEFT JOIN edges e2 ON e2.src = ci.id AND e2.rel = rel_code('in_country')
    LEFT JOIN nodes co ON co.id = e2.dst
    WHERE ap.class = class_code('Airport') AND ap.nkey = airport
);
