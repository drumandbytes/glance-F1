# Changelog

## [2.1.1](https://github.com/drumandbytes/paddock-api/compare/v2.1.0...v2.1.1) (2026-09-23)


### Bug Fixes

* port the better-built tyre-usage widget, fix a dead docstring ref ([#27](https://github.com/drumandbytes/paddock-api/issues/27)) ([6d02b83](https://github.com/drumandbytes/paddock-api/commit/6d02b8300e8ecb60fda6330497f3b15f17b089ce))

## [2.1.0](https://github.com/drumandbytes/paddock-api/compare/v2.0.0...v2.1.0) (2026-09-22)


### Features

* expose last_race url/country, wire unused fields into widgets ([#25](https://github.com/drumandbytes/paddock-api/issues/25)) ([ae5329c](https://github.com/drumandbytes/paddock-api/commit/ae5329ce2cc42ae2323f52b98fc6b2fae14544d2))

## [2.0.0](https://github.com/drumandbytes/paddock-api/compare/v1.2.2...v2.0.0) (2026-09-22)


### ⚠ BREAKING CHANGES

* replace Python implementation with Go ([#22](https://github.com/drumandbytes/paddock-api/issues/22))

### Features

* replace Python implementation with Go ([#22](https://github.com/drumandbytes/paddock-api/issues/22)) ([80962fc](https://github.com/drumandbytes/paddock-api/commit/80962fc9ad7c2693feb8873c73b3bd54745a5e47))

## [1.2.2](https://github.com/drumandbytes/paddock-api/compare/v1.2.1...v1.2.2) (2026-09-21)


### Performance Improvements

* **api:** fix cache reads, move blocking Ergast/FastF1 calls to threadpool ([#20](https://github.com/drumandbytes/paddock-api/issues/20)) ([d29b6cb](https://github.com/drumandbytes/paddock-api/commit/d29b6cbb2710139bd024a8317400cd8adddb2e73))

## [1.2.1](https://github.com/drumandbytes/paddock-api/compare/v1.2.0...v1.2.1) (2026-09-21)


### Bug Fixes

* track map stroke width and outline visibility ([#15](https://github.com/drumandbytes/paddock-api/issues/15)) ([b098f63](https://github.com/drumandbytes/paddock-api/commit/b098f630c7a06428d0e4eae01fba63125a9a40f7))

## [1.2.0](https://github.com/drumandbytes/paddock-api/compare/v1.1.0...v1.2.0) (2026-09-20)


### Features

* add tyre usage per session for the current race weekend ([#7](https://github.com/drumandbytes/paddock-api/issues/7)) ([86417d6](https://github.com/drumandbytes/paddock-api/commit/86417d6ae0c2c5e52d45b73b5e33bf184673578b))
* drop f1api.dev, use fastf1/Ergast for everything ([1b79466](https://github.com/drumandbytes/paddock-api/commit/1b7946640234952e969efb2caea635d7cc6797eb))


### Bug Fixes

* remove dead Lap Record/Length rows from the Next Race widgets ([#13](https://github.com/drumandbytes/paddock-api/issues/13)) ([c94b16a](https://github.com/drumandbytes/paddock-api/commit/c94b16a4b584ee3fbcfb39832e7ae347af4a00af))
* stop retrying after a rate limit, don't burn through the whole calendar ([8ca9b4a](https://github.com/drumandbytes/paddock-api/commit/8ca9b4a846e58ae2312646be120eb5f171a4b5a4))


### Performance Improvements

* select tyre_usage's needed columns before the groupby ([#14](https://github.com/drumandbytes/paddock-api/issues/14)) ([00b59ea](https://github.com/drumandbytes/paddock-api/commit/00b59ea544dd183242373d83a6d6fc14f0e680c9))
