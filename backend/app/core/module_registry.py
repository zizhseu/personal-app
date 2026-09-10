"""模块注册机制：自动发现 app/modules/ 下的功能模块并挂载路由。

约定：每个模块包必须有一个 module.py，导出名为 module 的 AppModule 实例。
新增模块只需创建包目录，核心代码零改动。
"""
from dataclasses import dataclass, field
from importlib import import_module
from pkgutil import iter_modules
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from fastapi import FastAPI, APIRouter


@dataclass
class AppModule:
    """功能模块声明。"""

    name: str
    router: "APIRouter"
    # 可选启动钩子，预留扩展
    on_startup: Callable[[], None] | None = field(default=None)


def register_modules(app: "FastAPI") -> list[str]:
    """扫描并挂载全部模块，返回已加载的模块名列表。"""
    from app import modules as modules_pkg

    loaded: list[str] = []
    for info in sorted(iter_modules(modules_pkg.__path__), key=lambda m: m.name):
        if not info.ispkg:
            continue
        mod = import_module(f"app.modules.{info.name}.module")
        module: AppModule = mod.module
        if module.on_startup is not None:
            module.on_startup()
        app.include_router(module.router)
        loaded.append(module.name)
    return loaded