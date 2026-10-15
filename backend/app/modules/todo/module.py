from app.core.module_registry import AppModule
from app.modules.todo.router import router

module = AppModule(name="todo", router=router)
