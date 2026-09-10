"""jobs 模块声明：模块注册的唯一入口。"""
from app.core.module_registry import AppModule
from app.modules.jobs.router import router

module = AppModule(name="jobs", router=router)