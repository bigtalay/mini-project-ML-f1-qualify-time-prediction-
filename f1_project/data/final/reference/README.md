# Circuit features (2021–2023)

Source: F1DB contributors, https://github.com/f1db/f1db, revision 5487e45d4df4097080332f29a0513f275c1023cd. CC BY 4.0: https://creativecommons.org/licenses/by/4.0/ (upstream LICENSE at that revision).

Adaptation: selected circuitId, circuitLayoutId, courseLength (km), turns from each season/race.yml; matched FastF1 by race date, renamed columns, omitted race outcomes. Two explicit matches by year/event: Turkey 2021 (upstream date says October 3; FastF1 October 10) and Las Vegas 2023 (local November 18 versus UTC November 19). No positional round-number join. Original URL is recorded per row.

66 rows cover the existing events snapshot. These are retrospective records of the layout used that year; dimensions are known before Qualifying, not derived from outcomes. They are not a historical publication-time archive. Do not replace them with today's layout.

Barcelona 2021–22 = 4.675 km / 16 corners; 2023 = 4.657 / 14. Singapore 2022 = 5.063 / 23; 2023 = 4.940 / 19. Cross-check Barcelona: https://corp.formula1.com/formula-1-aws-gran-premio-de-espana-2023-changes-its-track-configuration/ . Singapore corner change: https://www.formula1.com/en/latest/article/singapore-grand-prix-set-to-feature-revised-track-layout-in-2023.6KsrU6hQw3hxrVJ6zKeJ74 (announced length provisional; final length from race record).

Only circuit_length_km and corner_count enter X. IDs/URLs are provenance, not features. Raw lap CSVs retain their tyre columns for audit and browsing; the new model does not use them.
