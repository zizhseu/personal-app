"""代码手撕模块注册。"""
from app.core.module_registry import AppModule
from app.modules.coding.router import router

module = AppModule(name="coding", router=router)
