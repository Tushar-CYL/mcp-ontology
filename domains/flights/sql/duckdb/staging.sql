-- Flights domain - staging tables (DuckDB)
--
-- Deliberately permissive: VARCHAR everywhere, no constraints. Staging holds
-- the data AS IT IS - including OpenFlights' literal \N for "no value", the
-- airports with no IATA code, and the empty delay fields on cancelled
-- flights - so the validator can MEASURE those things. Cleaning before
-- validating hides exactly what this project exists to show.

-- ------------------------------------------------------------- OpenFlights
-- None of these three files has a header row, and none is quoted
-- consistently, so the column order below IS the contract. It comes from the
-- OpenFlights data page, verified against the actual files.
CREATE TABLE IF NOT EXISTS stg_airports (
    openflights_id  VARCHAR,
    name            VARCHAR,
    city            VARCHAR,
    country         VARCHAR,
    iata            VARCHAR,   -- \N where the airport has none
    icao            VARCHAR,
    latitude        VARCHAR,
    longitude       VARCHAR,
    altitude        VARCHAR,
    tz_offset       VARCHAR,
    dst             VARCHAR,
    tz_name         VARCHAR,
    type            VARCHAR,
    source          VARCHAR,
    src_file        VARCHAR
);

CREATE TABLE IF NOT EXISTS stg_airlines (
    openflights_id  VARCHAR,
    name            VARCHAR,
    alias           VARCHAR,
    iata            VARCHAR,
    icao            VARCHAR,
    callsign        VARCHAR,
    country         VARCHAR,
    active          VARCHAR,   -- 'Y' / 'N'
    src_file        VARCHAR
);

-- The static route network: who flies where, as a snapshot. It has no dates
-- at all, which is precisely why the BTS flights below are also loaded -
-- they are what make the graph rewindable.
CREATE TABLE IF NOT EXISTS stg_routes (
    airline_iata    VARCHAR,
    airline_id      VARCHAR,
    src_iata        VARCHAR,
    src_id          VARCHAR,
    dst_iata        VARCHAR,
    dst_id          VARCHAR,
    codeshare       VARCHAR,   -- 'Y' or empty
    stops           VARCHAR,
    equipment       VARCHAR,   -- space-separated aircraft type codes
    src_file        VARCHAR
);

-- --------------------------------------------------------------------- BTS
-- The real flights. One row per flight actually scheduled, with what
-- happened to it. The source file has 110 columns; these are the ones the
-- graph and the metrics use. Loading all 110 would cost ~4x the space to
-- carry fields nothing reads.
--
-- Everything stays VARCHAR here on purpose: Cancelled arrives as '0.00',
-- delays are empty strings on cancelled flights, and CRSDepTime is '0659' -
-- a string whose leading zero matters. Parsing happens in facts.sql, where
-- TRY_CAST can count what failed instead of aborting the load.
CREATE TABLE IF NOT EXISTS stg_flights (
    flight_date      VARCHAR,
    carrier          VARCHAR,   -- Reporting_Airline, e.g. 'AA'
    flight_number    VARCHAR,
    tail_number      VARCHAR,   -- one physical aeroplane, e.g. 'N104NN'
    origin           VARCHAR,
    origin_city      VARCHAR,
    dest             VARCHAR,
    dest_city        VARCHAR,
    sched_dep        VARCHAR,
    dep_delay        VARCHAR,   -- minutes; negative means early
    arr_delay        VARCHAR,
    cancelled        VARCHAR,   -- '0.00' / '1.00'
    cancel_code      VARCHAR,   -- A carrier, B weather, C NAS, D security
    diverted         VARCHAR,
    air_time         VARCHAR,
    distance         VARCHAR,   -- statute miles
    src_file         VARCHAR
);
