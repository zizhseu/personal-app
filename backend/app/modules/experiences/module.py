"""面经模块声明。"""
from app.core.module_registry import AppModule
from app.modules.experiences.router import router

module = AppModule(name="experiences", router=router)
