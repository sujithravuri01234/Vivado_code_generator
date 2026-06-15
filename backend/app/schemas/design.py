from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TruthTableRow(BaseModel):
    inputs: dict[str, int | str]
    outputs: dict[str, int | str]


class NetworkElement(BaseModel):
    name: str
    source: str | None = None
    drain: str | None = None
    gate: str | None = None
    bulk: str | None = None
    kind: str | None = None


class DiagramNode(BaseModel):
    id: str
    type: str
    position: dict[str, float]
    data: dict[str, Any] = Field(default_factory=dict)


class DiagramEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str | None = None
    type: str | None = None


class VivadoReports(BaseModel):
    simulation_report: dict[str, Any] = Field(default_factory=dict)
    timing_report: dict[str, Any] = Field(default_factory=dict)
    utilization_report: dict[str, Any] = Field(default_factory=dict)
    power_report: dict[str, Any] = Field(default_factory=dict)
    log: dict[str, Any] = Field(default_factory=dict)
    artifacts: dict[str, Any] = Field(default_factory=dict)


class DesignContract(BaseModel):
    design_type: str = ""
    design_name: str = ""
    abstraction: str = ""
    modeling_style: str = "dataflow"
    implementation_profile: str = "combinational"
    gate_count: int = 0
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    truth_table: list[TruthTableRow] = Field(default_factory=list)
    boolean_equation: str = ""
    technology_node: str = ""
    pmos_network: list[NetworkElement] = Field(default_factory=list)
    nmos_network: list[NetworkElement] = Field(default_factory=list)
    transistor_sizing: dict[str, str] = Field(default_factory=dict)
    gate_level_design: dict[str, Any] = Field(default_factory=dict)
    verilog: str = ""
    testbench: str = ""
    vivado_results: VivadoReports = Field(default_factory=VivadoReports)
    vivado_status: str = ""
    diagram_json: dict[str, Any] = Field(default_factory=dict)
    documentation: str = ""
    fpga_implementation: dict[str, Any] = Field(default_factory=dict)
    knowledge_contexts: list[dict[str, Any]] = Field(default_factory=list)
    architecture: dict[str, Any] = Field(default_factory=dict)
    retrieved_context_summary: str = ""
    storage_status: str = ""
    storage_details: dict[str, Any] = Field(default_factory=dict)


class PromptRequest(BaseModel):
    prompt: str
    email: str | None = None
    design_hint: Literal["digital", "analog", "auto"] = "auto"
    technology_node: str | None = None
    modeling_style: Literal["dataflow", "behavioral", "gate_level", "structural"] = "dataflow"
    validate_vivado: bool = True
