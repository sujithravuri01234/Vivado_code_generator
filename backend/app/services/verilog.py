from __future__ import annotations

from app.services.design_library import (
    detect_circuit_kind,
    detect_supported_design,
    verilog_for,
)


def _sanitize_comment(text: str, limit: int = 120) -> str:
    cleaned = " ".join(text.split())
    return cleaned[:limit]


def generate_verilog_from_design_name(design_name: str, modeling_style: str = "dataflow") -> str:
    return verilog_for(design_name, modeling_style)


def generate_verilog_from_prompt(prompt: str, design_hint: str = "auto", modeling_style: str = "dataflow") -> str:
    design_type = detect_circuit_kind(prompt, design_hint)
    if design_type != "digital":
        return """module analog_wrapper(input wire IN_A, input wire IN_B, output wire OUT_Y);
    assign OUT_Y = IN_A & IN_B;
endmodule
"""

    design_name = detect_supported_design(prompt)
    if design_name == "unsupported_design":
        comment = _sanitize_comment(prompt)
        return f"""module custom_design(input wire A, input wire B, output wire Y);
    // Best-effort fallback for: {comment}
    assign Y = A & B;
endmodule
"""
    return verilog_for(design_name, modeling_style)


def generate_verilog_stub(design_type: str, prompt: str, modeling_style: str = "dataflow") -> str:
    return generate_verilog_from_prompt(prompt, design_type, modeling_style)
