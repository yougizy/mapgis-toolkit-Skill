# Contributing

Thanks for considering a contribution. This project deals with reverse-engineered
binary formats, so a few ground rules keep things maintainable.

## Development setup

```bash
git clone https://github.com/you/mapgis-toolkit-Skill.git
cd mapgis-toolkit-Skill
pip install -e ".[all]"
python -m unittest discover -s tests
```

The core format codecs (`geometry`, `shp`, `hdb`, `mapx`, `layout`) must keep
working with the standard library only. Optional features live behind extras.

## Tests

- Every change must keep `python -m unittest discover -s tests` green.
- Tests that need a MapGIS empty database read the `MG_TEMPLATE` environment
  variable and are skipped when it is unset.
- When touching binary codecs, add a round-trip test and, if possible, an
  assertion against real sample data.

## Format changes

If you discover a new part of the format:

1. Document it in `docs/format-hdb.md` or `docs/format-mapx.md`.
2. Add a probe script under `tools/` (read-only, no side effects).
3. Add a regression test with a minimal fixture.
4. Avoid hard-coding absolute paths; use `MAPGIS_HOME` / `MG_TEMPLATE`.

## Pull requests

- Keep changes focused; separate refactors from behavior changes.
- Do not commit personal data, credentials, customer data or licensed MapGIS
  installation files.
- Update `README.md` / `AGENTS.md` when behavior or public API changes.

## License

By contributing you agree that your contributions are licensed under the MIT
License.
