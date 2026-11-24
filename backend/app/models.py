from typing import Literal
from pydantic import BaseModel, Field

Operation = Literal["simplify", "expand", "factor", "solve", "system", "limit", "differentiate", "integrate", "definite_integral", "plot", "revolution"]

class MathRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=600)
    operation: Operation
    latex: str | None = Field(default=None, max_length=600)
    operation_explicit: bool = False
    variable: str = "x"
    order: int = Field(default=1, ge=1, le=5)
    point: str | None = None
    direction: Literal["+", "-", "+-"] = "+-"
    lower: str | None = None
    upper: str | None = None
    second_expression: str | None = None
    axis: Literal["x", "y"] = "x"
    axis_value: str = "0"

class Step(BaseModel):
    number: int
    rule: str
    before_latex: str
    after_latex: str
    explanation: str
    verified: bool | None = None

class MathResponse(BaseModel):
    request_id: str
    expression: str
    operation: Operation
    status: Literal["solved", "unsupported", "error"]
    result_latex: str | None = None
    result_text: str | None = None
    steps: list[Step] = []
    verification: Literal["result_verified", "procedure_verified", "procedure_partial", "procedure_unavailable", "unverified", "unsupported"] = "unverified"
    warnings: list[str] = []
    plot: dict | None = None
    solid: dict | None = None
