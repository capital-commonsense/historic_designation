# Items to fetch manually

These sources block scripted access (bot challenges or 403s), so the pipeline can't fetch them. Download them in a browser and save them **unedited** under `data/raw/manual/<folder>/`. Keep the original file names where possible. Nothing in that folder is ever overwritten.

What the pipeline does with each folder today:

- `hpo_reports/`: read automatically on every build.
- `dcpl_990/`: archived, OCR'd, and the figures recorded in `inputs/dcpl_990_lines.csv`. The 990s are scanned images, so I check each OCR'd figure by eye rather than trusting it blind.
- `mayors_agent/`, `hprb_box/`, `icg_settlement/`: parsers will be written once the files arrive, since their formats aren't known yet.

Status as of 2026-10-17. Ordered by how much each item unlocks.

## 1. DCPL Form 990 filings (H10, governance)

**Why blocked:** ProPublica returns HTTP 403 to scripted PDF downloads.
**Save to:** `data/raw/manual/dcpl_990/`. The file names below match ProPublica's, as you used for the two already provided.
**Already have:** FY ending 2014-03 and 2015-03.

Priority filings:

| Fiscal year end | Why | URL |
|---|---|---|
| 2011-03 | Years around the 2010 ICG agreement: when did money arrive? | https://projects.propublica.org/nonprofits/download-filing?path=2012_01_EO%2F52-1038849_990_201103.pdf |
| 2012-03 | Program revenue $211K, a possible first payment | https://projects.propublica.org/nonprofits/download-filing?path=2013_03_EO%2F52-1038849_990_201203.pdf |
| 2013-03 | Year before the $751K | https://projects.propublica.org/nonprofits/download-filing?path=2014_03_EO%2F52-1038849_990_201303.pdf |
| 2004-03 | Monument Realty / Potomac Place payment (2003) | https://projects.propublica.org/nonprofits/download-filing?path=2004_08_EO%2F52-1038849_990_200403.pdf |
| 2005-03 | Follow-on year for the Monument fund | https://projects.propublica.org/nonprofits/download-filing?path=2006_07_EO%2F52-1038849_990_200503.pdf |
| 2023-12 | Latest governance (board, Part VI) | https://projects.propublica.org/nonprofits/download-filing?path=IRS%2F521038849_202312_990_2025030723162592.pdf |

Remaining years, for complete governance and fund history:

- 2002-03 https://projects.propublica.org/nonprofits/download-filing?path=2002_11_EO%2F52-1038849_990_200203.pdf
- 2003-03 https://projects.propublica.org/nonprofits/download-filing?path=2003_11_EO%2F52-1038849_990_200303.pdf
- 2006-03 https://projects.propublica.org/nonprofits/download-filing?path=2007_01_EO%2F52-1038849_990_200603.pdf
- 2007-03 https://projects.propublica.org/nonprofits/download-filing?path=2008_03_EO%2F52-1038849_990_200703.pdf
- 2008-03 https://projects.propublica.org/nonprofits/download-filing?path=2009_03_EO%2F52-1038849_990_200803.pdf
- 2009-03 (990-EZ) https://projects.propublica.org/nonprofits/download-filing?path=2009_11_EO%2F52-1038849_990EZ_200903.pdf
- 2010-03 (990-EZ) https://projects.propublica.org/nonprofits/download-filing?path=2010_12_EO%2F52-1038849_990EZ_201003.pdf
- 2017-03 https://projects.propublica.org/nonprofits/download-filing?path=08_2018_prefixes_47-52%2F521038849_201703_990_2018080215560757.pdf
- 2018-03 https://projects.propublica.org/nonprofits/download-filing?path=01_2020_prefixes_51-52%2F521038849_201803_990_2020010316995176.pdf
- 2019-03 https://projects.propublica.org/nonprofits/download-filing?path=04_2021_prefixes_51-52%2F521038849_201903_990_2021040617904082.pdf
- 2021-12 https://projects.propublica.org/nonprofits/download-filing?path=download990pdf_05_2023_prefixes_48-53%2F521038849_202112_990_2023051021198149.pdf
- 2022-12 https://projects.propublica.org/nonprofits/download-filing?path=download990pdf_01_2024_prefixes_47-52%2F521038849_202212_990_2024010522183786.pdf
- 2024-12 https://projects.propublica.org/nonprofits/download-filing?path=IRS%2F521038849_202412_990_2026030223953505.pdf

ProPublica lists no PDF for FY ending 2016-03 or for the 2019-20 change to calendar years (2020-12 has data but no PDF link). If you want them, the IRS's Tax Exempt Organization Search or DCPL itself may have copies.

## 2. ICG / Third Church settlement (H3, H10)

**Why:** the payment amount, the 20% fee and the terms come only from a news report. The 990 shows a matching inflow but doesn't name the payer.
**Save to:** `data/raw/manual/icg_settlement/`

- Washington City Paper, Dec. 20, 2010, the article on the DCPL / Third Church / ICG agreement (save as PDF or HTML).
- Scribd document 45707262 (partial settlement text): https://www.scribd.com/document/45707262
- The court filing, c. Nov. 24, 2010. Press accounts say DC Court of Appeals, but the church's challenge may have been in federal court (U.S. District Court for D.C.). I couldn't search CourtListener's RECAP dockets because the API rate limit (50/hour) was exhausted. When it resets, the pipeline can run that search. If you have PACER access, search for *Third Church of Christ, Scientist v. District of Columbia*.

## 3. Mayor's Agent decisions (H6)

**Why blocked:** Georgetown Law's digital collection sits behind a Cloudflare browser challenge.
**Save to:** `data/raw/manual/mayors_agent/`, one PDF per decision. Keep the collection's file names or use `YYYY-MM-DD_case-name.pdf`.
**URL:** https://law.digital.georgetown.edu/collections/bdb751b4-23bc-44db-b7d7-cb2e188172ce

If the collection is large, start with decisions from 2000 on. HPO annual reports already summarize some cases, and the 112 DC Court of Appeals cases are being fetched through your CourtListener token.

## 4. HPRB meeting records on box.com (H1, H7)

**Why blocked:** HPO archives past meeting records in a box.com shared folder that needs a JavaScript browser.
**Save to:** `data/raw/manual/hprb_box/<year>/`. Keep box's folder and file names.
**URL:** https://app.box.com/s/t5gnx7p29jtpzv6on4khbiyl1p00owzh

**What's already covered:** HPRB actions for 2006–2026 from planning.dc.gov's publications (330 designation actions on 288 cases), but with gaps.
**Most useful from box:** meeting "Actions" PDFs for **1979–2005**, which aren't online elsewhere, plus any months missing from 2006–2012. Staff reports for designation cases would add HPO's recommendation for H7. Permit-case staff reports aren't needed.

## 5. Missing HPO annual reports (coverage table)

**Why:** not found at any URL pattern on planning.dc.gov, so they may not be online.
**Save to:** `data/raw/manual/hpo_reports/hpo_annual_report_fy<YYYY>.pdf`

FY1989, 1990, 1991, 1992, 1995, 2010, 2011, 2013, 2014, 2016, 2019. For FY2010–2019, the Inventory-update excerpts are already in hand, so the full reports matter mainly for Mayor's Agent and permit statistics. FY1989–1995 matter more. If they can't be found, add them to the records request.

## Not needed from you

- **Court opinions:** your CourtListener token unblocked them, and they're downloading, rate-limited to 50 requests/hour.
- **dccourts.gov PDFs:** the CourtListener text replaces them.
- **Zoning Commission exhibit lists:** fetched for 2000–2026 (48,872 exhibits in 823 cases). BZA cases aren't covered yet. That's a scope decision rather than a block, and it can be scripted.
