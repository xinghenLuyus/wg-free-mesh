from typing import Generic, TypeVar

from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class ErrorBody(BaseModel):
    code: str
    message: str
    detail: dict[str, object] = Field(default_factory=dict)


class ApiResponse(BaseModel, Generic[DataT]):
    success: bool = True
    data: DataT


class ApiErrorResponse(BaseModel):
    success: bool = False
    error: ErrorBody


def ok(data: DataT) -> ApiResponse[DataT]:
    return ApiResponse(data=data)
