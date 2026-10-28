-- Executable shapes for the rules in ontology.yaml (flights, DuckDB).
--
-- Each shape is a SELECT returning exactly two columns:
--     row_key  VARCHAR - identifies the offending row
--     detail   JSON    - enough context to understand the violation
--
-- The validator wraps each one twice: once in count(*) for the exact number
-- of violations, once with a LIMIT for a stored sample.
--
-- Several of these are EXPECTED to fire. Two independent sources that do not
-- fully agree is the normal condition, not a fault, and measuring the
-- disagreement is the deliverable.


-- @rule: airport_has_iata
-- @stage: staging
-- OpenFlights writes a literal \N - two characters, not NULL - for airports
-- with no IATA code. They are real airports, mostly small strips and
-- heliports, but we key on IATA so they cannot enter the graph. Counting
-- them is the difference between "we excluded 1,900 rows deliberately" and
-- silently losing a quarter of the file.
SELECT coalesce(nullif(trim(name), ''), 'row ' || openflights_id) AS row_key,
       to_json({'iata': iata, 'name': name, 'country': country,
                'type': type}) AS detail
FROM stg_airports
WHERE NOT (iata IS NOT NULL
           AND regexp_matches(upper(trim(iata)), '^[A-Z]{3}$'));


-- @rule: coordinates_valid
-- @stage: staging
-- A latitude outside -90..90 is invisible until someone draws a map and an
-- airport lands in the wrong hemisphere.
SELECT upper(trim(iata)) AS row_key,
       to_json({'lat': latitude, 'lon': longitude, 'name': name}) AS detail
FROM stg_airports
WHERE iata IS NOT NULL
  AND regexp_matches(upper(trim(iata)), '^[A-Z]{3}$')
  AND (TRY_CAST(latitude AS DOUBLE) IS NULL
       OR TRY_CAST(longitude AS DOUBLE) IS NULL
       OR abs(TRY_CAST(latitude AS DOUBLE)) > 90
       OR abs(TRY_CAST(longitude AS DOUBLE)) > 180);


-- @rule: airline_active_flag
-- @stage: staging
-- Carriers marked inactive that still appear in the route file. The route
-- snapshot lags reality; worth reporting, not worth fixing.
SELECT upper(trim(l.iata)) AS row_key,
       to_json({'name': l.name, 'active': l.active,
                'routes': count(*)}) AS detail
FROM stg_airlines l
JOIN stg_routes r ON upper(trim(r.airline_iata)) = upper(trim(l.iata))
WHERE upper(trim(l.active)) <> 'Y'
GROUP BY 1, l.name, l.active;


-- @rule: delay_parseable
-- @stage: staging
-- Delay fields that are not numbers. Cancelled flights carry EMPTY delays,
-- which is correct and must become NULL - a zero would read as "on time"
-- and drag every average towards punctual.
SELECT flight_date || ' ' || carrier || ' ' || flight_number AS row_key,
       to_json({'dep_delay': dep_delay, 'arr_delay': arr_delay,
                'cancelled': cancelled}) AS detail
FROM stg_flights
WHERE (nullif(trim(dep_delay), '') IS NOT NULL
       AND TRY_CAST(dep_delay AS DOUBLE) IS NULL)
   OR (nullif(trim(arr_delay), '') IS NOT NULL
       AND TRY_CAST(arr_delay AS DOUBLE) IS NULL);


-- @rule: cancelled_has_code
-- @stage: staging
-- A cancelled flight should say why: A carrier, B weather, C national
-- airspace system, D security. Where it does not, the reason is unknown
-- rather than absent - which is why weather_cancel_share is a lower bound.
SELECT flight_date || ' ' || carrier || ' ' || flight_number AS row_key,
       to_json({'origin': origin, 'dest': dest,
                'cancel_code': cancel_code}) AS detail
FROM stg_flights
WHERE coalesce(TRY_CAST(cancelled AS DOUBLE), 0) >= 0.5
  AND nullif(trim(cancel_code), '') IS NULL;


-- @rule: flight_airports_known
-- @stage: graph
-- A flown route whose origin or destination is not in the OpenFlights list.
-- BTS and OpenFlights are independent sources; the disagreement is a
-- measurement, not a bug, and node_alias records which side each code came
-- from so the answer stays auditable.
SELECT a.alias AS row_key,
       to_json({'reason': a.reason,
                'flights': (SELECT count(*) FROM flights f
                            WHERE f.origin = a.node_id
                               OR f.dest = a.node_id)}) AS detail
FROM node_alias a
WHERE a.reason = 'bts_only';


-- @rule: airline_resolvable
-- @stage: graph
-- The operating carrier is not in the airline list. Same two independent
-- sources, same class of disagreement.
SELECT n.nkey AS row_key,
       to_json({'flights': count(f.carrier)}) AS detail
FROM nodes n
LEFT JOIN flights f ON f.carrier = n.id
WHERE n.class = class_code('Airline')
  AND (n.props ->> 'name') IS NULL
GROUP BY n.nkey;


-- @rule: no_self_route
-- @stage: graph
-- An airport flying to itself. Meaningless as a connection, and it inflates
-- degree counts wherever it survives.
SELECT n.nkey AS row_key,
       to_json({'flights': e.weight, 'day': e.valid_from}) AS detail
FROM edges e
JOIN nodes n ON n.id = e.src
WHERE e.rel = rel_code('flies_to') AND e.src = e.dst;


-- @rule: edge_endpoints_typed
-- @stage: graph
-- Every edge must point at nodes of the classes its relation declares. In
-- the other domain this caught 34,594 wrongly-typed edges. A traversal
-- through a mistyped edge does not crash - it quietly returns less - so
-- nothing but a declared rule finds it.
SELECT CAST(e.src AS VARCHAR) || '->' || CAST(e.dst AS VARCHAR) AS row_key,
       to_json({'relation': rr.name,
                'src_class': cs.name, 'expected_domain': rr.domain,
                'dst_class': cd.name, 'expected_range': rr.range}) AS detail
FROM edges e
JOIN relation_registry rr ON rr.code = e.rel
LEFT JOIN nodes ns ON ns.id = e.src
LEFT JOIN nodes nd ON nd.id = e.dst
LEFT JOIN class_registry cs ON cs.code = ns.class
LEFT JOIN class_registry cd ON cd.code = nd.class
WHERE cs.name IS NULL OR cd.name IS NULL
   OR NOT list_contains(rr.domain, cs.name)
   OR NOT list_contains(rr.range, cd.name);


-- @rule: route_endpoints_exist
-- @stage: graph
-- Both ends of a flies_to edge must be airports that exist in `nodes`. A
-- dangling id means our id minting disagrees with itself, which is the
-- severity-1 case: our builder is broken, not the source.
SELECT CAST(e.src AS VARCHAR) || '->' || CAST(e.dst AS VARCHAR) AS row_key,
       to_json({'src_exists': ns.id IS NOT NULL,
                'dst_exists': nd.id IS NOT NULL}) AS detail
FROM edges e
LEFT JOIN nodes ns ON ns.id = e.src
LEFT JOIN nodes nd ON nd.id = e.dst
WHERE e.rel = rel_code('flies_to')
  AND (ns.id IS NULL OR nd.id IS NULL);


-- @rule: single_region
-- @stage: graph
-- An airport may belong to at most one region at any instant. Regions are
-- not derived yet, so this is expected to be empty - and an empty severity-1
-- rule that will fire the moment the deriver is wrong is worth more than one
-- added afterwards.
SELECT n.nkey AS row_key,
       to_json({'regions': count(DISTINCT e.src)}) AS detail
FROM edges e
JOIN nodes n ON n.id = e.dst
WHERE e.rel = rel_code('covers')
GROUP BY n.nkey, e.valid_from
HAVING count(DISTINCT e.src) > 1;


-- @rule: region_truncated_at_cap
-- @stage: graph
-- Reachability from an airport still expanding at the depth cap. The network
-- is densely connected, so this is EXPECTED: it means the answer is a lower
-- bound, not that anything is broken. Capped at a small depth on purpose -
-- the equivalent rule in the other domain took 402 seconds.
SELECT n.nkey AS row_key,
       to_json({'depth_cap': 3, 'reached': cnt}) AS detail
FROM (
    SELECT src_id, count(*) AS cnt FROM (
        SELECT e1.src AS src_id, e2.dst
        FROM edges e1
        JOIN edges e2 ON e2.src = e1.dst AND e2.rel = rel_code('flies_to')
        WHERE e1.rel = rel_code('flies_to')
    ) GROUP BY src_id
) t
JOIN nodes n ON n.id = t.src_id
WHERE t.cnt > 2000;
