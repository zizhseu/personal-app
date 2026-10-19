# 个人 App

本地个人应用，包含秋招投递管理、面试问答、笔试选择题、待办事项、基于简历的 AI 模拟面试，以及小红书面经搜索、图片识别和 AI 整理。前后端按功能模块组织，菜单和路由由模块注册表生成。

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

## 面经资料

在「面经资料 → 搜索与收集」连接本机采集组件，用小红书 App 扫码确认后搜索图文面经。勾选笔记保存正文和图片，执行本地 OCR、人工校对，再用设置中的模型提取附带原文引用的面试问题；确认后可加入问答。也支持直接粘贴正文手动导入。

图片识别需要在项目 conda 环境安装 `backend/requirements-experiences.txt`。采集组件可在界面安装启动，或运行 `python scripts/xhs_collector.py start|status|stop`。安装、搜索策略、保存规则与限制见 [面经功能说明](docs/experiences.md)。

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
