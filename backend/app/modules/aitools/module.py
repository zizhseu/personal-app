"""aitools 模块声明。"""
from app.core.module_registry import AppModule
from app.modules.aitools.router import router

module = AppModule(name="aitools", router=router)