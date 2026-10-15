# 个人 App

本地个人应用，包含秋招投递管理、面试问答、笔试选择题、待办事项和 AI 模拟面试。前后端按功能模块组织，菜单和路由由模块注册表生成。

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

`references/`、数据库、`.env`、依赖和本地运行产物不纳入 Git。提交前可用 `git status --short` 与 `git diff --cached --name-only` 核对待提交文件。

## 回归验证

在 `personal-app` conda 环境中，从 `backend` 目录运行：

```powershell
python -m unittest discover -s tests -v
```

测试使用独立内存数据库和模拟模型，不访问业务数据库或外部模型服务。从 `frontend` 目录运行 `npm run build`，执行完整类型检查和生产构建。

最近一次修复及浏览器实测范围见 [验证记录](docs/validation-2026-10-15.md)。
