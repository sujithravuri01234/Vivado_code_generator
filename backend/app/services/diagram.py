from __future__ import annotations

from typing import Any


def _get(source: Any, key: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _name(contract: Any) -> str:
    return str(_get(contract, "design_name", _get(contract, "title", "logic"))).strip().lower()


def _display(contract: Any) -> str:
    return str(_get(contract, "design_name", _get(contract, "title", "Logic"))).strip()


def _inputs(contract: Any) -> list[str]:
    raw = _get(contract, "inputs", None) or _get(contract, "input_names", None)
    if raw:
        return [str(item) for item in raw]
    if "xor" in _name(contract):
        return ["A", "B"]
    return ["A", "B"]


def _output(contract: Any) -> str:
    return str(_get(contract, "output_name", _get(contract, "output", "Y"))).strip() or "Y"


def _base_gate(name: str) -> str:
    if "nand" in name:
        return "nand"
    if "nor" in name:
        return "nor"
    if "xor" in name:
        return "xor"
    if "and" in name:
        return "and"
    if "or" in name:
        return "or"
    return "logic"


def _simple_gate(name: str) -> bool:
    return any(token in name for token in ("nand", "nor", "xor", "and", "or"))


def _node(id_: str, type_: str, x: int, y: int, label: str, **data: Any) -> dict[str, Any]:
    return {
        "id": id_,
        "type": type_,
        "position": {"x": x, "y": y},
        "data": {"label": label, **data},
    }


def _edge(source: str, target: str, label: str = "", **data: Any) -> dict[str, Any]:
    return {
        "id": f"{source}-{target}-{label or 'link'}",
        "source": source,
        "target": target,
        "label": label,
        "data": data,
    }


def _text(x: int, y: int, text: str, size: int = 18, color: str = "#6ec8ff", anchor: str = "start", weight: int = 700) -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" '
        f'font-family="Arial, Helvetica, sans-serif" font-weight="{weight}" '
        f'text-anchor="{anchor}">{text}</text>'
    )


def _line(x1: int, y1: int, x2: int, y2: int, color: str = "#7fb3ff", width: int = 3, dash: str = "") -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" stroke-linecap="round"{dash_attr} />'


def _circle(cx: int, cy: int, r: int, fill: str, stroke: str = "none", width: int = 0) -> str:
    sw = f' stroke="{stroke}" stroke-width="{width}"' if stroke != "none" else ""
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"{sw} />'


def _rect(x: int, y: int, w: int, h: int, fill: str = "none", stroke: str = "#7fb3ff", width: int = 3, rx: int = 10) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" />'


def _pmos_symbol(x: int, y: int, gate: str, label: str) -> str:
    return f"""
    <g>
      {_rect(x - 55, y - 18, 110, 36, fill="#1c2b51", stroke="#7fb3ff", width=3, rx=10)}
      {_line(x - 90, y, x - 55, y)}
      {_line(x + 55, y, x + 90, y)}
      {_line(x, y - 36, x, y - 18)}
      {_circle(x - 60, y, 5, "#d9ecff")}
      {_circle(x + 60, y, 5, "#d9ecff")}
      {_text(x - 24, y - 28, label, size=19, color="#d9ecff", anchor="middle")}
      {_text(x, y + 36, gate, size=18, color="#ff5aa5", anchor="middle")}
      {_circle(x - 82, y - 2, 4, "#7fb3ff")}
    </g>
    """


def _nmos_symbol(x: int, y: int, gate: str, label: str) -> str:
    return f"""
    <g>
      {_rect(x - 55, y - 18, 110, 36, fill="#291d4f", stroke="#7fb3ff", width=3, rx=10)}
      {_line(x - 90, y, x - 55, y)}
      {_line(x + 55, y, x + 90, y)}
      {_line(x, y - 36, x, y - 18)}
      {_circle(x - 60, y, 5, "#d9ecff")}
      {_circle(x + 60, y, 5, "#d9ecff")}
      {_text(x - 24, y - 28, label, size=19, color="#d9ecff", anchor="middle")}
      {_text(x, y + 36, gate, size=18, color="#ff5aa5", anchor="middle")}
    </g>
    """


def _nand_svg(inputs: list[str], output_name: str, title: str) -> str:
    a, b = (inputs + ["B"])[:2]
    return f"""
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="100%" height="100%">
      <rect width="1280" height="720" fill="#0b1220"/>
      {_line(120, 100, 1210, 100, color="#6ec8ff", width=5)}
      {_text(128, 82, "VDD", size=22, color="#6ec8ff", anchor="start")}
      {_circle(1040, 100, 5, "#6ec8ff")}
      {_line(1040, 100, 1040, 140, color="#6ec8ff", width=3)}
      {_line(1040, 140, 1040, 330, color="#6ec8ff", width=3, dash="12 10")}
      {_circle(1040, 380, 12, "#8f78ff")}
      {_text(1070, 388, output_name, size=22, color="#ffffff", anchor="start")}
      {_line(1040, 392, 1040, 530, color="#8aa0c8", width=3, dash="12 10")}
      {_line(120, 640, 1210, 640, color="#8aa0c8", width=5)}
      {_text(128, 680, "GND", size=22, color="#8aa0c8", anchor="start")}

      {_text(170, 200, "PMOS Network", size=22, color="#ffffff", anchor="start")}
      {_text(170, 470, "NMOS Network", size=22, color="#ffffff", anchor="start")}

      {_text(260, 170, a, size=22, color="#6ec8ff", anchor="middle")}
      {_text(540, 170, b, size=22, color="#6ec8ff", anchor="middle")}
      {_line(260, 170, 260, 214, color="#6ec8ff", width=3)}
      {_line(540, 170, 540, 214, color="#6ec8ff", width=3)}

      {_text(260, 548, a, size=22, color="#6ec8ff", anchor="middle")}
      {_text(540, 548, b, size=22, color="#6ec8ff", anchor="middle")}
      {_line(260, 548, 260, 494, color="#6ec8ff", width=3)}
      {_line(540, 548, 540, 494, color="#6ec8ff", width=3)}

      <g transform="translate(0,0)">
        {_pmos_symbol(270, 260, a, "P1")}
        {_pmos_symbol(520, 260, b, "P2")}
        {_line(320, 260, 470, 260, color="#8aa0c8", width=4)}
        {_line(320, 260, 320, 220, color="#8aa0c8", width=4)}
        {_line(470, 260, 470, 220, color="#8aa0c8", width=4)}
        {_line(320, 220, 470, 220, color="#8aa0c8", width=4)}
        {_line(320, 220, 320, 100, color="#8aa0c8", width=4)}
        {_line(470, 220, 470, 100, color="#8aa0c8", width=4)}
        {_line(470, 220, 620, 220, color="#8aa0c8", width=4)}
        {_line(620, 220, 620, 100, color="#8aa0c8", width=4)}
        {_line(470, 220, 470, 310, color="#8aa0c8", width=4)}
        {_line(620, 220, 620, 310, color="#8aa0c8", width=4)}
        {_line(470, 310, 620, 310, color="#8aa0c8", width=4)}
        {_line(470, 310, 470, 380, color="#8aa0c8", width=4)}
        {_line(620, 310, 620, 380, color="#8aa0c8", width=4)}
        {_line(470, 380, 620, 380, color="#8aa0c8", width=4)}
        {_line(620, 380, 1040, 380, color="#8aa0c8", width=4)}
      </g>

      <g transform="translate(0,0)">
        {_nmos_symbol(320, 540, a, "N1")}
        {_nmos_symbol(470, 540, b, "N2")}
        {_line(370, 540, 520, 540, color="#8aa0c8", width=4)}
        {_line(370, 540, 370, 595, color="#8aa0c8", width=4)}
        {_line(520, 540, 520, 595, color="#8aa0c8", width=4)}
        {_line(370, 595, 520, 595, color="#8aa0c8", width=4)}
        {_line(370, 595, 370, 640, color="#8aa0c8", width=4)}
        {_line(520, 595, 520, 640, color="#8aa0c8", width=4)}
        {_line(520, 595, 1040, 595, color="#8aa0c8", width=4)}
        {_line(370, 595, 370, 530, color="#8aa0c8", width=4)}
        {_line(520, 595, 520, 530, color="#8aa0c8", width=4)}
      </g>

      {_text(900, 232, f"{output_name} = {a} {b}", size=24, color="#ff5aa5", anchor="start")}
      {_text(900, 270, "PMOS in parallel", size=18, color="#8aa0c8", anchor="start", weight=600)}
      {_text(900, 300, "NMOS in series", size=18, color="#8aa0c8", anchor="start", weight=600)}
      {_text(900, 344, "Output node", size=18, color="#8f78ff", anchor="start", weight=600)}
      {_text(420, 690, title, size=20, color="#d9ecff", anchor="middle")}
    </svg>
    """


def _nor_svg(inputs: list[str], output_name: str, title: str) -> str:
    a, b = (inputs + ["B"])[:2]
    return f"""
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="100%" height="100%">
      <rect width="1280" height="720" fill="#0b1220"/>
      {_line(120, 100, 1210, 100, color="#6ec8ff", width=5)}
      {_text(128, 82, "VDD", size=22, color="#6ec8ff", anchor="start")}
      {_circle(1040, 100, 5, "#6ec8ff")}
      {_line(1040, 100, 1040, 145, color="#6ec8ff", width=3)}
      {_circle(1040, 380, 12, "#8f78ff")}
      {_text(1070, 388, output_name, size=22, color="#ffffff", anchor="start")}
      {_line(1040, 392, 1040, 530, color="#8aa0c8", width=3, dash="12 10")}
      {_line(120, 640, 1210, 640, color="#8aa0c8", width=5)}
      {_text(128, 680, "GND", size=22, color="#8aa0c8", anchor="start")}
      {_text(170, 200, "PMOS Network", size=22, color="#ffffff", anchor="start")}
      {_text(170, 470, "NMOS Network", size=22, color="#ffffff", anchor="start")}
      {_text(260, 170, a, size=22, color="#6ec8ff", anchor="middle")}
      {_text(540, 170, b, size=22, color="#6ec8ff", anchor="middle")}
      {_line(260, 170, 260, 214, color="#6ec8ff", width=3)}
      {_line(540, 170, 540, 214, color="#6ec8ff", width=3)}
      {_text(260, 548, a, size=22, color="#6ec8ff", anchor="middle")}
      {_text(540, 548, b, size=22, color="#6ec8ff", anchor="middle")}
      {_line(260, 548, 260, 494, color="#6ec8ff", width=3)}
      {_line(540, 548, 540, 494, color="#6ec8ff", width=3)}
      {_pmos_symbol(410, 260, a, "P1")}
      {_pmos_symbol(410, 360, b, "P2")}
      {_line(410, 224, 410, 310, color="#8aa0c8", width=4)}
      {_line(410, 310, 410, 410, color="#8aa0c8", width=4)}
      {_line(410, 410, 410, 100, color="#8aa0c8", width=4)}
      {_line(410, 410, 1040, 410, color="#8aa0c8", width=4)}
      {_nmos_symbol(320, 540, a, "N1")}
      {_nmos_symbol(520, 540, b, "N2")}
      {_line(370, 540, 470, 540, color="#8aa0c8", width=4)}
      {_line(370, 540, 370, 640, color="#8aa0c8", width=4)}
      {_line(470, 540, 470, 640, color="#8aa0c8", width=4)}
      {_line(370, 540, 370, 410, color="#8aa0c8", width=4)}
      {_line(470, 540, 470, 410, color="#8aa0c8", width=4)}
      {_line(470, 540, 1040, 540, color="#8aa0c8", width=4)}
      {_text(900, 232, f"{output_name} = {a} + {b}", size=24, color="#ff5aa5", anchor="start")}
      {_text(900, 270, "PMOS in series", size=18, color="#8aa0c8", anchor="start", weight=600)}
      {_text(900, 300, "NMOS in parallel", size=18, color="#8aa0c8", anchor="start", weight=600)}
      {_text(420, 690, title, size=20, color="#d9ecff", anchor="middle")}
    </svg>
    """


def _and_svg(inputs: list[str], output_name: str, title: str) -> str:
    return _nand_svg(inputs, output_name, title.replace("AND", "NAND") + " + inverter")


def _or_svg(inputs: list[str], output_name: str, title: str) -> str:
    return _nor_svg(inputs, output_name, title.replace("OR", "NOR") + " + inverter")


def _xor_svg(inputs: list[str], output_name: str, title: str) -> str:
    a, b = (inputs + ["B"])[:2]
    return f"""
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="100%" height="100%">
      <rect width="1280" height="720" fill="#0b1220"/>
      {_line(120, 100, 1210, 100, color="#6ec8ff", width=5)}
      {_text(128, 82, "VDD", size=22, color="#6ec8ff", anchor="start")}
      {_text(160, 180, "XOR transistor-level realization", size=22, color="#ffffff", anchor="start")}
      {_text(160, 216, f"Inputs: {a}, {b}", size=18, color="#8aa0c8", anchor="start")}
      {_text(900, 232, f"{output_name} = {a} \\u2295 {b}", size=24, color="#ff5aa5", anchor="start")}
      <rect x="160" y="260" width="310" height="150" rx="14" ry="14" fill="none" stroke="#7fb3ff" stroke-width="3"/>
      <rect x="510" y="260" width="310" height="150" rx="14" ry="14" fill="none" stroke="#7fb3ff" stroke-width="3"/>
      <rect x="335" y="470" width="310" height="150" rx="14" ry="14" fill="none" stroke="#7fb3ff" stroke-width="3"/>
      {_text(315, 294, "INV A", size=18, color="#d9ecff", anchor="middle")}
      {_text(665, 294, "INV B", size=18, color="#d9ecff", anchor="middle")}
      {_text(490, 504, "TG merge", size=18, color="#d9ecff", anchor="middle")}
      {_line(470, 335, 510, 335, color="#8aa0c8", width=4)}
      {_line(820, 335, 860, 335, color="#8aa0c8", width=4)}
      {_line(545, 560, 715, 560, color="#8aa0c8", width=4)}
      {_line(640, 100, 640, 470, color="#8aa0c8", width=4, dash="10 8")}
      {_circle(1040, 380, 12, "#8f78ff")}
      {_text(1070, 388, output_name, size=22, color="#ffffff", anchor="start")}
      {_line(1040, 392, 1040, 530, color="#8aa0c8", width=3, dash="12 10")}
      {_line(120, 640, 1210, 640, color="#8aa0c8", width=5)}
      {_text(128, 680, "GND", size=22, color="#8aa0c8", anchor="start")}
      {_text(420, 690, title, size=20, color="#d9ecff", anchor="middle")}
    </svg>
    """


def _fallback_svg(name: str) -> str:
    return f"""
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 400" width="100%" height="100%">
      <rect width="900" height="400" fill="#0b1220"/>
      {_text(450, 190, f"No transistor template for {name}", size=26, color="#d9ecff", anchor="middle")}
    </svg>
    """


def _transistor_payload(contract: Any, gate: str) -> dict[str, Any]:
    inputs = _inputs(contract)
    output_name = _output(contract)
    display_name = _display(contract)
    title = f"{display_name} transistor-level CMOS"
    if gate == "nand":
        svg = _nand_svg(inputs, output_name, title)
    elif gate == "nor":
        svg = _nor_svg(inputs, output_name, title)
    elif gate == "and":
        svg = _and_svg(inputs, output_name, title)
    elif gate == "or":
        svg = _or_svg(inputs, output_name, title)
    elif gate == "xor":
        svg = _xor_svg(inputs, output_name, title)
    else:
        svg = _fallback_svg(display_name)

    nodes = [
        _node("vdd", "power", 120, 40, "VDD"),
        _node("out", "output", 1040, 380, output_name),
        _node("gnd", "ground", 120, 660, "GND"),
    ]
    edges = [_edge("vdd", "out"), _edge("out", "gnd")]

    return {
        "title": title,
        "mode": "transistor",
        "style": "cmos",
        "design_name": display_name,
        "inputs": inputs,
        "output": output_name,
        "nodes": nodes,
        "edges": edges,
        "svg": svg,
        "svg_width": 1280,
        "svg_height": 720,
    }


def _gate_payload(contract: Any) -> dict[str, Any]:
    display_name = _display(contract)
    inputs = _inputs(contract)
    output_name = _output(contract)
    nodes = [
        _node("in", "input", 80, 160, ", ".join(inputs)),
        _node("gate", "block", 320, 130, display_name.upper()),
        _node("out", "output", 580, 160, output_name),
    ]
    edges = [_edge("in", "gate"), _edge("gate", "out")]
    return {
        "title": f"{display_name} gate-level diagram",
        "mode": "gate",
        "design_name": display_name,
        "inputs": inputs,
        "output": output_name,
        "nodes": nodes,
        "edges": edges,
        "svg": _fallback_svg(display_name),
        "svg_width": 900,
        "svg_height": 400,
    }


def generate_diagram(contract: Any, mode: str | None = None) -> dict[str, Any]:
    name = _name(contract)
    requested = (mode or str(_get(contract, "abstraction", "")) or "").lower()
    if requested == "gate":
        return _gate_payload(contract)
    if _simple_gate(name):
        return _transistor_payload(contract, _base_gate(name))
    return _gate_payload(contract)


def generate_diagram_from_contract(contract: Any) -> dict[str, Any]:
    return generate_diagram(contract)


def build_diagram(contract: Any) -> dict[str, Any]:
    return generate_diagram(contract)


def create_diagram(contract: Any) -> dict[str, Any]:
    return generate_diagram(contract)


def diagram_for_result(contract: Any) -> dict[str, Any]:
    return generate_diagram(contract)


def diagram_to_dict(contract: Any) -> dict[str, Any]:
    return generate_diagram(contract)


def generate_transistor_level_diagram(contract: Any) -> dict[str, Any]:
    return generate_diagram(contract, mode="transistor")


def generate_gate_level_diagram(contract: Any) -> dict[str, Any]:
    return generate_diagram(contract, mode="gate")


def generate_diagram_json(contract: Any) -> dict[str, Any]:
    return generate_diagram(contract)


def build_react_flow_from_contract(contract: Any) -> dict[str, Any]:
    return generate_diagram(contract)
