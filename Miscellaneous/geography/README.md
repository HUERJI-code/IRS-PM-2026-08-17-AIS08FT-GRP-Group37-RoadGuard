# RoadGuard static geographic materials

These freeze the first Jurong task area and user-selected NUS-ISS simulated origin. Business conventions follow the [scope/depot document](../JURONG_SCOPE_AND_DEPOT.md). No business implementation or driving routes are included.

| File | Contents |
| --- | --- |
| [jurong-boundary-mp2025.geojson](jurong-boundary-mp2025.geojson) | Two original URA MP2025 Features, JURONG EAST/JURONG WEST, without simplification |
| [nus-iss-depot.geojson](nus-iss-depot.geojson) | NUS-ISS building address reference for shared four-crew simulated origin |
| [sources.json](sources.json) | Sources/query results/versions/hashes/static geometry checks |
| [jurong-scope-map.png](jurong-scope-map.png) | Area/origin schematic, not road navigation |

GeoJSON uses [longitude, latitude], WGS84 decimal degrees. Validate tasks against the union, including boundaries. NUS-ISS is outside and is only a designated-depot exception; vehicle access needs later verification.

Boundary version: jurong-je-jw-mp2025-v1. Depot: nus-iss-v1. Do not substitute another year or separately downloaded boundary without synchronized change.

## Sources and attribution

Contains [URA/data.gov.sg Master Plan 2025 Planning Area Boundary (No Sea)](https://data.gov.sg/datasets/d_2cc750190544007400b2cfd5d7f53209/view), obtained 2026-10-12 under [Singapore Open Data Licence v1.0](https://data.gov.sg/open-data-licence). Boundary is a source subset; map is derived. Retain attribution/license without implying government endorsement.

Address: [NUS-ISS directions](https://www.iss.nus.edu.sg/about-us/getting-to-nus-iss); coordinates: [SLA OneMap full-address query](https://www.onemap.gov.sg/api/common/elastic/search?searchVal=25%20HENG%20MUI%20KENG%20TERRACE&returnGeom=Y&getAddrDetails=Y&pageNum=1). NUS-ISS is a course-simulation dispatch location, not evidence of university involvement in road maintenance.
