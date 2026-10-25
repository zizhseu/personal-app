# 个人 App

本地个人应用，包含秋招投递管理、面试问答、代码手撕、笔试选择题、待办事项、基于简历的 AI 模拟面试，以及小红书面经搜索、图片识别和 AI 整理。前后端按功能模块组织，菜单和路由由模块注册表生成。

## 技术栈

- 前端：Vue 3 + TypeScript + Vite + Element Plus + ECharts + Pinia
- 后端：FastAPI + SQLAlchemy 2.x + SQLite

## 快速开始

### 首次安装

双击 `scripts\setup.bat`，或手动执行：

```bash
# 后端：创建独立 conda 环境并安装依赖
conda create -n personal-app python=3.13 -y
conda activate personal-app
cd backend
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 前端
cd frontend
npm install
```

### 启动

双击 `scripts\start.bat`，或手动执行：

```bash
# 终端 1：后端（需 conda activate personal-app）
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 终端 2：前端
cd frontend
npm run dev
```

访问 http://localhost:5173 ，后端接口文档见 http://127.0.0.1:8000/docs

## 简历面试

1. 在「AI 面试」新增简历：直接粘贴文本，或导入 PDF、DOCX、TXT、Markdown 文件，核对提取的文字后保存。文件上限 5 MB，简历文本上限 30000 字；扫描图片版 PDF 需要先转成文字。
2. 选择简历，可填写目标岗位和考察方向，然后开始面试。面试官围绕简历中的具体项目和经历提问，根据回答继续追问。
3. 简历快照和已提交对话会保存到本地数据库。刷新或切换页面后，可以从面试记录继续；生成失败时可重试。
4. 完成至少一次作答后，选择「结束并生成复盘」。复盘展示逐题反馈、简历原文引用和原始回答；确认后可加入问答或待办，保存前可修改内容并选择分类。

在「设置 → 大模型」配置服务地址、API Key 和模型，或者连接 ChatGPT 账号。支持获取模型列表、测试连接和保存后立即生效，AI 面试与选择题解析共用此连接。尚未在界面保存时，继续使用 `backend/.env` 中的默认值，可参考 `backend/.env.example`。

ChatGPT 账号通过官方浏览器授权接入，需要符合官方开放范围、套餐与模型权限；应用不会接收账号密码。账号授权、API Key 的区别、保存规则和排错见 [大模型设置说明](docs/model-settings.md)。文件导入只做本地文本提取，开始面试和生成复盘时才调用配置的模型。语音播放默认关闭，可手动开启。

升级本版本时，在项目专用 conda 环境中重新运行 `pip install -r requirements.txt`（从 `backend` 目录），然后重启后端，新表会自动创建。功能契约、数据结构和实测范围见 [简历面试说明](docs/resume-interview.md)。

## 代码手撕

1. 在侧栏「代码手撕 → 全部题目」新建分类，例如算法、语言基础或项目手撕，再新增题目。
2. 打开题目即可在同一个工作区修改题目描述、来源、代码、思路复盘和复杂度，无需切换编辑模式。填写题目名称后，停止输入 1 秒自动保存，顶部显示保存状态；保存过程中可继续编写，也可用 `Ctrl+S` 立即补存。
3. Monaco 代码编辑器支持语法高亮、行号、自动缩进、括号配对、撤销、复制与自动换行。`Ctrl+Space` 或「补全」显示提示，`Tab` 接受提示；JavaScript / TypeScript 提供类型及成员提示，Python 等其他内置语言提供关键词、常用片段与当前代码中的词补全。
4. 使用难度、标签及「待练习 / 练习中 / 已掌握」状态管理题目；列表支持搜索、筛选和分页。可直接修改分类，分类内仍有题目时禁止删除分类。

内容保存在本地数据库，自动保存后刷新可恢复；切换应用内页面前会补存最新内容。失败时保留当前输入并提示重试，尚未保存成功时刷新或关闭会提醒。本模块用于记录，不执行提交的代码。升级后重启后端会自动创建 `coding_category`、`coding_item` 两张表，无需改写原有数据。

编辑器与语言 Worker 随前端构建，不依赖 CDN，不会将代码发给外部补全服务。更新依赖后从 `frontend` 目录运行 `npm install`。编辑器改版的实测范围见 [验证记录](docs/validation-coding-editor-2026-10-25.md)。

## 面经资料

在「设置 → 内容采集来源」选择小红书的「浏览器采集（MCP）」或「接口采集（CLI）」，分别扫码登录后，在「面经资料 → 搜索与收集」搜索图文面经。勾选笔记保存正文和图片，执行本地 OCR、人工校对，再用设置中的模型提取附带原文引用的面试问题；确认后可加入问答。也支持直接粘贴正文手动导入。

图片识别需要在项目 conda 环境安装 `backend/requirements-experiences.txt`。采集组件可在界面安装启动，或运行 `python scripts/xhs_collector.py start|status|stop`。安装、搜索策略、保存规则与限制见 [面经功能说明](docs/experiences.md)。

CLI 使用可选依赖 `backend/requirements-collectors.txt`，也可在连接弹窗中安装。两种方式的登录记录独立，切换只影响后续搜索；统一采集契约与以后接入其他平台的方法见 [内容来源说明](docs/content-sources.md)。

真实 CLI 搜索、样本正文 / 图片 / OCR、MCP 登录及两种方式切换的范围见 [统一来源验证记录](docs/validation-content-sources-2026-10-25.md)。

## 开发疑问与学习记录

开发过程中主动发现的问题、方案比较和原理追问统一保存在 [开发疑问与学习记录](docs/development-learning.md)，按原始提问、概念解释、实现阶段和验证依据整理，供项目复盘、简历与面试准备使用。

## 目录结构

```
backend/app/
├── main.py                  # 入口：CORS + 模块注册 + 建表
├── core/
│   ├── config.py            # 配置（端口、数据库、CORS）
│   ├── database.py          # engine / get_db / init_db
│   └── module_registry.py   # ★ 模块自动发现与路由挂载
├── shared/base.py           # 声明基类 + 时间戳混入
└── modules/jobs/            # 业务模块：秋招投递管理
    ├── module.py            # 模块声明（注册入口）
    ├── router.py / models.py / schemas.py / service.py / constants.py

frontend/src/
├── main.ts / App.vue
├── router/index.ts          # ★ 汇总各模块路由
├── layouts/BasicLayout.vue  # 布局壳（侧边菜单 + 主内容区）
├── shared/                  # 跨模块通用：axios 封装 / 类型 / 工具
└── modules/
    ├── index.ts             # ★ 模块注册表
    └── jobs/                # 秋招投递模块（views + components + api + store）
```

## 如何新增一个功能模块

1. **后端**：参考 `backend/app/modules/todo/` 创建独立模块，实现 `module.py` 并导出 `module` 实例，路由会被自动发现挂载。
2. **前端**：参考 `frontend/src/modules/todo/` 创建模块，在 `frontend/src/modules/index.ts` 中 import 并加入数组，路由和侧边菜单随之生成。

## 数据

SQLite 数据库文件：`backend/data/app.db`（首次启动自动创建），备份整个文件即可。

### 版本升级与数据库兼容

后端启动时会自动执行幂等迁移（补列 / 数据修正），通常无需手动操作。各版本的功能更新与**数据库结构变更明细**见 [CHANGELOG.md](CHANGELOG.md)——升级前校对或让 AI 辅助修改数据库时，请先阅读该文件（含已知残留列与枚举变更说明）。

`references/`、数据库、`.env`、依赖和本地运行产物不纳入 Git。模型配置和账号令牌保存在 `backend/data/*.private`，同样排除在 Git 外；Windows 使用当前用户的 DPAPI 保护内容，不能复制到另一个 Windows 用户后直接使用。提交前可用 `git status --short` 与 `git diff --cached --name-only` 核对待提交文件。

## 回归验证

在 `personal-app` conda 环境中，从 `backend` 目录运行：

```powershell
python -m unittest discover -s tests -v
```

测试使用独立内存数据库、临时私有配置和模拟模型，不访问业务数据库或外部模型服务。从 `frontend` 目录运行 `npm run build`，执行完整类型检查和生产构建。

最近一次修复及浏览器实测范围见 [验证记录](docs/validation-2026-10-15.md)。
模型设置与账号授权的新增验证见 [模型设置验证记录](docs/validation-model-settings-2026-10-19.md)。
小红书真实搜索、采集、OCR 和面经整理流程的验证见 [面经功能验证记录](docs/validation-experiences-2026-10-19.md)。
