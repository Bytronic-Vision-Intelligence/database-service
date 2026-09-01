-- Starting schema and sample rows for churchill_database.
--
-- The .db file itself is gitignored: it is a live store the service writes to,
-- so committing it meant every run showed as a binary diff, and reverting it
-- pulled the frames/results tables out from under a running service. This file
-- is the tracked source of truth for what a fresh database starts as.
--
-- Applied on boot by dependencies.seed.seed_database(), which only runs when
-- sku_table is absent - an existing store is never overwritten.
--
-- NOTE: `Id int Auto Increment` is not valid SQLite. SQLite accepts it as a
-- column named Id with the type string "int Auto Increment", but it never
-- auto-populates, which is why every seeded row has Id NULL. This reproduces
-- the committed schema exactly rather than quietly changing it: main() reads
-- these column names via set_database_map(), and the fuzzy search builds its
-- query from them. Replacing this table is the SKU config-profiles work.

CREATE TABLE IF NOT EXISTS sku_table(
    Id int Auto Increment,
    depth_data longblob NULL,
    colour_data longblob NULL,
    depth FLOAT,
    area FLOAT,
    perimeter FLOAT
);

INSERT INTO sku_table (depth, area, perimeter) VALUES
    (10.0,  299.0,  500.0),
    (10.0,  299.0,  500.0),
    (10.0,  259.0,  500.0),
    (150.0,  29.0,   50.0),
    (50.0, 2119.0,   20.0);
