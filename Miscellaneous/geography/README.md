# RoadGuard 静态地理资料

这些资料固定首版 Jurong 任务范围和用户指定的 NUS-ISS 模拟起点。业务约定以 [范围与基地文档](../JURONG_SCOPE_AND_DEPOT.md) 为准；这里不包含业务实现或行驶路线。

| 文件 | 内容 |
| --- | --- |
| [jurong-boundary-mp2025.geojson](jurong-boundary-mp2025.geojson) | URA MP2025 的 JURONG EAST、JURONG WEST 两个原始 Feature；未简化 |
| [nus-iss-depot.geojson](nus-iss-depot.geojson) | NUS-ISS 建筑地址参考点，作为四队共用模拟起点 |
| [sources.json](sources.json) | 来源、查询结果、版本、哈希及静态几何核验记录 |
| [jurong-scope-map.png](jurong-scope-map.png) | 区域与起点示意图，不是道路导航图 |

GeoJSON 坐标顺序为 `[longitude, latitude]`，WGS84 十进制度。任务范围按两个多边形的并集判断，包含边界。NUS-ISS 在此区域之外，仅作为指定基地例外；其车辆入口仍需后续核验。

边界版本：`jurong-je-jw-mp2025-v1`。基地版本：`nus-iss-v1`。未经同步变更，不替换为其他年份或独立下载的边界。

## 来源与署名

包含 [Urban Redevelopment Authority／data.gov.sg 的 Master Plan 2025 Planning Area Boundary (No Sea)](https://data.gov.sg/datasets/d_2cc750190544007400b2cfd5d7f53209/view) 数据，获取于 2026-10-12，依据 [Singapore Open Data Licence v1.0](https://data.gov.sg/open-data-licence) 使用。边界文件为原资料子集，地图为派生展示；保留此来源和许可说明，不暗示政府机构认可本项目。

地址依据 [NUS-ISS 官方到达说明](https://www.iss.nus.edu.sg/about-us/getting-to-nus-iss)，坐标依据 [SLA OneMap 完整地址查询](https://www.onemap.gov.sg/api/common/elastic/search?searchVal=25%20HENG%20MUI%20KENG%20TERRACE&returnGeom=Y&getAddrDetails=Y&pageNum=1)。NUS-ISS 仅用作课程模拟调度地点，不代表学校实际参与道路维修。
