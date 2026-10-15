from app.core.module_registry import AppModule
from app.modules.quiz.router import router

module = AppModule(name="quiz", router=router)