-- Flights domain - staging -> knowledge graph (DuckDB)
--
-- Two independent sources that do not fully agree, which is the point:
--
--   OpenFlights  the global network. Rich (name, city, country, lat/lon)
--                but a SNAPSHOT with no dates at all.
--   BTS          every US commercial flight, with a date, a delay and a
--                cancellation flag. This is what makes the graph rewindable.
--
-- So: OpenFlights describes the things, BTS says what happened between them.
-- Where the two disagree about which airports exist, the disagreement is
-- recorded in node_alias rather than resolved by picking a winner.

DELETE FROM edges;
DELETE FROM node_alias;
DELETE FROM nodes;

-- ------------------------------------------------------------- 0. cleaning
-- OpenFlights writes a literal \N - two characters - for "no value", and
-- quotes inconsistently. A valid IATA code is exactly three letters; that
-- test is cheap and catches both \N and the empty string.
CREATE OR REPLACE MACRO ok_iata(s) AS
    (s IS NOT NULL AND regexp_matches(upper(trim(s)), '^[A-Z]{3}$'));

CREATE OR REPLACE TABLE clean_airports AS
SELECT upper(trim(iata))                       AS iata,
       nullif(trim(name), '')                  AS name,
       nullif(trim(city), '')                  AS city,
       nullif(trim(country), '')               AS country,
       TRY_CAST(latitude  AS DOUBLE)           AS lat,
       TRY_CAST(longitude AS DOUBLE)           AS lon,
       TRY_CAST(altitude  AS INTEGER)          AS altitude,
       nullif(trim(tz_name), '')               AS timezone
FROM stg_airports
WHERE ok_iata(iata)
QUALIFY row_number() OVER (PARTITION BY upper(trim(iata))
                           ORDER BY openflights_id) = 1;

CREATE OR REPLACE TABLE clean_airlines AS
SELECT upper(trim(iata))                       AS carrier,
       nullif(trim(name), '')                  AS name,
       nullif(trim(callsign), '')              AS callsign,
       (upper(trim(active)) = 'Y')             AS active,
       nullif(trim(country), '')               AS country
FROM stg_airlines
WHERE iata IS NOT NULL
  AND regexp_matches(upper(trim(iata)), '^[A-Z0-9]{2}$')
QUALIFY row_number() OVER (PARTITION BY upper(trim(iata))
                           -- An active carrier beats a defunct one holding
                           -- the same reassigned code.
                           ORDER BY (upper(trim(active)) = 'Y') DESC,
                                    openflights_id) = 1;

-- One typed row per flight. Cancelled flights carry EMPTY delay fields;
-- TRY_CAST turns those into NULL rather than 0, which matters because a
-- zero would read as "on time" and drag every average towards punctual.
CREATE OR REPLACE TABLE clean_flights AS
SELECT CAST(flight_date AS DATE)               AS fdate,
       upper(trim(carrier))                    AS carrier,
       nullif(trim(flight_number), '')         AS flight_number,
       nullif(upper(trim(tail_number)), '')    AS tail_number,
       upper(trim(origin))                     AS origin,
       upper(trim(dest))                       AS dest,
       TRY_CAST(dep_delay AS DOUBLE)           AS dep_delay,
       TRY_CAST(arr_delay AS DOUBLE)           AS arr_delay,
       coalesce(TRY_CAST(cancelled AS DOUBLE), 0) >= 0.5  AS cancelled,
       nullif(trim(cancel_code), '')           AS cancel_code,
       coalesce(TRY_CAST(diverted AS DOUBLE), 0) >= 0.5   AS diverted,
       TRY_CAST(air_time AS DOUBLE)            AS air_time,
       TRY_CAST(distance AS DOUBLE)            AS distance
FROM stg_flights
WHERE flight_date IS NOT NULL
  AND ok_iata(origin) AND ok_iata(dest);

-- --------------------------------------------------------------- 1. nodes
-- Airports from BOTH sources. OpenFlights is authoritative for the
-- descriptive fields, but BTS flies to codes OpenFlights has never heard of,
-- and an edge pointing at a node that does not exist is the exact defect
-- route_endpoints_exist is there to catch. So every code either source names
-- becomes a node, and which source it came from is recorded below.
CREATE OR REPLACE TABLE all_airports AS
SELECT iata FROM clean_airports
UNION
SELECT origin FROM clean_flights
UNION
SELECT dest FROM clean_flights;

INSERT INTO nodes (id, class, nkey, props)
SELECT node_id(class_code('Airport'), a.iata),
       class_code('Airport'),
       a.iata,
       to_json({'name': c.name, 'city': c.city, 'country': c.country,
                'lat': c.lat, 'lon': c.lon, 'altitude': c.altitude,
                'timezone': c.timezone,
                'source': CASE WHEN c.iata IS NULL THEN 'bts' ELSE 'openflights' END})
FROM all_airports a
LEFT JOIN clean_airports c ON c.iata = a.iata;

-- Auditable and reversible: these are the airports BTS flies to that
-- OpenFlights does not list. Not an error - two independent sources - but
-- it must be visible rather than inferred later from a missing name.
INSERT INTO node_alias (alias, class, node_id, reason)
SELECT a.iata, class_code('Airport'),
       node_id(class_code('Airport'), a.iata), 'bts_only'
FROM all_airports a
LEFT JOIN clean_airports c ON c.iata = a.iata
WHERE c.iata IS NULL;

INSERT INTO nodes (id, class, nkey, props)
SELECT node_id(class_code('Airline'), x.carrier), class_code('Airline'),
       x.carrier,
       to_json({'name': l.name, 'callsign': l.callsign,
                'active': l.active, 'country': l.country})
FROM (SELECT carrier FROM clean_airlines
      UNION
      SELECT carrier FROM clean_flights WHERE carrier IS NOT NULL) x
LEFT JOIN clean_airlines l ON l.carrier = x.carrier;

INSERT INTO nodes (id, class, nkey)
SELECT DISTINCT node_id(class_code('City'), city), class_code('City'), city
FROM clean_airports WHERE city IS NOT NULL;

INSERT INTO nodes (id, class, nkey)
SELECT DISTINCT node_id(class_code('Country'), country),
       class_code('Country'), country
FROM (SELECT country FROM clean_airports WHERE country IS NOT NULL
      UNION
      SELECT country FROM clean_airlines WHERE country IS NOT NULL);

-- One physical aeroplane. Tail numbers are reused over decades, but not
-- within one month, so this is safe at this slice and would need revisiting
-- at multi-year scale.
INSERT INTO nodes (id, class, nkey)
SELECT DISTINCT node_id(class_code('Aircraft'), tail_number),
       class_code('Aircraft'), tail_number
FROM clean_flights WHERE tail_number IS NOT NULL;

-- --------------------------------------------------------------- 2. edges
-- flies_to: THE edge, aggregated per day. Daily is the right grain because
-- it is the unit a human reasons in ("what was flying on the 3rd?") and
-- because a 31-day month then gives 31 genuinely different networks to
-- travel between.
--
-- Cancelled flights are counted but excluded from the delay percentiles: a
-- cancellation is not a slow flight, and folding the two together would
-- make a badly disrupted route look merely sluggish.
INSERT INTO edges (src, rel, dst, valid_from, valid_to,
                   weight, stat_p50, stat_p99, tag)
SELECT node_id(class_code('Airport'), origin),
       rel_code('flies_to'),
       node_id(class_code('Airport'), dest),
       CAST(fdate AS TIMESTAMP),
       CAST(fdate + INTERVAL 1 DAY AS TIMESTAMP),
       count(*),
       quantile_cont(arr_delay, 0.5) FILTER (WHERE NOT cancelled),
       quantile_cont(arr_delay, 0.99) FILTER (WHERE NOT cancelled),
       carrier
FROM clean_flights
WHERE origin <> dest                      -- see the no_self_route rule
GROUP BY origin, dest, fdate, carrier;

-- serves: which carrier operated from which airport, per day. Flown, not
-- scheduled - this comes from BTS, so it is what actually happened.
INSERT INTO edges (src, rel, dst, valid_from, valid_to, weight)
SELECT node_id(class_code('Airline'), carrier),
       rel_code('serves'),
       node_id(class_code('Airport'), origin),
       CAST(fdate AS TIMESTAMP),
       CAST(fdate + INTERVAL 1 DAY AS TIMESTAMP),
       count(*)
FROM clean_flights
WHERE carrier IS NOT NULL
GROUP BY carrier, origin, fdate;

-- The global scheduled network from routes.dat contributes `serves` for
-- carriers and airports BTS never sees, with an open-ended interval because
-- the file carries no dates. Open-ended is the honest encoding of "we know
-- this is true, we do not know when it started".
--
-- Join on the natural KEY, never on the computed id. Written as
--     JOIN nodes n ON n.id = node_id(class_code('Airline'), r.airline_iata)
-- this statement did not finish in ten minutes: the join condition is an
-- expression, so DuckDB cannot hash-join it and degrades to a nested loop -
-- 67,663 routes x ~11,000 nodes, hashing MD5 at every comparison. Matching
-- on nkey, a plain VARCHAR column, makes it a normal hash join and the same
-- statement runs in well under a second.
INSERT INTO edges (src, rel, dst, valid_from, valid_to, weight)
SELECT node_id(class_code('Airline'), r.airline),
       rel_code('serves'),
       node_id(class_code('Airport'), r.airport),
       TIMESTAMP '1970-01-01', NULL, count(*)
FROM (SELECT upper(trim(airline_iata)) AS airline,
             upper(trim(src_iata))     AS airport
      FROM stg_routes
      WHERE ok_iata(src_iata)
        AND regexp_matches(upper(trim(airline_iata)), '^[A-Z0-9]{2}$')) r
JOIN nodes al ON al.class = class_code('Airline') AND al.nkey = r.airline
JOIN nodes ap ON ap.class = class_code('Airport') AND ap.nkey = r.airport
GROUP BY r.airline, r.airport;

INSERT INTO edges (src, rel, dst, valid_from, valid_to)
SELECT node_id(class_code('Airport'), iata), rel_code('in_city'),
       node_id(class_code('City'), city),
       TIMESTAMP '1970-01-01', NULL
FROM clean_airports WHERE city IS NOT NULL;

INSERT INTO edges (src, rel, dst, valid_from, valid_to)
SELECT DISTINCT node_id(class_code('City'), city), rel_code('in_country'),
       node_id(class_code('Country'), country),
       TIMESTAMP '1970-01-01', NULL
FROM clean_airports WHERE city IS NOT NULL AND country IS NOT NULL;

INSERT INTO edges (src, rel, dst, valid_from, valid_to)
SELECT node_id(class_code('Airline'), carrier), rel_code('based_in'),
       node_id(class_code('Country'), country),
       TIMESTAMP '1970-01-01', NULL
FROM clean_airlines WHERE country IS NOT NULL;

-- flown_by: which carrier operated this airframe, as INTERVALS rather than
-- one row per day. Same gaps-and-islands method the other domain uses for
-- container placement: a change of carrier, or a gap of more than 3 days,
-- closes the interval. Collapsing 31 daily rows into one interval is what
-- makes "who was flying N104NN on the 14th?" a range lookup.
CREATE OR REPLACE TABLE ac_day AS
SELECT DISTINCT tail_number, carrier, fdate
FROM clean_flights
WHERE tail_number IS NOT NULL AND carrier IS NOT NULL;

INSERT INTO edges (src, rel, dst, valid_from, valid_to, weight)
WITH marked AS (
    SELECT tail_number, carrier, fdate,
           CASE WHEN lag(carrier) OVER w IS DISTINCT FROM carrier
                  OR date_diff('day', lag(fdate) OVER w, fdate) > 3
                THEN 1 ELSE 0 END AS new_island
    FROM ac_day
    WINDOW w AS (PARTITION BY tail_number ORDER BY fdate)
),
islands AS (
    SELECT tail_number, carrier, fdate,
           sum(new_island) OVER (PARTITION BY tail_number
                                 ORDER BY fdate
                                 ROWS UNBOUNDED PRECEDING) AS island
    FROM marked
)
SELECT node_id(class_code('Aircraft'), tail_number),
       rel_code('flown_by'),
       node_id(class_code('Airline'), carrier),
       CAST(min(fdate) AS TIMESTAMP),
       CAST(max(fdate) + INTERVAL 1 DAY AS TIMESTAMP),
       count(*)
FROM islands
GROUP BY tail_number, carrier, island;
