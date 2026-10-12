# 范围、基地与四队场景

document_id：`rg-kb-scope`；document_version：`1`；owner：`A`。

<a id="scope-baseline"></a>
## 项目任务范围

classification：`confirmed_project_fact`。citation_id：`rg-kb-scope#scope-baseline`。

维修任务范围是新加坡 Jurong East 与 Jurong West 的 URA MP2025 冻结多边形并集，版本 `jurong-je-jw-mp2025-v1`。按完整多边形覆盖点，包含外边缘和孔洞边缘、排除孔洞内部；外接矩形不足以判定有效任务。经纬度按 WGS84 十进制度传入，GeoJSON 顺序为 longitude、latitude。照片与位置分别提交，不证明照片来自 Jurong。

来源：[src-project-config](../../config/project.example.json)、[src-boundary](../../../Miscellaneous/geography/jurong-boundary-mp2025.geojson)、[src-geography-code](../roadguard/geography.py)、[context-workflow-guide](../../../Miscellaneous/INSPECTION_REVIEW_TASK_WORKFLOW.md)。

<a id="depot-crews"></a>
## 模拟部门、基地与队伍

classification：`confirmed_project_fact`。citation_id：`rg-kb-scope#depot-crews`。

一个虚构维修部门使用四支模拟工程队：`crew-01`、`crew-02`、`crew-03`、`crew-04`。共享起点是 NUS-ISS，25 Heng Mui Keng Terrace，坐标 latitude `1.292149`、longitude `103.776551`，基地版本 `nus-iss-v1`。这是在真实地址上的模拟起点，不是 NUS-ISS 的真实维修运营。

该指定基地允许位于任务区域外，基地到首个任务的行程必须计入；路线可以离开 JE/JW。例外只针对基地，使用 NUS-ISS 坐标提交维修任务仍会被拒绝。建筑参考点尚未核验为车辆出入口；是否返回基地仍是 null/待确认，不能默认为不返回。四队配置已确定，不表示工程队服务和规划算法已经实现。

来源：[src-project-config](../../config/project.example.json)、[src-depot](../../../Miscellaneous/geography/nus-iss-depot.geojson)、[context-scope](../../../Miscellaneous/PROJECT_SCOPE.md)。

<a id="road-evidence"></a>
## 道路声明的证据边界

classification：`confirmed_project_fact`。citation_id：`rg-kb-scope#road-evidence`。

项目只接受符合排除条件的公共机动车道路任务，排除快速路主线/匝道、私人或受限内部道路。当前请求必须声明 `road_type="public_motor_road"`，记录来源 `road_type_source="user_declared"`；其他声明被拒绝。

这只是调用者声明与范围校验，不是道路网络、道路许可或实时通行状态的自动核验。仅凭通过上传/多边形校验不能断言某点允许真实维修或车辆通行；需要 A/B 后续核验材料，不得借基地例外推断任务点例外。

来源：[src-project-config](../../config/project.example.json)、[src-geography-code](../roadguard/geography.py)、[src-workflow-schema](../roadguard/schemas/workflow.py)、[context-workflow-guide](../../../Miscellaneous/INSPECTION_REVIEW_TASK_WORKFLOW.md)。
