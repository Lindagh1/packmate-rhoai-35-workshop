from pydantic import BaseModel, Field


class BaggageRulesResult(BaseModel):
    warnings: list[str] = Field(default_factory=list)
    matched_rule_ids: list[str] = Field(default_factory=list)
    general_rules: list[str] = Field(default_factory=list)
    disclaimer: str
