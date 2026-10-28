# Public records request: HPO nomination case log

**Status:** draft, not filed. The author files it; see `status.md`.

**Submit via:** DC Government Public FOIA Portal (believed to be https://foia-dc.gov/; verify before filing), agency: DC Office of Planning.

---

To: DC Office of Planning, FOIA Officer

Under the DC Freedom of Information Act (D.C. Code § 2-531 et seq.), I request copies of the following records maintained by the Historic Preservation Office, for the period January 1, 1979 to the present:

1. Any log, database, spreadsheet or index of applications for historic landmark or historic district designation (including boundary amendments), showing for each application: case number, property or district name, address or square/lot, applicant name(s), date received, hearing date(s), Historic Preservation Review Board action and date, and final disposition (designated, denied, withdrawn, or pending).
2. For applications withdrawn by the applicant, the withdrawal letter or notice.
3. Any agreements, memoranda of understanding, covenants or mitigation agreements provided to or held by the Historic Preservation Office that reference the withdrawal of a designation application or an applicant's agreement not to oppose a permit application.

Electronic records are preferred in their native format (e.g., spreadsheet or database export). If any portion is withheld, please cite the specific exemption and release all reasonably segregable portions. I request a fee waiver because the records will be used to inform the public about the operation of DC's historic preservation program; if fees are expected to exceed $50, please contact me first.

---

## Notes for the filer

- Case numbers in published sources take the form `YY-NN` (e.g. Case 22-05); citing a few known numbers (from `nominations.csv`) may help the office locate the log.
- If the office says no consolidated log exists, ask for item 1 as whatever the HPO uses to produce the "applications received / approved / denied" tables in its annual reports.
- When records arrive, save them unedited under `data/raw/manual/records_request/<date>/` and update `status.md`; the pipeline joins them to `nominations.csv` by case number and address.
