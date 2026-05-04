import pydantic


class EvalRunDeleteStatsDTO(pydantic.BaseModel):
    eval_runs_deleted: int
    tenants_deleted: int
