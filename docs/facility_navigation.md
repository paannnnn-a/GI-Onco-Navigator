# Healthcare facility navigation

This module filters verified facility records using only the location, willingness to travel, cancer type, and service attributes supplied by the patient. Results contain no quality score for a hospital, department, or clinician; make no outcome claim; and do not select a provider for the patient.

## Sources and verification

- Current operating registration should be checked in the [National Health Commission facility register](https://zgcx.nhc.gov.cn/unit).
- Service scope, key disciplines, regulated medical technologies, contact details, and access processes must come from the facility's official website.
- The National Health Commission's [Measures for the Administration of Healthcare Institution Information Disclosure](https://www.nhc.gov.cn/wjw/gfxwj/202201/ff9ccaeb120c4a5b81699eb5d77676a9.shtml) identifies institution overview, department distribution, services, key disciplines, regulated technologies, and service processes as disclosure categories and requires accurate, timely updates.
- An administrator records the verification date, official registration link, and verification note. Unverified, withdrawn, or stale records do not enter patient filtering.

“Verified” means only that recorded public attributes matched the cited official pages on the verification date. It is not a platform guarantee of clinical quality, access, cost, insurance coverage, or suitability for an individual. Patients must confirm these matters directly with the facility and payer.
