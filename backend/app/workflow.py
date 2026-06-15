from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.core.settings import settings
from app.schemas.design import DesignContract
from app.services.design_library import (
    abstraction_for,
    boolean_equation,
    build_documentation,
    build_gate_level_design,
    build_testbench,
    detect_circuit_kind,
    detect_supported_design,
    gate_count_for,
    generate_truth_table,
    fpga_implementation_plan,
    recommend_technology_node,
    transistor_network,
    transistor_sizing,
    render_verilog_for_request,
)
from app.services.diagram import build_react_flow_from_contract
from app.services.rag import KnowledgeRetriever
from app.services.supabase_store import CircuitRepository
from app.services.vivado import VivadoService
from app.services.verilog import generate_verilog_from_prompt


class DesignState(TypedDict, total=False):
    validate_vivado: bool
    prompt: str
    email: str
    design_hint: str
    modeling_style: str
    technology_node: str | None
    validate_vivado: bool
    result: DesignContract
    knowledge_contexts: list[dict[str, str]]


def analyze_requirements(state: DesignState) -> DesignState:
    prompt = state["prompt"]
    design_type = detect_circuit_kind(prompt, state.get("design_hint", "auto"))
    design_name = detect_supported_design(prompt) if design_type == "digital" else "analog_circuit"
    gate_count = gate_count_for(design_name) if design_type == "digital" else 0
    abstraction = abstraction_for(gate_count) if design_type == "digital" else "gate_level"
    truth_table = generate_truth_table(design_name) if design_type == "digital" else []
    inputs = list(truth_table[0].inputs.keys()) if truth_table else []
    outputs = list(truth_table[0].outputs.keys()) if truth_table else []
    sequential_keywords = [
        "flip flop",
        "flip-flop",
        "dff",
        "register",
        "counter",
        "fifo",
        "ram",
        "memory",
        "shift register",
        "fsm",
        "state machine",
        "uart",
        "spi",
        "i2c",
        "axi",
        "protocol",
        "timer",
        "divider",
    ]
    implementation_profile = "sequential" if any(keyword in prompt.lower() for keyword in sequential_keywords) else "combinational"
    if implementation_profile == "sequential":
        abstraction = "gate_level"

    contract = DesignContract(
        design_type=design_type,
        design_name=design_name,
        abstraction=abstraction,
        modeling_style=state.get("modeling_style", "dataflow"),
        implementation_profile=implementation_profile,
        gate_count=gate_count,
        technology_node=state.get("technology_node") or settings.default_technology_node,
        truth_table=truth_table,
        inputs=inputs,
        outputs=outputs,
    )
    return {"result": contract}


def retrieve_knowledge(state: DesignState) -> DesignState:
    contexts = KnowledgeRetriever().search(state["prompt"])
    result = state["result"]
    result.knowledge_contexts = contexts
    return {"result": result, "knowledge_contexts": contexts}


def build_architecture(state: DesignState) -> DesignState:
    result = state["result"]
    if result.design_type == "digital":
        if not result.technology_node:
            result.technology_node = recommend_technology_node(result.gate_count, result.abstraction)
        if result.abstraction == "transistor_level":
            pmos, nmos = transistor_network(result.design_name)
            result.pmos_network = pmos
            result.nmos_network = nmos
        result.boolean_equation = boolean_equation(result.design_name)
        result.gate_level_design = build_gate_level_design(
            result.design_name,
            result.inputs,
            result.outputs,
            result.abstraction,
        )
        result.transistor_sizing = transistor_sizing(result.technology_node, result.abstraction, result.design_name)
    else:
        result.boolean_equation = ""
        result.gate_level_design = {
            "abstraction": "analog",
            "components": ["R", "C", "MOS"],
            "connections": [],
        }
        result.technology_node = result.technology_node or settings.default_technology_node
    result.architecture = {
        "design_type": result.design_type,
        "design_name": result.design_name,
        "abstraction": result.abstraction,
        "modeling_style": result.modeling_style,
        "implementation_profile": result.implementation_profile,
        "gate_count": result.gate_count,
        "inputs": result.inputs,
        "outputs": result.outputs,
        "technology_node": result.technology_node,
        "boolean_equation": result.boolean_equation,
    }
    result.fpga_implementation = fpga_implementation_plan(result)
    return {"result": result}


def generate_verilog(state: DesignState) -> DesignState:
    result = state["result"]
    if result.design_type == "digital":
        if result.design_name == "unsupported_design":
            result.design_name = "custom_design"
            result.verilog = generate_verilog_from_prompt(state["prompt"], state.get("design_hint", "auto"), result.modeling_style)
            result.testbench = build_testbench(result)
            return {"result": result}
        result.verilog = render_verilog_for_request(result.design_name, result.modeling_style)
        result.testbench = build_testbench(result)
    else:
        result.verilog = """module analog_wrapper(input wire IN_A, input wire IN_B, output wire OUT_Y);
    assign OUT_Y = IN_A & IN_B;
endmodule
"""
        result.testbench = ""
    return {"result": result}


def validate_with_vivado(state: DesignState) -> DesignState:
    result = state["result"]
    vivado_reports = VivadoService().validate(result.verilog, result.testbench)
    result.vivado_results = vivado_reports
    result.vivado_status = vivado_reports.timing_report.get(
        "status",
        vivado_reports.artifacts.get("status", ""),
    )
    return {"result": result}


def generate_diagram(state: DesignState) -> DesignState:
    result = state["result"]
    result.diagram_json = build_react_flow_from_contract(result)
    result.documentation = build_documentation(result)
    if result.knowledge_contexts:
        result.retrieved_context_summary = "; ".join(
            f"{item.get('title', 'Knowledge')}: {item.get('snippet', '')[:120]}"
            for item in result.knowledge_contexts[:3]
        )
    return {"result": result}


def finalize_output(state: DesignState) -> DesignState:
    result = state["result"]
    if not result.knowledge_contexts:
        result.knowledge_contexts = state.get("knowledge_contexts", [])
    return {"result": result}


def persist_to_supabase(state: DesignState) -> DesignState:
    result = state["result"]
    details = CircuitRepository().save_contract(
        result,
        prompt=state.get("prompt", ""),
        email=state.get("email"),
    )
    result.storage_status = str(details.get("status", ""))
    result.storage_details = details
    if details.get("status") == "completed":
        result.architecture["supabase_storage"] = {
            "table": details.get("table", ""),
            "row_id": details.get("row_id", ""),
            "email": details.get("email", ""),
        }
    return {"result": result}


def build_graph():
    graph = StateGraph(DesignState)
    graph.add_node("analyze_requirements", analyze_requirements)
    graph.add_node("retrieve_knowledge", retrieve_knowledge)
    graph.add_node("build_architecture", build_architecture)
    graph.add_node("generate_verilog", generate_verilog)
    graph.add_node("validate_with_vivado", validate_with_vivado)
    graph.add_node("generate_diagram", generate_diagram)
    graph.add_node("finalize_output", finalize_output)
    graph.add_node("persist_to_supabase", persist_to_supabase)
    graph.set_entry_point("analyze_requirements")
    graph.add_edge("analyze_requirements", "retrieve_knowledge")
    graph.add_edge("retrieve_knowledge", "build_architecture")
    graph.add_edge("build_architecture", "generate_verilog")
    graph.add_edge("generate_verilog", "validate_with_vivado")
    graph.add_edge("validate_with_vivado", "generate_diagram")
    graph.add_edge("generate_diagram", "finalize_output")
    graph.add_edge("finalize_output", "persist_to_supabase")
    graph.add_edge("persist_to_supabase", END)
    return graph.compile()
