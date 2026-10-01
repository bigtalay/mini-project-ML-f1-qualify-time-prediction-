# Circuit features (2021–2023)

Source: F1DB contributors, https://github.com/f1db/f1db, revision 5487e45d4df4097080332f29a0513f275c1023cd. CC BY 4.0: https://creativecommons.org/licenses/by/4.0/ (upstream LICENSE at that revision).

Reproduction: run final.ipynb sections 2.8.1–2.8.3. The notebook downloads the pinned GitHub directory indexes, original race.yml files and Grand Prix name reference YAMLs into f1db/<revision>/, recording each URL and byte-level SHA256 in manifest.json. Existing source files are verified before reuse; the existing circuits.csv is never used to infer a match.

Matching: follow race.yml grandPrixId to the pinned src/data/grands-prix/<id>.yml fullName, and join by year plus that normalized Grand Prix name against FastF1 EventName (case, whitespace and punctuation removed). Only when this fails, require an exact normalized official-name/year match instead (Mexico City Grand Prix versus Mexican Grand Prix, three events). Every pair must independently pass the FastF1 local race date or Race-session UTC date check against the F1DB race date, except the explicit Turkey discrepancy below. No fuzzy matches, positional round-number joins or assumed event_id-to-circuit mappings. Duplicate or unmatched names and unexplained date differences stop processing. Both original names and the matching method remain in the audit.

Date discrepancy: Turkey 2021 has October 3 in this pinned F1DB revision and October 10 in FastF1. The notebook explicitly allows only this year/Grand Prix/date combination after the Grand Prix names match; it does not modify the source file. Las Vegas 2023 has November 18 in FastF1 EventDate and November 19 in both its Race-session UTC date and F1DB, so it passes the UTC-date check without an event-id override.

Audit: circuit_matches.csv records both Grand Prix names and official names, both FastF1 dates, the F1DB date/round, match method, historical layout, both source URLs/files and SHA256 hashes. circuits.csv is generated from that table, selecting circuitId, circuitLayoutId, courseLength (km), turns and renaming the columns; race outcomes are omitted. The notebook reads the generated CSV back and checks complete event coverage. If it is byte-identical to the existing snapshot, no rewrite occurs, preserving the saved model fingerprint.

66 rows cover the existing events snapshot. These are retrospective records of the layout used that year; dimensions are known before Qualifying, not derived from outcomes. They are not a historical publication-time archive. Do not replace them with today's layout.

Barcelona 2021–22 = 4.675 km / 16 corners; 2023 = 4.657 / 14. Singapore 2022 = 5.063 / 23; 2023 = 4.940 / 19. Cross-check Barcelona: https://corp.formula1.com/formula-1-aws-gran-premio-de-espana-2023-changes-its-track-configuration/ . Singapore corner change: https://www.formula1.com/en/latest/article/singapore-grand-prix-set-to-feature-revised-track-layout-in-2023.6KsrU6hQw3hxrVJ6zKeJ74 (announced length provisional; final length from race record).

Only circuit_length_km and corner_count enter X alongside FP1_Time, FP2_Time and FP3_Time. IDs/URLs are provenance, not features. Raw lap CSVs retain their tyre columns for audit and browsing, not model inputs.
