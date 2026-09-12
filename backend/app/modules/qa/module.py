"""qa 模块声明。"""
from app.core.module_registry import AppModule
from app.modules.qa.router import router

module = AppModule(name="qa", router=router)