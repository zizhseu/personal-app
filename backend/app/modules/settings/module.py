"""设置模块声明。"""
from app.core.module_registry import AppModule
from app.modules.settings.router import router

module = AppModule(name="settings", router=router)
