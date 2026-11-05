"""Concrete plans reviewed before the operations they describe."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExecutionPlan(BaseModel):
    """Specify the operations and limits a human can approve.

    Attributes:
        title: Readable name of the proposed plan.
        objective: Intended outcome of executing the plan.
        steps: Concrete ordered operations, including commands where appropriate.
        inputs: Required materials and their known locations.
        parameters: Explicit settings, including assumptions and selected defaults.
        resources: Tools, environments, data and permissions required.
        budget: Expected time, compute, money or bounds on their use.
        stop_conditions: Conditions that end or interrupt execution.
        acceptance_criteria: Observable evidence used to assess the outcome.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    objective: str
    steps: list[str] = Field(min_length=1)
    inputs: list[str]
    parameters: list[str]
    resources: list[str]
    budget: str
    stop_conditions: list[str] = Field(min_length=1)
    acceptance_criteria: list[str] = Field(min_length=1)

    def markdown(self) -> str:
        """Render all approved plan fields for human review.

        Returns:
            A readable report that retains every structured plan field.
        """
        lines = [f"# {self.title}", f"Objective: {self.objective}"]
        for title, values in (
            ("Steps", self.steps), ("Inputs", self.inputs), ("Parameters", self.parameters),
            ("Resources", self.resources), ("Stopping conditions", self.stop_conditions),
            ("Acceptance criteria", self.acceptance_criteria),
        ):
            lines.append(f"## {title}")
            lines.extend(f"{index}. {value}" for index, value in enumerate(values, 1))
        lines.extend(["## Budget", self.budget])
        return "\n\n".join(lines)


class PlanningResult(BaseModel):
    """Return either a concrete plan or focused questions needed to form one.

    Attributes:
        plan: Complete reviewable plan when enough information is available.
        questions: Essential user-owned information needed to complete planning.
    """

    model_config = ConfigDict(extra="forbid")

    plan: ExecutionPlan | None
    questions: list[str]

    @model_validator(mode="after")
    def check_outcome(self) -> "PlanningResult":
        """Require one actionable planning outcome.

        Returns:
            A plan or nonempty focused questions.
        """
        if self.plan is None:
            if not self.questions or any(not question.strip() for question in self.questions):
                raise ValueError("Planning requires a plan or focused questions")
        elif self.questions:
            raise ValueError("Resolve blocking questions before submitting a complete plan")
        return self
