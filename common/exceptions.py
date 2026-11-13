"""业务层可主动抛出的异常，由 API 全局异常处理器转换为 Result。"""


class BusinessException(Exception):
    """可预期的业务失败；message 应是可以公开给客户端的信息。"""

    status_code = 400
    error = "BUSINESS_ERROR"

    def __init__(
        self,
        message: str = "业务处理失败",
        *,
        code: int | None = None,
        status_code: int | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = self.status_code if status_code is None else status_code
        self.code = self.status_code if code is None else code


class NotFoundException(BusinessException):
    """用户、Agent、会话或记忆等资源不存在。"""

    status_code = 404
    error = "NOT_FOUND"


class ConflictException(BusinessException):
    """业务明确判定的重复操作或资源状态冲突。"""

    status_code = 409
    error = "CONFLICT"
