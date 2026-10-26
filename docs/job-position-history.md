# 岗位变更与阶段历史

## 使用

同一家公司的一条求职记录可以经历多个岗位。详情顶部显示当前岗位，下方轮次和状态历史分别显示该阶段当时的岗位。

例如：

| 阶段 | 岗位 | 结果 |
| --- | --- | --- |
| 原岗位初筛、笔试 | 岗位 A | 通过 |
| 原岗位面试 | 岗位 A | 未通过 |
| 更换岗位后初筛 | 岗位 B | 未开始 |

1. 进入投递详情，点击「更换岗位」，填写新岗位。
2. 默认勾选「重新从初筛开始」，保存后新增该岗位的初筛阶段及轮次，旧轮次、结果与复盘继续保留。相同名称再次投递，也可以开始新的独立流程。
3. 若新岗位继续当前阶段，取消该选项；例如仍处于面试阶段时，只新增新岗位的阶段记录，不借用旧岗位的面试结果。
4. 普通「编辑投递」更改岗位也会保留历史，表单可选择新岗位是否重新从初筛开始。仅修改备注或保存相同岗位，不会新增岗位流程。

投递列表及看板的当前结果、投递列表的截止时间只使用当前岗位流程。日程仍保留旧轮次，但展示轮次当时的岗位。切换岗位会清除上一岗位的 Offer 接受 / 拒绝决定；当前求职记录的其他基本资料保持既有编辑方式。

## 补录旧数据

旧版本只保存当前岗位，不能从数据库可靠还原曾被覆盖的岗位名称。升级时不把当前岗位填充成历史事实，旧阶段、轮次会显示「补录岗位」或「岗位未记录」。

- 点击状态变化中的岗位文字，可补录或更正该阶段岗位，同时更新明确关联到该阶段的轮次和结果快照；不会更改当前岗位。
- 也可在「编辑轮次 → 此轮岗位」单独补录或更正。若改成与原阶段冲突的岗位，会解除冲突关联，结果不会强行挂到另一岗位的阶段下。
- 无法确定所属阶段的结果会显示在「未归属阶段的结果记录」中，记录本身保留。
- 若当前岗位已在旧版本中被覆盖，可先补录旧阶段，再通过「更换岗位」为当前岗位重新开始独立流程。

## 保存规则

本功能属于后端业务历史持久化，与列表搜索、页码的前端会话记忆不同。

- `application.position` 为当前岗位，`position_version` 区分每次岗位流程。A → B → A 仍是三个不同的流程，不能仅靠名称判断归属。
- `status_history`、`interview_round`、`round_result_history` 保存岗位与流程代次快照。
- 轮次与结果保存 `status_history_id`；补记旧轮次的结果时优先归属旧阶段。新结果不依靠当前岗位名称或最新时间猜测旧记录的归属。
- 正向推进状态只联动当前岗位流程内的最新轮次，不将旧岗位结果改为通过。历史轮次仍可更新复盘和结果。
- 更换岗位支持 `expectedPositionVersion` 检查，陈旧表单返回 409；岗位流程递增使用数据库条件更新，避免同时改投时重复使用同一代次。

## 数据库升级与接口

后端启动自动补列，无新增业务表。新增字段为：

| 表 | 新增字段 |
| --- | --- |
| `application` | `position_version` |
| `status_history` | `position`、`position_version` |
| `interview_round` | `position`、`position_version`、`status_history_id` |
| `round_result_history` | `position`、`position_version`、`status_history_id` |

旧记录的代次初始为 1、岗位快照为空。一次性标记 `position_history_20261026` 只补有时间与状态依据的阶段关联，不猜测旧岗位名称；重复启动不覆盖人工补录。

`PUT /api/jobs/applications/{id}` 新增可选的 `restartProcess` 和 `expectedPositionVersion`。`PATCH /api/jobs/status-history/{id}/position` 保存 `{position}`，轮次更新支持可选 `{position}`；岗位长度上限为 100 字。阶段删除后关联置空，岗位快照保留；删除整条投递时仍按原级联关系清理其历史。

源码见 [业务逻辑](../backend/app/modules/jobs/service.py)、[数据库迁移](../backend/app/core/database.py)、[详情页](../frontend/src/modules/jobs/views/ApplicationDetailView.vue)、[历史归属](../frontend/src/modules/jobs/history.ts)。验证范围见 [验证记录](validation-position-history-2026-10-26.md)。
