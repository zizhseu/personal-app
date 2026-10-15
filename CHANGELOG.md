# 更新记录（CHANGELOG）

> 本文件记录各版本的功能更新与**数据库结构变更**，供使用者（或协助升级的 AI）在升级、校对数据库时参考。
>
> **自动迁移说明**：后端启动时会执行 `backend/app/core/database.py` 中 `init_db()` 的幂等迁移链（补列 / 表重建 / 数据修正按顺序编写，可重复执行），正常情况下无需手动操作。本文档用于人工或 AI 校对时核对每个版本的预期结构。
>
> **已知残留（旧库兼容注意）**：
> - `application` 表的 `channel`、`location`、`reject_stage` 列自 v1.1.0 起废弃，旧库中**物理保留**但代码不再读写（SQLite 删列成本高，刻意保留）。
> - `interview_round.result` 的旧枚举值 `pending` 已被迁移拆分为 `completed` / `not_started`，不再出现。
> - 状态枚举旧值 `applied` / `viewed` 已被 v1.1.0 迁移合并为 `screening`；`assessment`（测评）/ `written_test`（笔试）已被 v1.3.0 迁移合并为 `rescreen`（复筛），均不再出现。

---

## v1.4.1（2026-10-15）

### 修复
- 新库不再读取已废弃的 `application.location`；初始化内置问答分类时补齐时间戳，支持首次启动和重复启动。
- 旧问答表重建时保留 `related_ids`，避免升级后丢失关联题目。
- AI 面试和题目解析请求的等待时间与后端一致：前端 130 秒，后端整次调用上限 120 秒；模型超时、连接失败和异常响应分别返回可识别的错误，避免回传上游调试正文。
- AI 候选题、新增及编辑共用答案约束；校验题干、2–8 个非空选项、严格整数答案下标以及单选/多选数量。无效模型响应不会进入预览；无效编辑不会改写原题。
- 修复全项目类型检查发现的类型缺失、空值处理、列表排序索引和 Offer 结果类型问题。
- 修复日程标签参数警告，以及问答、选择题页面在窄屏下的按钮和工具栏溢出。

### 界面
- 参考 OfferPilot 的浅紫灰背景、白色侧栏、靛紫色交互与卡片层次；延续现有模块、分类和业务流程。
- 顶部用当前位置和秋招进度替代重复的横向菜单；导航入口统一保留在侧栏。
- 分类操作改用可聚焦按钮；窄屏使用支持焦点管理与关闭操作的抽屉导航，保持键盘焦点及减少动画偏好支持。

### 验证与数据
- 新增启动、旧库迁移、模型异常和题目校验回归，连同原有待办用例共 20 项通过。
- 完整前端类型检查和生产构建通过；浏览器验证范围见 [验证记录](docs/validation-2026-10-15.md)。
- 本版本未新增业务表或业务列；`references/`、数据库、本地配置和运行目录继续排除在版本控制之外。

---

## v1.4.0（2026-09-20，开发中）

### 功能
- 看板「状态分布」右侧新增「结果分布」饼图，按投递列表当前结果口径统计，每条投递计一次；Offer 待决定与未记录结果单独展示。
- 新增「待办事项」顶级侧栏：目录的新建、重命名和删除统一放在侧栏；正文支持待办新增、编辑、删除、完成及重新打开，可填写备注与截止时间，自动记录完成时间。支持搜索、状态筛选和每页 5 条固定高度分页；非空目录不可直接删除。
- 新增「笔试选择」模块：侧栏顶级分组，分类支持自定义增删改；题目支持单选 / 多选，分为问题区 / 答案区 / 解析区
- 答案与解析的显示时机可配置（设置页）：立即显示 / 作答后显示（判定对错）/ 手动查看
- 题目支持手动录入，也支持 **AI 解析导入**：粘贴任意格式的题目文本，LLM 自动提取题干 / 选项 / 答案 / 解析，预览勾选后批量入库

### 数据库变更
| 表 | 变更 | 说明 |
|---|---|---|
| `quiz_category` | **新表** | 笔试选择分类。字段：`id`、`name`(UNIQUE) + 时间戳 |
| `todo_category` | **新表** | 待办目录。字段：`id`、`name`(VARCHAR(50), UNIQUE)、`created_at`、`updated_at`。模块自动注册后由 `create_all` 建表，无需修改既有数据 |
| `todo_item` | **新表** | 待办内容。字段：`id`、`category_id`(FK→todo_category, RESTRICT)、`title`(VARCHAR(200))、`note`(TEXT 可空)、`due_at`(DATETIME 可空)、`completed`(BOOLEAN)、`completed_at`(DATETIME 可空) + 本地时间戳。启动时由 `create_all` 自动建表，已有目录保留；完成时自动打点，重新打开时清空完成时间 |
| `quiz_item` | **新表** | 选择题。字段：`id`、`category_id`(FK→quiz_category, RESTRICT)、`question`(TEXT)、`options`(JSON 选项文本数组)、`answer`(JSON 正确选项下标数组)、`qtype`(single/multi)、`analysis`(TEXT 可空) + 时间戳 |

> 设置（答案显示时机）存浏览器 localStorage，不涉及数据库。

---

## v1.3.0（2026-09-16，commit 9547adf）

### 功能
- 详情页「状态变化」升级为二级目录：展开查看该状态期间的轮次结果变化，一级 / 二级条目均可手动删除（新增删除接口）
- 详情页新增相关题目：自动相关（标签集合一致）+ 手动相关（有向图，三档筛选）
- 全局设置模块（侧栏左下角入口，偏好存浏览器 localStorage，不涉及数据库）
- 八股详情支持批量编辑标签（添加 / 移除）、标签筛选（含 / 排除 / 无标签）
- 时间统一修正为本地时间（详见下方时区修正）
- **状态模型再调整**：测评 / 笔试 / AI 面试统一归为新状态「复筛（rescreen）」，位于初筛与面试之间（各家流程顺序不固定，可来回切换）；轮次类型不变（测评 / 笔试 / AI 面试 / 其他）

### 数据库变更
| 表 | 变更 | 说明 |
|---|---|---|
| `round_result_history` | **新表** | 轮次结果变化历史。字段：`id`、`round_id`(FK→interview_round, CASCADE)、`application_id`(FK→application, CASCADE)、`status`(变化时的投递状态)、`from_result`(可空)、`to_result`、`changed_at` + 时间戳 |
| `qa_item` | 补列 `related_ids JSON` | 手动相关题目的有向边（指向谁的 id 列表）。曾短暂以列名 `related` 创建，迁移会自动改名为 `related_ids` |
| 全部表 | 数据修正：时区 | 旧数据由 SQLite `CURRENT_TIMESTAMP` 生成的是 **UTC**，迁移统一 +8h 修正为本地时间（含 `created_at`/`updated_at`/`changed_at`）。仅执行一次，以 `_migration_flags` 表中的标记防重跑 |
| `round_result_history` | 数据回填 | 历史表为空时，把既有轮次的结果与 `result_changed_at` 补录为初始历史记录（幂等） |
| `application` / `status_history` / `round_result_history` | 数据修正：状态合并 | 旧状态值 `assessment`（测评）、`written_test`（笔试）统一迁移为 `rescreen`（复筛），三张表同步 |

> 代码侧同时把 `TimestampMixin` 与历史表的 `changed_at` 默认值从 `server_default=func.now()`（UTC）改为 Python `datetime.now()`（本地时间），此后新数据不再需要修正。

---

## v1.2.0（2026-09-15，commit d185696）

### 功能
- 新增 AI 工具模块：AI 面试（LLM 面试官 + edge-tts 语音 + Web Speech 实时识别），配置走 `backend/.env`（模板见 `.env.example`）
- 投递状态模型重构（前端枚举与联动）：状态精简为 初筛/测评/笔试/面试/Offer；轮次结果细化为 未开始/已完成/通过/未通过/未参加 等
- 状态正向推进时最新轮次自动置「通过」，轮次结果修改自动打点时间
- 日程页改为 待办/已办/过期 三容器，待办按截止紧急度变色
- 面试八股：批量勾选与批量打标签、删除

### 数据库变更
| 表 | 变更 | 说明 |
|---|---|---|
| `interview_round` | 补列 `result_changed_at DATETIME` | 结果最后一次被修改的时间 |
| `interview_round` | 补列 `start_at DATETIME`、`duration_minutes INTEGER` | 计划时间拆分为开始时间 + 持续时长，`scheduled_at` 变为后端计算的截止时间（= 开始 + 持续）。旧库无 `start_at` 时自动以旧 `scheduled_at` 回填 |
| `interview_round` | 数据修正：枚举 | 旧值 `pending` 按截止时间是否已过拆分为 `completed` / `not_started` |
| `status_history` | 数据修正：初始化 | 没有任何状态历史的投递，按其创建时间补录一条初始状态记录 |
| — | 新模块 `aitools` | 无新增表；LLM 配置从 `backend/.env` 读取（不入库） |

---

## v1.1.0（2026-09-10，commit 1356e22）

### 功能
- 新增面试八股模块：分类（侧栏动态管理）、题目导入（Markdown `##` 解析）、标签、掌握状态、最后阅读时间
- 投递字段调整：渠道改为投递链接 + 意向 Base 多选城市；状态模型重构（7 态 → 5 态）；Offer 决定（接受 / 拒绝）

### 数据库变更
| 表 | 变更 | 说明 |
|---|---|---|
| `qa_category` | **新表** | 分类实体。字段：`id`、`name`(UNIQUE) + 时间戳 |
| `qa_item` | **新表** | 题目。字段：`id`、`category_id`(FK→qa_category, RESTRICT)、`question`、`answer`(TEXT)、`tags JSON`、`status`、`last_read_at` + 时间戳 |
| `qa_item` | 表重建 | 移除早期 `category` 列（NOT NULL 字符串，已废弃），数据迁移到 `category_id` |
| `qa_item` | 数据修正 | 旧 `category` 字符串值（resume/backend/agent）回填为对应分类 id；初始化内置分类「简历项目 / 后端中间件 / Agent」 |
| `application` | 补列 `base JSON`、`offer_decision VARCHAR(20)` | 意向城市多选、Offer 决定。旧 `location` 的文本按分隔符拆分回填进 `base` |
| `application` | 数据修正：状态合并 | `applied` / `viewed` → `screening`（`application.status` 与 `status_history.status` 同步） |

---

## v1.0.0（2026-09-08，commit 856a6de）

### 功能
- 首个版本：简历投递管理模块（投递列表 / 详情 / 流程轮次时间线 / 看板 / 日程）
- 模块化架构：后端自动扫描注册模块路由，前端模块注册表派生路由与菜单

### 数据库变更
| 表 | 变更 | 说明 |
|---|---|---|
| `application` | **新表** | 投递记录。初始含 `channel`/`location`/`reject_stage`（后废弃），`status` 初值 `applied` |
| `interview_round` | **新表** | 流程轮次。含 `start_at`/`duration_minutes`/`scheduled_at`(截止)/`result`(默认 `pending`)/`review_note` |
| `schedule_event` | **新表** | 自定义日程（宣讲会等，`application_id` 可空，投递删除仅断开关联） |
| `status_history` | **新表** | 状态变化记录，每次状态变更追加一行 |

> SQLite 约定：外键级联依赖 `PRAGMA foreign_keys=ON`（`database.py` 已在连接事件中开启）；新表由 `create_all` 自动创建，旧表补列走迁移链。
