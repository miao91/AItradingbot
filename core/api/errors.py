"""
AI TradeBot - 统一错误处理模块

提供标准化的错误响应格式和错误码定义
"""
from enum import Enum
from typing import Any, Dict, Optional
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorCode(str, Enum):
    """错误码枚举"""

    # 通用错误 (1xxx)
    UNKNOWN_ERROR = "E1000"
    INVALID_REQUEST = "E1001"
    MISSING_PARAMETER = "E1002"
    INVALID_PARAMETER = "E1003"

    # 数据源错误 (2xxx)
    DATA_SOURCE_UNAVAILABLE = "E2000"
    TUSHARE_ERROR = "E2001"
    EXTERNAL_API_ERROR = "E2002"
    RATE_LIMIT_EXCEEDED = "E2003"

    # AI/LLM 错误 (3xxx)
    LLM_UNAVAILABLE = "E3000"
    LLM_TIMEOUT = "E3001"
    LLM_RESPONSE_ERROR = "E3002"
    AI_GENERATION_FAILED = "E3003"

    # 计算错误 (4xxx)
    VALUATION_FAILED = "E4000"
    SIMULATION_FAILED = "E4001"
    INVALID_PRICE = "E4002"
    HALLUCINATION_DETECTED = "E4003"

    # 系统错误 (5xxx)
    DATABASE_ERROR = "E5000"
    CACHE_ERROR = "E5001"
    GPU_ERROR = "E5002"
    SERVICE_UNAVAILABLE = "E5003"


class ErrorResponse(BaseModel):
    """标准错误响应"""
    success: bool = False
    error_code: str
    error_message: str
    detail: Optional[str] = None
    suggestion: Optional[str] = None
    request_id: Optional[str] = None


class APIError(HTTPException):
    """自定义 API 异常"""

    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        detail: Optional[str] = None,
        suggestion: Optional[str] = None,
    ):
        self.error_code = error_code
        self.message = message
        self.detail = detail
        self.suggestion = suggestion
        super().__init__(status_code=status_code, detail=message)


# 预定义的错误
class Errors:
    """预定义错误工厂"""

    @staticmethod
    def invalid_request(message: str = "请求参数无效", detail: str = None) -> APIError:
        return APIError(
            error_code=ErrorCode.INVALID_REQUEST,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )

    @staticmethod
    def missing_parameter(param: str) -> APIError:
        return APIError(
            error_code=ErrorCode.MISSING_PARAMETER,
            message=f"缺少必需参数: {param}",
            status_code=status.HTTP_400_BAD_REQUEST,
            suggestion=f"请提供 {param} 参数",
        )

    @staticmethod
    def invalid_parameter(param: str, reason: str = None) -> APIError:
        return APIError(
            error_code=ErrorCode.INVALID_PARAMETER,
            message=f"参数 {param} 无效",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=reason,
        )

    @staticmethod
    def data_source_unavailable(source: str = "数据源") -> APIError:
        return APIError(
            error_code=ErrorCode.DATA_SOURCE_UNAVAILABLE,
            message=f"{source}不可用",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            suggestion="请稍后重试或使用备用数据源",
        )

    @staticmethod
    def tushare_error(detail: str = None) -> APIError:
        return APIError(
            error_code=ErrorCode.TUSHARE_ERROR,
            message="Tushare 数据获取失败",
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
            suggestion="请检查 Tushare Token 是否有效",
        )

    @staticmethod
    def llm_unavailable(model: str = "AI 模型") -> APIError:
        return APIError(
            error_code=ErrorCode.LLM_UNAVAILABLE,
            message=f"{model}服务不可用",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            suggestion="请检查 API Key 是否有效",
        )

    @staticmethod
    def llm_timeout(model: str = "AI 模型") -> APIError:
        return APIError(
            error_code=ErrorCode.LLM_TIMEOUT,
            message=f"{model}响应超时",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            suggestion="请稍后重试",
        )

    @staticmethod
    def valuation_failed(reason: str = None) -> APIError:
        return APIError(
            error_code=ErrorCode.VALIDATION_FAILED,
            message="估值计算失败",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=reason,
            suggestion="请检查输入参数是否合理",
        )

    @staticmethod
    def simulation_failed(reason: str = None) -> APIError:
        return APIError(
            error_code=ErrorCode.SIMULATION_FAILED,
            message="蒙特卡洛模拟失败",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=reason,
        )

    @staticmethod
    def gpu_error(detail: str = None) -> APIError:
        return APIError(
            error_code=ErrorCode.GPU_ERROR,
            message="GPU 计算错误",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            suggestion="已自动切换到 CPU 模式",
        )


def create_error_response(
    error_code: ErrorCode,
    message: str,
    detail: str = None,
    suggestion: str = None,
) -> Dict[str, Any]:
    """创建标准错误响应字典"""
    return {
        "success": False,
        "error": {
            "code": error_code.value,
            "message": message,
            "detail": detail,
            "suggestion": suggestion,
        }
    }


def create_success_response(
    data: Any,
    message: str = "操作成功",
) -> Dict[str, Any]:
    """创建标准成功响应字典"""
    return {
        "success": True,
        "message": message,
        "data": data,
    }


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """API 错误处理器"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.error_code.value,
                "message": exc.message,
                "detail": exc.detail,
                "suggestion": exc.suggestion,
            }
        }
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """通用错误处理器"""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": ErrorCode.UNKNOWN_ERROR.value,
                "message": "服务器内部错误",
                "detail": str(exc) if str(exc) else None,
            }
        }
    )


__all__ = [
    "ErrorCode",
    "ErrorResponse",
    "APIError",
    "Errors",
    "create_error_response",
    "create_success_response",
    "api_error_handler",
    "generic_error_handler",
]
