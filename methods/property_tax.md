# Property tax on historic property, and a growth-gap scenario

How the property tax analysis and chart (`charts/out/property_tax_scenario`) were built, written to be checked step by step. Figures below are from raw snapshot 2026-10-17 as built on 2026-10-20. `findings.md` ("Property tax" section) is regenerated on every `make all`. Where it and this note disagree, the findings are current and this note is stale.

## Question

The DC Policy Center (DCPC) found slower assessed-value growth in historic districts. Taking that as an indicator:
- How much property tax does historic property pay?
- How much more would it pay had it grown like the rest of the city?

## Sources

| What | Where | Notes |
|---|---|---|
| Tax billed per property per year | DC GIS ITSPE layer, `DCGIS_DATA/Property_and_Land_WebMercator/MapServer/53` | Fetched as `itspe_tax_history` (see `config.py`): `PY1`–`PY9` YEAR/TAX (TY2017–2025), `CY1TAX` + `CY2TAX` (TY2026's two halves), `OLDTOTAL`. Raw pages are in `data/raw/2026-10-17/arcgis/itspe_tax_history/`. Server count 221,677. |
| Property type, designation status | `data/joined/itspe_status.parquet` | Existing pipeline: ITSPE joined to the zoning lookup, the condo crosswalk and the historic district and landmark layers. |
| Designation dates | `inputs/district_dates.csv`, `inputs/landmark_dates.csv` via `analysis/eras.py` | District first date = earliest of the 1950 act, a DC listing or a designation. Landmark dates come from the dated GIS features. |
| DCPC growth rates | `inputs/dcpc_growth_2006_2021.csv` | From [DCPC, April 13, 2022](https://www.dcpolicycenter.org/publications/historic-districts/) (Kathpalia and Sayin). The quotes were read from the web page; no copy is in the snapshot, so the build does not check them against source text. |

**Data DCPC had that we don't:** yearly ITSPE snapshots for 2006–2021. Only the current extract is public, so assessed values before 2018 would need a records request to OCFO or DC GIS.

## Steps

1. **Normalize** (`normalize/__init__.py`, `itspe_tax_history`).
   - Reshape to one row per record and tax year, written to `data/normalized/itspe_tax_history.parquet`.
   - TY2026 = CY1TAX + CY2TAX. Rows with zero or missing tax are dropped.
   - `PY10` (TY2016) and `PY9` (TY2017) are nearly empty: TY2017 has 2,414 rows against about 194,000 for each later year. The analysis therefore starts at TY2018.

2. **Classify each record** (`analysis/revenue.py`, `records()`). The join is on SSL, and every tax-history SSL matched.
   - *Residential*: `eras.property_class(proptype) == "residential"`. That covers Residential-*, Condominium, Cooperative, dormitories and fraternity houses, the same rule as the value-by-era analysis.
   - *Historic in year t*: the record is designated today and its first designation date (district or landmark, earlier wins) falls in year t or earlier. Records with no designation date count as historic in every year.
   - *Pre-2006 district home*: residential, and its district's first date is before 2006. This matches DCPC's sample, which excluded districts added in 2006 or later (DCPC footnote 10). Landmark-only property is not in this group.

3. **Actual tax by year.**
   - Sum tax by year for historic and other records, and for the two subgroups.
   - Output: `data/analysis/property_tax_by_year.csv`.

4. **DCPC scenario.**
   - Ratio r (`dcpc()`), two versions:
     - *Total*: r = 1.062 / 1.049 = 1.0124 a year. These are DCPC's annual growth rates in total value, 2006–21, outside and inside historic districts. The total includes new construction.
     - *Existing stock*: r = (1.94 / 1.85)^(1/15) = 1.0032 a year. This is DCPC's growth for buildings standing in 2006: 94% outside, 85% inside, over 15 years.
   - Scenario gap in year t = T_t × (r^(t − 2006) − 1), where T_t is the tax billed on pre-2006 district homes in year t.
     - The gap compounds from 2006, DCPC's start year, and DCPC's 2006–21 rate is carried forward past 2021.
     - This assumes tax scales with assessed value.
   - The chart stacks other property, then historic property, then the gap, with a dashed line at the existing-stock gap.

5. **Check against the roll's own years.**
   - *Same-record panel*: residential records billed in every year TY2018–2026 that are either pre-2006 district homes (39,544) or never designated (125,926). Landmark-only property and homes in post-2006 districts are left out.
   - Annual growth rate (CAGR) of the group totals, TY2018→2026, both for the panel and for all records.
   - `gap_at_other_rate`: what the pre-2006 district homes would pay in TY2026 had their TY2018 tax grown at the never-designated homes' rate, minus what they actually pay.
     - Computed once at the citywide rate.
     - Computed again ward by ward and summed. Ward is the tax roll's ward, falling back to the zoning lookup's.

## Results (TY2026 unless noted)

| | $ millions |
|---|---|
| All property tax billed | 2,851.7 |
| Historic (designated by that year) | 988.8 (34.7%; TY2018 36.5%) |
| of which residential | 466.1 |
| of which homes in pre-2006 districts | 382.8 |
| Scenario gap, DCPC total rate | 106.9 (TY2018–26 cumulative: 669.2) |
| Scenario gap, DCPC existing-stock rate | 25.0 (cumulative: 159.2) |

| Tax year | Other | Historic | Pre-2006 district homes | Gap, total | Gap, existing stock |
|---|---|---|---|---|---|
| 2018 | 1,595.6 | 918.9 | 285.8 | 45.5 | 11.1 |
| 2019 | 1,674.3 | 965.5 | 297.3 | 51.6 | 12.5 |
| 2020 | 1,733.6 | 966.7 | 308.1 | 58.0 | 14.0 |
| 2021 | 1,864.3 | 1,025.8 | 329.2 | 66.8 | 16.0 |
| 2022 | 1,797.6 | 974.5 | 335.0 | 73.0 | 17.4 |
| 2023 | 1,853.5 | 987.1 | 346.7 | 80.8 | 19.2 |
| 2024 | 1,884.3 | 1,001.4 | 357.4 | 88.7 | 21.0 |
| 2025 | 1,931.6 | 1,021.4 | 371.2 | 97.9 | 23.0 |
| 2026 | 1,862.9 | 988.8 | 382.8 | 106.9 | 25.0 |

**Residential tax growth, TY2018–2026, a year:**

| | Pre-2006 district homes | Never-designated homes |
|---|---|---|
| All records | 3.7% | 6.2% |
| Same records | 2.9% | 4.6% |

**Same-record gap in TY2026:**
- At the citywide rate, the pre-2006 district homes would pay $47.3M more.
- At each ward's own rate, they would pay $12.3M *less*:

| Ward | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| $M | +3.7 | −23.1 | +1.2 | +1.0 | +0.2 | +3.4 | +0.0 | +1.2 |

Wards 4, 5, 7 and 8 have few pre-2006 district homes: 480, 294, 10 and 708 records in the panel.

**Session check, not in the pipeline** (rerun it by grouping the panel on `pd.qcut` of TY2018 tax). Same-record growth by TY2018 tax quintile, historic against other:

| Quintile | Pre-2006 district homes | Other homes |
|---|---|---|
| 2nd | 3.4% | 7.2% |
| 3rd | 2.4% | 5.3% |
| 4th | 3.2% | 4.1% |
| Top | 2.6% | 3.0% |

The bottom quintile is dominated by small bills and growth from near zero, so it isn't meaningful.

## Cross-checks

- **Totals.** TY2024 tax billed on today's roll is $2.886B. OCFO's December 2024 revenue letter reports FY2024 real property tax revenue of $2.917B. Tax year and fiscal year differ, collections differ from levies, and the roll lacks retired records, so a close match is all that is expected.
- **Current year.** TY2026 total ($2.852B) equals the sum of `ANNUALTAX` on the current extract ($2.855B).
- **Coverage.** The record count rises from about 194,000 (TY2018) to about 205,000 (TY2026). That is partly new records and partly records retired before 2026 that the roll no longer carries. Early years therefore run low, and growth rates over all records are slightly overstated. The same-record panel avoids this.

## Limitations

- **The scenario is not a measured loss and is not causal.**
  - DCPC does not attribute its gap to designation. It names higher starting values, maintenance costs and nearness to new development as possible reasons.
  - Most of DCPC's total gap is new construction outside the districts, much of it on former industrial land.
  - The ward-by-ward comparison erases the 2018–26 gap.
- **Scaling tax with value is approximate.** The homestead deduction (a fixed amount) and the 10% cap on taxable assessment increases for owner-occupants don't scale with value. Tax growth is therefore not value growth, and the same-record comparison mixes the two.
- **DCPC's rate is extrapolated.** It covers 2006–21 and is carried to 2026. The roll's own 2018–26 citywide gap (2.9% against 4.6% on the same records) is larger than DCPC's, which suggests the extrapolation is not overstated at the citywide level.
- **Boundaries are today's.** Lots added by a later district expansion count from the district's original date (as in H9).
- **Some property gets no scenario.** Commercial, landmark-only and post-2006 district property ($988.8M − $382.8M = $606M of the TY2026 historic total) is left out because DCPC measured only residential property in pre-2006 districts.
- **Units differ from DCPC's.** We count tax records (condo units separately), while DCPC grouped condos into buildings. Group totals are comparable; counts are not.

## Files

- `src/historic_preservation/config.py`: `itspe_tax_history` layer
- `src/historic_preservation/normalize/__init__.py`: `itspe_tax_history()`
- `src/historic_preservation/analysis/revenue.py`: classification, scenario, same-record checks
- `src/historic_preservation/charts/revenue.py`: `property_tax()`; headline override key `property_tax_scenario`
- `src/historic_preservation/report.py`: `property_tax()` section of `findings.md`
- Outputs: `data/analysis/property_tax_by_year.csv`, `data/analysis/property_tax_summary.json`, `charts/out/property_tax_scenario.{png,svg,data.csv}`

## Open items

- Save the DCPC page to the snapshot so the build can check its quotes.
- Request ITSPE yearly snapshots for 2006–2017 from OCFO or DC GIS. These would allow DCPC's comparison to be redone on the same records and within wards.
- Possibly move the scenario to ward-specific rates, or replace it with them.
