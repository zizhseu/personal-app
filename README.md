# 个人 App

本地个人应用，首个功能模块：**秋招投递管理（JobTracker）**。架构按功能模块划分，未来可扩展待办事项等模块。

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

## 如何新增一个功能模块（以「待办事项」为例）

1. **后端**：复制 `backend/app/modules/jobs/` 的文件结构到 `backend/app/modules/todo/`，实现 `module.py` 导出 `module` 实例即可——路由会被自动发现挂载，无需改任何核心代码。
2. **前端**：复制 `frontend/src/modules/jobs/` 到 `frontend/src/modules/todo/`，在 `frontend/src/modules/index.ts` 中 import 并加入数组即可——路由和侧边菜单自动生成。

## 数据

SQLite 数据库文件：`backend/data/app.db`（首次启动自动创建），备份整个文件即可。