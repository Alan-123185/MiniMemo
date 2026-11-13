"""FastAPI 请求异常处理，统一返回项目已有的 Result 格式。"""

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from loguru import logger
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from common.exceptions import BusinessException
from common.result import Result


async def business_exception_handler(request: Request, exc: BusinessException) -> JSONResponse:
    """将主动抛出的业务异常转换为指定状态码的响应。"""
    return JSONResponse(
        status_code=exc.status_code,
        content=Result(code=exc.code, message=exc.message, error=exc.error).model_dump(mode="json"),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """处理框架和业务代码抛出的 HTTP 异常，保留认证等响应头。"""
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content=jsonable_encoder(Result(
            code=exc.status_code,
            message=exc.detail if isinstance(exc.detail, str) else "请求处理失败",
            response=None if isinstance(exc.detail, str) else exc.detail,
            error="HTTP_ERROR",
        )),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """返回字段位置、校验说明和错误类型，不回传请求原值。"""
    errors = [
        {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(Result(
            code=422,
            message="请求参数校验失败",
            response=errors,
            error="VALIDATION_ERROR",
        )),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """未预期异常记录完整堆栈，对外返回通用错误信息。"""
    logger.opt(exception=exc).error("请求处理异常: {} {}", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=Result(
            code=500,
            message="服务器内部错误",
            error="INTERNAL_SERVER_ERROR",
        ).model_dump(mode="json"),
    )
