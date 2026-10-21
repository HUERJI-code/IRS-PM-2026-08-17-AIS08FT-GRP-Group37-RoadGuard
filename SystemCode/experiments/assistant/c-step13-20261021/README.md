# C 第 13 步助手本地案例记录

22 条记录：10 个路线问题、11 个调整案例、1 条跨角色 HTTP 流程。所有数据合成；真实模型与 Google 调用均为 0。
路线问题采用预设证据选择的测试替身，仅验证指定方案、引用、版本、只读和拒答状态的传递，不能据此计算 GPT 准确率或回答充分率。响应中的 model_called 表示调用了 provider 抽象层；本记录的 real_model_called=false 才是是否调用真实模型的标识。

| 案例 | 输入 | 预期 | 实际 | 证据 |
| --- | --- | --- | --- | --- |
| a01 | 停用 crew-02 | disable | confirmed | [a01.json](a01.json) |
| a02 | 启用 crew-02 | enable | confirmed | [a02.json](a02.json) |
| a03 | 停用 crew-02 | cancel | cancelled | [a03.json](a03.json) |
| a04 | 停用 crew-02 | replay | confirmed | [a04.json](a04.json) |
| a05 | 停用 crew-02 | concurrent | confirmed | [a05.json](a05.json) |
| a06 | 停用 crew-02 | task_changed | failed | [a06.json](a06.json) |
| a07 | 停用 crew-02 | crew_changed | failed | [a07.json](a07.json) |
| a08 | 启用 crew-02 | noop | confirmed | [a08.json](a08.json) |
| a09 | 停用第二队 | 422; no crew mutation | unsupported_change | [a09.json](a09.json) |
| a10 | 封闭道路并直接提高任务优先级 | 422; no crew mutation | unsupported_change | [a10.json](a10.json) |
| a11 | 停用 crew-02 | failure_recovery | confirmed / succeeded | [a11.json](a11.json) |
| q01 | 四队分别负责什么任务？ | supported | supported | [q01.json](q01.json) |
| q02 | crew-01 的访问顺序是什么？ | supported | supported | [q02.json](q02.json) |
| q03 | 为什么从 NUS-ISS 出发？ | supported | supported | [q03.json](q03.json) |
| q04 | crew-01 的任务预计何时到达和完成？ | supported | supported | [q04.json](q04.json) |
| q05 | 有哪些未分配任务及原因？ | supported | supported | [q05.json](q05.json) |
| q06 | 哪个队最忙？请列出四队工作分钟供核对。 | supported | supported | [q06.json](q06.json) |
| q07 | GA 与 Greedy 哪项更好？ | insufficient_data | insufficient_data | [q07.json](q07.json) |
| q08 | 为什么这个方案已经过期？ | stale_plan | stale_plan | [q08.json](q08.json) |
| q09 | 当前矩阵是否来自 Google？ | supported | supported | [q09.json](q09.json) |
| q10 | 没有期限时能否判断延误？ | supported | supported | [q10.json](q10.json) |
| workflow | 巡查→审核→规划→施工队完成→重算→助手调整 | upload/review/plan/own-crew completion/stale/replan/change/replan | 完成；输入版本 2→3→4 | [workflow.json](workflow.json) |

预期标签：disable/enable=保存停用/启用；cancel=取消且输入不变；replay/concurrent=仅一次写入；task_changed/crew_changed=拒绝旧预览；noop=不增加输入版本；failure_recovery=失败保留队伍状态、同尝试不重算、新尝试成功、新应用实例恢复回执。

q07 的两方案优劣没有完整双方案输入，测试替身选择拒答；q08 的过期方案由服务端直接拒绝，未调用替身。q06 只提供四队分钟值，不声称模型已完成工作量排名推理。

完整原始输入、预期、实际响应、plan_id、输入版本、引用和摘要在逐例 JSON 中。凭据与会话未输出；合成账号 ID 只用于验证记录归属。run.json 记录本轮源文件摘要与基线提交，运行时生成的 ID/时间/耗时无需跨运行完全相同。
