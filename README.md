# Tuition Trail

[Compare Canadian tuition](https://coolcode.ca/tuitiontrail/) or [browse all source-backed records](https://coolcode.ca/tuitiontrail/records/).

<!-- coolcode:guide -->
Start with nursing in Nova Scotia and British Columbia, then change the places, field or academic year. Open a place’s tuition history to inspect the reported fees and preliminary years. The graduate-income comparison uses earlier Canadian undergraduate degree cohorts and broader fields, each labelled with the graduation year and constant-dollar basis.
<!-- /coolcode:guide -->

The opening comparison shows average annual tuition for Canadian undergraduate students. Statistics Canada table [37-10-0003-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3710000301) weights fees by enrolment. Fees are in current Canadian dollars before financial assistance or tax rebates. Residency can affect tuition in Quebec, Nova Scotia and Newfoundland and Labrador. Published missing values keep their source status in the downloadable edition. The site renders empty or undisclosed observations as text. The source flags 2026/2027 as preliminary.

[Table 37-10-0287-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3710028701) tracks employment income of previous graduates in constant dollars. Tuition Trail selects Canadian students, undergraduate degrees, all genders, ages 15–64, and the subpopulation reporting employment income. Their median includes wages and net self-employment income. Full-time students in any of the ten subsequent years and graduates with missing income information during follow-up are excluded. Geography is the place of study. This comparison cannot infer an individual’s wage or a current student’s future earnings. Each earnings record preserves the cohort, broad source field and currency basis. Jobs, institutions and tuition field labels do not identify earnings cohorts.

## Expand or customize

Edit the field and place selectors in `web/settings.json` to change the opening example. The tuition collector imports every published field, geography and academic year. Earnings imports the broad field groups in the table metadata; its graduate-population filters and horizons are defined in `scripts/refresh.py`. Revisit interface definitions and historical comparability before changing cohort filters. Province and field profiles are built from observed series with at least one published value. Settings and estimates are public. Form choices update the shareable page URL. They use the saved edition in the browser and do not contact Statistics Canada or store a reading history. Opening a source or sharing a link discloses that URL to its destination.

Source: Statistics Canada. Adapted under the [Statistics Canada Open Licence](https://www.statcan.gc.ca/en/reference/licence). CoolCode calculated the comparisons. Statistics Canada does not endorse this application.

## Data and publication

The monthly check on the 8th at 13:29 UTC downloads the two official full-table ZIPs, reads the tuition years and broad income classifications, and builds a compact local edition. Tuition is released annually. Cohort releases are occasional and have a separate reference period. An unsuccessful download, loss of earlier series or invalid dataset retains the previous deployed edition. The check date is independent of the academic and graduation years. The native workflow, schedule guard and the hub watchdog support scheduled checks.

```sh
python3 scripts/refresh.py
# Or rebuild from unmodified, previously downloaded 37100003.zip and 37100287.zip
python3 scripts/refresh.py --source-dir /path/to/official/zips
python3 -m unittest discover -s tests
node --test tests/*.test.mjs
python3 scripts/build.py
python3 tests/browser_smoke.py
```

`web/data/edition.json` is the checked-in input for the offline build. A main push checks and publishes `dist/` to GitHub Pages, including `data/status.json` and the result-only sitemap. Successful scheduled checks commit validated source data and dispatch the same Pages workflow. The directory contains the sources, yearly values, and a link to the national Wage Window tool.
