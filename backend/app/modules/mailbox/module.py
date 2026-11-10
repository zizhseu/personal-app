"""邮箱模块自动注册。"""
from app.core.module_registry import AppModule
from .router import router

module = AppModule(name="mailbox", router=router)
