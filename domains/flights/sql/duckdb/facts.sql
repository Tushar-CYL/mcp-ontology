-- Flights domain - the fact table behind the semantic layer (DuckDB)
--
-- NOT part of the graph. The graph answers "what connects to what"; this
-- answers "what happened to the flights between them". Keeping them apart
-- means a traversal never scans half a million flight rows.
--
-- Node ids are resolved here, so a metric filtered by airport and an edge
-- in the graph can never disagree about which airport that is.

CREATE TABLE IF NOT EXISTS flights (
    fdate         DATE NOT NULL,
    carrier       BIGINT,        -- Airline node id
    origin        BIGINT,        -- Airport node id
    dest          BIGINT,        -- Airport node id
    aircraft      BIGINT,        -- Aircraft node id
    flight_number VARCHAR,
    dep_delay     REAL,          -- minutes; NEGATIVE means early
    arr_delay     REAL,
    cancelled     BOOLEAN NOT NULL,
    cancel_code   VARCHAR,       -- A carrier, B weather, C NAS, D security
    diverted      BOOLEAN NOT NULL,
    air_time      REAL,
    distance      REAL
);

DELETE FROM flights;

-- Delays stay NULL on cancelled flights rather than becoming 0. A zero here
-- would read as "departed exactly on time", which is the opposite of what
-- happened, and it would drag every average towards punctual.
INSERT INTO flights
SELECT f.fdate,
       node_id(class_code('Airline'),  f.carrier),
       node_id(class_code('Airport'),  f.origin),
       node_id(class_code('Airport'),  f.dest),
       CASE WHEN f.tail_number IS NULL THEN NULL
            ELSE node_id(class_code('Aircraft'), f.tail_number) END,
       f.flight_number,
       CAST(f.dep_delay AS REAL),
       CAST(f.arr_delay AS REAL),
       f.cancelled,
       f.cancel_code,
       f.diverted,
       CAST(f.air_time AS REAL),
       CAST(f.distance AS REAL)
FROM clean_flights f;
