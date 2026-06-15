from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import re
from typing import Any

from app.schemas.design import DiagramEdge, DiagramNode, NetworkElement, TruthTableRow


@dataclass(frozen=True)
class CircuitSpec:
    design_type: str
    name: str
    inputs: list[str]
    outputs: list[str]
    gate_count: int
    truth_table: list[TruthTableRow]
    boolean_equation: str
    gate_level_design: dict[str, Any]
    pmos_network: list[NetworkElement]
    nmos_network: list[NetworkElement]
    verilog: str


SUPPORTED_GATES = {"not", "buffer", "nand", "nor", "and", "or", "xor", "xnor"}


def normalize_prompt(prompt: str) -> str:
    return re.sub(r"\s+", " ", prompt.strip().lower())


def detect_circuit_kind(prompt: str, design_hint: str = "auto") -> str:
    text = normalize_prompt(prompt)
    if design_hint in {"digital", "analog"} and design_hint != "auto":
        return design_hint

    if any(
        keyword in text
        for keyword in [
            "half adder",
            "full adder",
            "adder",
            "mux",
            "demux",
            "encoder",
            "decoder",
            "comparator",
            "alu",
            "register",
            "counter",
            "shift register",
            "fsm",
            "memory",
            "uart",
            "spi",
            "i2c",
            "protocol",
        ]
    ):
        return "digital"

    if any(
        keyword in text
        for keyword in [
            "amplifier",
            "filter",
            "oscillator",
            "adc",
            "dac",
            "divider",
            "mirror",
            "bandgap",
            "ldo",
            "op amp",
            "opamp",
        ]
    ):
        return "analog"

    return "digital"


def detect_mux_size(text: str) -> str | None:
    match = re.search(r"\b(\d+)\s*(?:x|:|to)\s*1\s*(?:mux|multiplexer)\b", text)
    if match:
        try:
            return f"{max(2, int(match.group(1)))}to1"
        except ValueError:
            return None
    if any(keyword in text for keyword in ["mux", "multiplexer"]):
        return "2to1"
    return None


def detect_counter_width(text: str) -> int:
    patterns = [
        r"(\d+)\s*[-:]?\s*(?:bit|bt)\s+counter",
        r"counter\s+of\s+(\d+)\s*[-:]?\s*(?:bit|bt)",
        r"(\d+)\s*[-:]?\s*(?:bit|bt)\s+counter",
        r"(\d+)\s*b\s*counter",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return max(1, int(match.group(1)))
            except ValueError:
                continue
    return 4


def detect_counter_ff_kind(text: str) -> str:
    if any(keyword in text for keyword in ["using t flip flop", "using t flip-flop", "t flip flop", "t flip-flop", "tff"]):
        return "tff"
    if any(keyword in text for keyword in ["using jk flip flop", "using jk flip-flop", "jk flip flop", "jk flip-flop", "jkff"]):
        return "jkff"
    if any(keyword in text for keyword in ["using sr flip flop", "using sr flip-flop", "sr flip flop", "sr flip-flop", "srff"]):
        return "srff"
    return "dff"


def detect_shift_register_width(text: str) -> int:
    patterns = [
        r"(\d+)\s*[-:]?\s*(?:bit|bt)\s+shift\s*register",
        r"shift\s*register\s*(\d+)\s*[-:]?\s*(?:bit|bt)",
        r"(\d+)\s*bit\s*srl",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return max(1, int(match.group(1)))
            except ValueError:
                continue
    return 4


def detect_fifo_spec(text: str) -> tuple[int, int]:
    patterns = [
        r"(\d+)\s*x\s*(\d+)\s*fifo",
        r"fifo\s*(\d+)\s*x\s*(\d+)",
        r"(\d+)\s*deep\s*(\d+)\s*bit\s*fifo",
        r"(\d+)\s*entry\s*(\d+)\s*bit\s*fifo",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                depth = max(2, int(match.group(1)))
                width = max(1, int(match.group(2)))
                return depth, width
            except ValueError:
                continue
    return 4, 8


def detect_protocol_design(text: str) -> str | None:
    if "baud rate" in text or "baud generator" in text or "baud" in text:
        return "uart_baud_rate_generator"
    if "uart receiver" in text or "uart rx" in text:
        return "uart_rx_8n1"
    if "uart transmitter" in text or "uart tx" in text or "uart" in text:
        return "uart_tx_8n1"
    if "spi slave" in text:
        return "spi_slave_8bit"
    if "spi master" in text or "spi" in text:
        return "spi_master_8bit"
    if "i2c slave" in text:
        return "i2c_slave_simple"
    if "i2c" in text:
        return "i2c_master_simple"
    if "axi lite" in text or "axi-lite" in text or "axilite" in text:
        return "axi_lite_slave_simple"
    return None


def detect_mux_tree_variant(text: str) -> bool:
    return any(keyword in text for keyword in ["using 2x1 mux", "using 2:1 mux", "using 2 to 1 mux", "implemented using 2x1 mux", "implemented using 2:1 mux"])


def detect_supported_design(prompt: str) -> str:
    text = normalize_prompt(prompt)
    mux_size = detect_mux_size(text)
    mux_tree = detect_mux_tree_variant(text)
    if mux_size:
        size = int(mux_size.replace("to1", ""))
        if mux_tree and size >= 4 and size & (size - 1) == 0:
            return f"mux_{size}to1_tree"
        return f"mux_{size}to1"

    if "2 to 4 decoder" in text or "2:4 decoder" in text or "2x4 decoder" in text:
        return "decoder_2to4"
    if "4 to 2 encoder" in text or "4:2 encoder" in text or "4x2 encoder" in text:
        return "encoder_4to2"
    if "priority encoder" in text:
        return "priority_encoder_4to2"
    if any(keyword in text for keyword in ["counter", "counting circuit"]):
        width = detect_counter_width(text)
        ff_kind = detect_counter_ff_kind(text)
        if width == 4 and ff_kind == "dff":
            return "counter_4bit"
        return f"counter_{width}bit_{ff_kind}"
    if any(keyword in text for keyword in ["shift register", "shift-register", "srl"]):
        width = detect_shift_register_width(text)
        return f"shift_register_{width}bit"
    if any(keyword in text for keyword in ["t flip flop", "t flip-flop", "tff"]):
        return "tff"
    if any(keyword in text for keyword in ["jk flip flop", "jk flip-flop", "jkff"]):
        return "jkff"
    if any(keyword in text for keyword in ["sr flip flop", "sr flip-flop", "srff"]):
        return "srff"
    if any(keyword in text for keyword in ["d flip flop", "d flip-flop", "dff"]):
        return "dff"
    if any(keyword in text for keyword in ["flip flop", "flip-flop"]):
        return "dff"
    if any(keyword in text for keyword in ["fsm", "finite state machine", "state machine"]):
        return "fsm_traffic_light"
    if "uart receiver" in text or "uart rx" in text:
        return "uart_rx_8n1"
    if "uart" in text:
        return "uart_tx_8n1"
    if "spi slave" in text:
        return "spi_slave_8bit"
    if "spi" in text:
        return "spi_master_8bit"
    if "i2c slave" in text:
        return "i2c_slave_simple"
    if "i2c" in text:
        return "i2c_master_simple"
    if "axi lite" in text or "axi-lite" in text or "axilite" in text:
        return "axi_lite_slave_simple"
    if protocol_design := detect_protocol_design(text):
        return protocol_design
    if any(keyword in text for keyword in ["fifo", "first in first out", "queue"]):
        depth, width = detect_fifo_spec(text)
        if depth == 4 and width == 8:
            return "fifo_4x8"
        return f"fifo_{depth}x{width}"

    keyword_map = [
        ("half adder", "half_adder"),
        ("full adder", "full_adder"),
        ("ripple carry adder", "ripple_carry_adder"),
        ("carry lookahead adder", "carry_lookahead_adder"),
        ("demux", "demux_1to2"),
        ("encoder", "encoder"),
        ("decoder", "decoder"),
        ("comparator", "comparator"),
        ("xnor", "xnor"),
        ("xor", "xor"),
        ("nand", "nand"),
        ("nor", "nor"),
        ("and gate", "and"),
        ("or gate", "or"),
        ("not gate", "not"),
        ("inverter", "not"),
        ("buffer", "buffer"),
    ]
    for keyword, design in keyword_map:
        if keyword in text:
            return design
    return "unsupported_design"


def _combine_rows(values: list[tuple[dict[str, int], dict[str, int]]]) -> list[TruthTableRow]:
    return [TruthTableRow(inputs=input_values, outputs=output_values) for input_values, output_values in values]


def _mux_truth_table(size: int) -> list[TruthTableRow]:
    select_bits = size.bit_length() - 1
    inputs = [f"S{i}" for i in range(select_bits)]
    rows: list[TruthTableRow] = []
    for selection in product([0, 1], repeat=select_bits):
        selected_index = sum(bit << (select_bits - index - 1) for index, bit in enumerate(selection))
        rows.append(
            TruthTableRow(
                inputs={inputs[i]: selection[i] for i in range(select_bits)},
                outputs={"Y": f"D{selected_index}"},
            )
        )
    return rows


def _is_mux_tree(design_name: str) -> bool:
    return design_name.endswith("_tree")


def _mux_spec(design_name: str) -> tuple[int, bool] | None:
    match = re.fullmatch(r"mux_(\d+)to1(?:_tree)?", design_name)
    if not match:
        return None
    size = max(2, int(match.group(1)))
    return size, design_name.endswith("_tree")


def _mux_select_bits(size: int) -> int:
    return max(1, (size - 1).bit_length())


def _mux_input_names(size: int) -> tuple[list[str], list[str]]:
    select_bits = _mux_select_bits(size)
    return [f"S{i}" for i in range(select_bits)], [f"D{i}" for i in range(size)]


def _mux_case_expression(size: int) -> str:
    select_bits = _mux_select_bits(size)
    return "{" + ", ".join(f"S{i}" for i in range(select_bits)) + "}"


def _mux_truth_rows(size: int) -> list[TruthTableRow]:
    select_bits = _mux_select_bits(size)
    rows: list[TruthTableRow] = []
    for selection in product([0, 1], repeat=select_bits):
        selected_index = sum(bit << (select_bits - index - 1) for index, bit in enumerate(selection))
        outputs = {"Y": f"D{min(selected_index, size - 1)}"}
        rows.append(
            TruthTableRow(
                inputs={f"S{i}": selection[i] for i in range(select_bits)},
                outputs=outputs,
            )
        )
    return rows


def _counter_spec(design_name: str) -> tuple[int, str]:
    match = re.fullmatch(r"counter_(\d+)bit(?:_(dff|tff|jkff|srff))?", design_name)
    if not match:
        return 4, "dff"
    width = max(1, int(match.group(1)))
    ff_kind = match.group(2) or "dff"
    return width, ff_kind


def _shift_register_spec(design_name: str) -> int:
    match = re.fullmatch(r"shift_register_(\d+)bit", design_name)
    if not match:
        return 4
    return max(1, int(match.group(1)))


def _protocol_spec(design_name: str) -> tuple[str, int]:
    if design_name == "uart_baud_rate_generator":
        return "uart", 8
    if design_name == "uart_tx_8n1":
        return "uart", 8
    if design_name == "uart_rx_8n1":
        return "uart", 8
    if design_name == "spi_master_8bit":
        return "spi", 8
    if design_name == "spi_slave_8bit":
        return "spi", 8
    if design_name == "i2c_master_simple":
        return "i2c", 8
    if design_name == "i2c_slave_simple":
        return "i2c", 8
    if design_name == "axi_lite_slave_simple":
        return "axi", 32
    return "generic", 8


def _counter_output_name(width: int) -> str:
    return f"Q[{width - 1}:0]" if width > 1 else "Q"


def _counter_next_value(width: int, ff_kind: str) -> str:
    return f"Q + {width}'d1"


def _mux_tree_size(design_name: str) -> int | None:
    spec = _mux_spec(design_name)
    if not spec:
        return None
    size, is_tree = spec
    return size if is_tree else None


def _mux_direct_verilog(design_name: str, style: str = "dataflow") -> str:
    spec = _mux_spec(design_name)
    if not spec:
        return ""
    size, _is_tree = spec
    select_bits = _mux_select_bits(size)
    select_names, data_names = _mux_input_names(size)
    case_expr = _mux_case_expression(size)
    ordered_selects = ", ".join(reversed(select_names))
    module_decl = _verilog_module_name(design_name)

    if style == "behavioral":
        lines = [
            f"module {module_decl}(",
            *[f"    input wire {name}," for name in select_names],
            *[f"    input wire {name}," for name in data_names],
            "    output reg Y",
            ");",
            "",
            "    always @* begin",
            f"        case ({case_expr})",
        ]
        for index in range(size):
            select_code = format(index, f"0{select_bits}b")
            lines.append(f"            {select_bits}'b{select_code}: Y = D{index};")
        lines.extend([
            "            default: Y = D0;",
            "        endcase",
            "    end",
            "endmodule",
        ])
        return "\n".join(lines) + "\n"

    if style == "dataflow":
        terms = [f"({case_expr} == {select_bits}'b{format(index, f'0{select_bits}b')}) ? D{index}" for index in range(size)]
        assign_expr = " : ".join(terms + ["D0"])
        return (
            f"module {module_decl}(\n"
            + "\n".join([f"    input wire {name}," for name in select_names] + [f"    input wire {name}," for name in data_names])
            + "\n    output wire Y\n);\n"
            f"    assign Y = {assign_expr};\n"
            "endmodule\n"
        )

    if style == "gate_level":
        negated = [f"n{name}" for name in select_names]
        term_names = [f"w{index}" for index in range(size)]
        lines = [
            f"module {module_decl}(",
            *[f"    input wire {name}," for name in select_names],
            *[f"    input wire {name}," for name in data_names],
            "    output wire Y",
            ");",
            "",
            "    wire " + ", ".join(negated) + ";",
            "    wire " + ", ".join(term_names) + ";",
        ]
        for index, sel_name in enumerate(select_names, start=1):
            lines.append(f"    not g{index}({negated[index - 1]}, {sel_name});")
        gate_index = len(select_names) + 1
        for index in range(size):
            literals = []
            select_code = format(index, f"0{select_bits}b")
            for bit_index, bit in enumerate(select_code):
                literals.append(negated[bit_index] if bit == "0" else select_names[bit_index])
            literals.append(data_names[index])
            lines.append(f"    and g{gate_index + index}({term_names[index]}, {', '.join(literals)});")
        if size == 1:
            lines.append("    buf g0(Y, D0);")
        else:
            or_terms = ", ".join(term_names)
            lines.append(f"    or g{gate_index + size}(Y, {or_terms});")
        lines.append("endmodule")
        return "\n".join(lines) + "\n"

    # structural: use a tree of 2x1 muxes for power-of-two sizes, otherwise fall back to the gate-level netlist
    if size & (size - 1) != 0 or size < 2:
        return _mux_direct_verilog(design_name, "gate_level")

    levels = _mux_select_bits(size)
    lines = [
        f"module {module_decl}(",
        *[f"    input wire {name}," for name in select_names],
        *[f"    input wire {name}," for name in data_names],
        "    output wire Y",
        ");",
        "",
    ]
    current = data_names[:]
    for level in range(levels):
        next_level: list[str] = []
        pair_count = len(current) // 2
        for pair_index in range(pair_count):
            out_name = "Y" if (level == levels - 1 and pair_index == 0) else f"l{level}_{pair_index}"
            if not (level == levels - 1 and pair_index == 0):
                lines.append(f"    wire {out_name};")
            next_level.append(out_name)
        if pair_count:
            lines.append("")
            for pair_index in range(pair_count):
                left = current[pair_index * 2]
                right = current[pair_index * 2 + 1]
                out_name = next_level[pair_index]
                lines.append(
                    f"    mux_2to1 m{level}_{pair_index}(.S0({select_names[level]}), .D0({left}), .D1({right}), .Y({out_name}));"
                )
            lines.append("")
        current = next_level
    lines.append("endmodule")

    leaf_impl = """module mux_2to1(
    input wire S0,
    input wire D0,
    input wire D1,
    output wire Y
);

wire nS0, w0, w1;

not g1(nS0, S0);
and g2(w0, nS0, D0);
and g3(w1, S0, D1);
or g4(Y, w0, w1);

endmodule
"""
    return "\n".join(lines) + "\n" + leaf_impl


def _counter_family_verilog(design_name: str, style: str = "dataflow") -> str:
    width, ff_kind = _counter_spec(design_name)
    q_range = f"[{width - 1}:0] " if width > 1 else ""
    zero_value = f"{width}'b0" if width > 1 else "1'b0"
    increment = f"Q + {width}'d1"
    style = (style or "dataflow").strip().lower()

    if style == "behavioral":
        return f"""module {design_name}(input wire CLK, input wire RST, input wire EN, output reg {q_range}Q);
    always @(posedge CLK) begin
        if (RST)
            Q <= {zero_value};
        else if (EN)
            Q <= {increment};
        else
            Q <= Q;
    end
endmodule
"""

    if style == "structural":
        bits = list(range(width))
        q_bits = [f"Q[{i}]" for i in bits]
        next_bits = [f"Q_next[{i}]" for i in bits]
        toggle_bits = [f"toggle_{i}" for i in bits]
        bit_width_decl = f"[{width - 1}:0] " if width > 1 else ""
        module_lines = [
            f"module {design_name}(input wire CLK, input wire RST, input wire EN, output wire {q_range}Q);",
            f"    wire {bit_width_decl}Q_next;",
        ]
        if ff_kind == "tff":
            module_lines.append(f"    wire {bit_width_decl}toggle;")
            module_lines.append(f"    assign Q_next = RST ? {zero_value} : (Q ^ {{ {width}{{EN}} }});")
        elif ff_kind == "jkff":
            module_lines.append(f"    wire {bit_width_decl}toggle;")
            module_lines.append(f"    assign Q_next = RST ? {zero_value} : (EN ? (Q + {width}'d1) : Q);")
        elif ff_kind == "srff":
            module_lines.append(f"    wire {bit_width_decl}toggle;")
            module_lines.append(f"    assign Q_next = RST ? {zero_value} : (EN ? (Q + {width}'d1) : Q);")
        else:
            module_lines.append(f"    assign Q_next = RST ? {zero_value} : (EN ? (Q + {width}'d1) : Q);")
        module_lines.append("")
        if ff_kind == "dff":
            module_lines.append(f"    {design_name}_reg u_reg(.CLK(CLK), .D(Q_next), .Q(Q));")
        elif ff_kind == "tff":
            for i in bits:
                toggle_expr = " & ".join([f"Q[{j}]" for j in range(i)]) if i > 0 else "1'b1"
                module_lines.append(f"    wire toggle_{i} = EN & {toggle_expr};")
                module_lines.append(f"    tff u_ff_{i}(.CLK(CLK), .T(toggle_{i}), .Q(Q[{i}]));")
        elif ff_kind == "jkff":
            for i in bits:
                toggle_expr = " & ".join([f"Q[{j}]" for j in range(i)]) if i > 0 else "1'b1"
                module_lines.append(f"    wire toggle_{i} = EN & {toggle_expr};")
                module_lines.append(f"    jkff u_ff_{i}(.CLK(CLK), .J(toggle_{i}), .K(toggle_{i}), .Q(Q[{i}]));")
        elif ff_kind == "srff":
            for i in bits:
                next_bit = f"Q_next[{i}]"
                module_lines.append(f"    wire s_{i} = {next_bit} & ~Q[{i}];")
                module_lines.append(f"    wire r_{i} = ~{next_bit} & Q[{i}];")
                module_lines.append(f"    srff u_ff_{i}(.CLK(CLK), .S(s_{i}), .R(r_{i}), .Q(Q[{i}]));")
        module_lines.append("endmodule")
        if ff_kind == "dff":
            module_lines.append("")
            module_lines.append(f"module {design_name}_reg(input wire CLK, input wire {q_range}D, output reg {q_range}Q);")
            module_lines.append("    always @(posedge CLK) begin")
            module_lines.append("        Q <= D;")
            module_lines.append("    end")
            module_lines.append("endmodule")
        return "\n".join(module_lines) + "\n"

    return f"""module {design_name}(input wire CLK, input wire RST, input wire EN, output reg {q_range}Q);
    wire {q_range}Q_next;
    assign Q_next = RST ? {zero_value} : (EN ? {increment} : Q);
    always @(posedge CLK) begin
        Q <= Q_next;
    end
endmodule
"""


def _shift_register_family_verilog(design_name: str, style: str = "dataflow") -> str:
    width = _shift_register_spec(design_name)
    q_range = f"[{width - 1}:0] " if width > 1 else ""
    zero_value = f"{width}'b0" if width > 1 else "1'b0"
    style = (style or "dataflow").strip().lower()
    default_next = f"{{Q[{width - 2}:0], D}}" if width > 1 else "D"

    if style == "behavioral":
        return f"""module {design_name}(input wire CLK, input wire RST, input wire EN, input wire D, output reg {q_range}Q);
    always @(posedge CLK) begin
        if (RST)
            Q <= {zero_value};
        else if (EN)
            Q <= {default_next};
        else
            Q <= Q;
    end
endmodule
"""

    if style == "structural":
        return f"""module {design_name}(input wire CLK, input wire RST, input wire EN, input wire D, output wire {q_range}Q);
    wire {q_range}q_next;

    {design_name}_next u_next(.Q(Q), .RST(RST), .EN(EN), .D(D), .Q_NEXT(q_next));
    {design_name}_reg u_reg(.CLK(CLK), .D(q_next), .Q(Q));
endmodule

module {design_name}_next(input wire {q_range}Q, input wire RST, input wire EN, input wire D, output wire {q_range}Q_NEXT);
    assign Q_NEXT = RST ? {zero_value} : (EN ? {default_next} : Q);
endmodule

module {design_name}_reg(input wire CLK, input wire {q_range}D, output reg {q_range}Q);
    always @(posedge CLK) begin
        Q <= D;
    end
endmodule
"""

    return f"""module {design_name}(input wire CLK, input wire RST, input wire EN, input wire D, output reg {q_range}Q);
    wire {q_range}Q_next;
    assign Q_next = RST ? {zero_value} : (EN ? {default_next} : Q);
    always @(posedge CLK) begin
        Q <= Q_next;
    end
endmodule
"""


def _protocol_family_verilog(design_name: str, style: str = "behavioral") -> str:
    style = (style or "behavioral").strip().lower()
    if design_name == "uart_baud_rate_generator":
        return """module uart_baud_rate_generator(
    input wire CLK,
    input wire RST,
    input wire [15:0] DIVISOR,
    output reg TICK
);
    reg [15:0] count;
    always @(posedge CLK) begin
        if (RST) begin
            count <= 16'd0;
            TICK <= 1'b0;
        end else if (count >= DIVISOR - 1) begin
            count <= 16'd0;
            TICK <= 1'b1;
        end else begin
            count <= count + 16'd1;
            TICK <= 1'b0;
        end
    end
endmodule
"""
    if design_name == "uart_tx_8n1":
        if style == "structural":
            return """module uart_tx_8n1(
    input wire CLK,
    input wire RST,
    input wire START,
    input wire [7:0] DATA_IN,
    output wire TX,
    output wire BUSY,
    output wire DONE
);
    wire [2:0] state_next;
    wire [3:0] bit_idx_next;
    wire [7:0] shifter_next;
    wire [3:0] baud_next;
    wire tx_next;
    wire busy_next;
    wire done_next;

    uart_tx_8n1_next u_next(
        .STATE(STATE),
        .BIT_IDX(bit_idx),
        .BAUD_CNT(baud_cnt),
        .SHIFTER(shifter),
        .START(START),
        .DATA_IN(DATA_IN),
        .TX_NEXT(tx_next),
        .BUSY_NEXT(busy_next),
        .DONE_NEXT(done_next),
        .STATE_NEXT(state_next),
        .BIT_IDX_NEXT(bit_idx_next),
        .BAUD_CNT_NEXT(baud_next),
        .SHIFTER_NEXT(shifter_next)
    );
    uart_tx_8n1_reg u_reg(
        .CLK(CLK),
        .RST(RST),
        .STATE_NEXT(state_next),
        .BIT_IDX_NEXT(bit_idx_next),
        .BAUD_CNT_NEXT(baud_next),
        .SHIFTER_NEXT(shifter_next),
        .TX_NEXT(tx_next),
        .BUSY_NEXT(busy_next),
        .DONE_NEXT(done_next),
        .TX(TX),
        .BUSY(BUSY),
        .DONE(DONE)
    );
endmodule

module uart_tx_8n1_next(
    input wire [2:0] STATE,
    input wire [3:0] BIT_IDX,
    input wire [3:0] BAUD_CNT,
    input wire [7:0] SHIFTER,
    input wire START,
    input wire [7:0] DATA_IN,
    output wire TX_NEXT,
    output wire BUSY_NEXT,
    output wire DONE_NEXT,
    output wire [2:0] STATE_NEXT,
    output wire [3:0] BIT_IDX_NEXT,
    output wire [3:0] BAUD_CNT_NEXT,
    output wire [7:0] SHIFTER_NEXT
);
    localparam IDLE = 3'd0, START_BIT = 3'd1, DATA_BITS = 3'd2, STOP_BIT = 3'd3;
    assign TX_NEXT = (STATE == IDLE) ? 1'b1 :
                     (STATE == START_BIT) ? 1'b0 :
                     (STATE == DATA_BITS) ? SHIFTER[0] : 1'b1;
    assign BUSY_NEXT = (STATE != IDLE);
    assign DONE_NEXT = (STATE == STOP_BIT);
    assign SHIFTER_NEXT = (STATE == IDLE && START) ? DATA_IN : (STATE == DATA_BITS ? {1'b0, SHIFTER[7:1]} : SHIFTER);
    assign BIT_IDX_NEXT = (STATE == DATA_BITS && BAUD_CNT == 4'd3) ? (BIT_IDX + 4'd1) : BIT_IDX;
    assign BAUD_CNT_NEXT = (STATE == IDLE) ? 4'd0 : (BAUD_CNT == 4'd3 ? 4'd0 : BAUD_CNT + 4'd1);
    assign STATE_NEXT = (STATE == IDLE && START) ? START_BIT :
                        (STATE == START_BIT && BAUD_CNT == 4'd3) ? DATA_BITS :
                        (STATE == DATA_BITS && BAUD_CNT == 4'd3 && BIT_IDX == 4'd7) ? STOP_BIT :
                        (STATE == DATA_BITS && BAUD_CNT == 4'd3) ? DATA_BITS :
                        (STATE == STOP_BIT && BAUD_CNT == 4'd3) ? IDLE : STATE;
endmodule

module uart_tx_8n1_reg(
    input wire CLK,
    input wire RST,
    input wire [2:0] STATE_NEXT,
    input wire [3:0] BIT_IDX_NEXT,
    input wire [3:0] BAUD_CNT_NEXT,
    input wire [7:0] SHIFTER_NEXT,
    input wire TX_NEXT,
    input wire BUSY_NEXT,
    input wire DONE_NEXT,
    output reg TX,
    output reg BUSY,
    output reg DONE
);
    reg [2:0] STATE;
    reg [3:0] bit_idx;
    reg [3:0] baud_cnt;
    reg [7:0] shifter;
    always @(posedge CLK) begin
        if (RST) begin
            STATE <= 3'd0;
            bit_idx <= 4'd0;
            baud_cnt <= 4'd0;
            shifter <= 8'd0;
            TX <= 1'b1;
            BUSY <= 1'b0;
            DONE <= 1'b0;
        end else begin
            STATE <= STATE_NEXT;
            bit_idx <= BIT_IDX_NEXT;
            baud_cnt <= BAUD_CNT_NEXT;
            shifter <= SHIFTER_NEXT;
            TX <= TX_NEXT;
            BUSY <= BUSY_NEXT;
            DONE <= DONE_NEXT;
        end
    end
endmodule
"""
        return """module uart_tx_8n1(
    input wire CLK,
    input wire RST,
    input wire START,
    input wire [7:0] DATA_IN,
    output reg TX,
    output reg BUSY,
    output reg DONE
);
    reg [2:0] STATE;
    reg [3:0] BIT_IDX;
    reg [3:0] BAUD_CNT;
    reg [7:0] SHIFTER;
    localparam IDLE = 3'd0, START_BIT = 3'd1, DATA_BITS = 3'd2, STOP_BIT = 3'd3;

    always @(posedge CLK) begin
        if (RST) begin
            STATE <= IDLE;
            BIT_IDX <= 4'd0;
            BAUD_CNT <= 4'd0;
            SHIFTER <= 8'd0;
            TX <= 1'b1;
            BUSY <= 1'b0;
            DONE <= 1'b0;
        end else begin
            DONE <= 1'b0;
            case (STATE)
                IDLE: begin
                    TX <= 1'b1;
                    BUSY <= 1'b0;
                    if (START) begin
                        STATE <= START_BIT;
                        SHIFTER <= DATA_IN;
                        BAUD_CNT <= 4'd0;
                        BUSY <= 1'b1;
                    end
                end
                START_BIT: begin
                    TX <= 1'b0;
                    BUSY <= 1'b1;
                    if (BAUD_CNT == 4'd3) begin
                        STATE <= DATA_BITS;
                        BAUD_CNT <= 4'd0;
                        BIT_IDX <= 4'd0;
                    end else begin
                        BAUD_CNT <= BAUD_CNT + 4'd1;
                    end
                end
                DATA_BITS: begin
                    TX <= SHIFTER[0];
                    BUSY <= 1'b1;
                    if (BAUD_CNT == 4'd3) begin
                        BAUD_CNT <= 4'd0;
                        SHIFTER <= {1'b0, SHIFTER[7:1]};
                        if (BIT_IDX == 4'd7)
                            STATE <= STOP_BIT;
                        else
                            BIT_IDX <= BIT_IDX + 4'd1;
                    end else begin
                        BAUD_CNT <= BAUD_CNT + 4'd1;
                    end
                end
                STOP_BIT: begin
                    TX <= 1'b1;
                    BUSY <= 1'b1;
                    if (BAUD_CNT == 4'd3) begin
                        STATE <= IDLE;
                        BAUD_CNT <= 4'd0;
                        BUSY <= 1'b0;
                        DONE <= 1'b1;
                    end else begin
                        BAUD_CNT <= BAUD_CNT + 4'd1;
                    end
                end
            endcase
        end
    end
endmodule
"""
    if design_name == "spi_master_8bit":
        return """module spi_master_8bit(
    input wire CLK,
    input wire RST,
    input wire START,
    input wire MISO,
    input wire [7:0] DATA_IN,
    output reg SCLK,
    output reg MOSI,
    output reg CS,
    output reg BUSY,
    output reg DONE,
    output reg [7:0] DATA_OUT
);
    reg [2:0] BIT_IDX;
    reg [7:0] SHIFT;
    reg [3:0] DIV;
    localparam IDLE = 2'd0, SHIFTING = 2'd1, DONE_S = 2'd2;

    always @(posedge CLK) begin
        if (RST) begin
            BIT_IDX <= 3'd0;
            SHIFT <= 8'd0;
            DIV <= 4'd0;
            SCLK <= 1'b0;
            MOSI <= 1'b0;
            CS <= 1'b1;
            BUSY <= 1'b0;
            DONE <= 1'b0;
            DATA_OUT <= 8'd0;
        end else begin
            DONE <= 1'b0;
            if (START && !BUSY) begin
                BUSY <= 1'b1;
                CS <= 1'b0;
                SHIFT <= DATA_IN;
                BIT_IDX <= 3'd0;
                DIV <= 4'd0;
            end else if (BUSY) begin
                DIV <= DIV + 4'd1;
                if (DIV == 4'd3) begin
                    DIV <= 4'd0;
                    SCLK <= ~SCLK;
                    if (SCLK == 1'b0) begin
                        MOSI <= SHIFT[7];
                        SHIFT <= {SHIFT[6:0], MISO};
                        BIT_IDX <= BIT_IDX + 3'd1;
                        if (BIT_IDX == 3'd7) begin
                            BUSY <= 1'b0;
                            CS <= 1'b1;
                            DONE <= 1'b1;
                            DATA_OUT <= {SHIFT[6:0], MISO};
                        end
                    end
                end
            end else begin
                SCLK <= 1'b0;
                CS <= 1'b1;
            end
        end
    end
endmodule
"""
    return """module i2c_master_simple(
    input wire CLK,
    input wire RST,
    input wire START,
    input wire SDA_IN,
    input wire [6:0] ADDR,
    input wire [7:0] DATA_IN,
    output reg SCL,
    output reg SDA_OUT,
    output reg SDA_OE,
    output reg BUSY,
    output reg DONE,
    output reg ACK
);
    reg [1:0] STATE;
    reg [3:0] BIT_IDX;
    reg [3:0] DIV;
    reg [7:0] SHIFT;
    localparam IDLE = 2'd0, START_S = 2'd1, TRANSFER = 2'd2, STOP_S = 2'd3;

    always @(posedge CLK) begin
        if (RST) begin
            STATE <= IDLE;
            BIT_IDX <= 4'd0;
            DIV <= 4'd0;
            SHIFT <= 8'd0;
            SCL <= 1'b1;
            SDA_OUT <= 1'b1;
            SDA_OE <= 1'b0;
            BUSY <= 1'b0;
            DONE <= 1'b0;
            ACK <= 1'b0;
        end else begin
            DONE <= 1'b0;
            case (STATE)
                IDLE: begin
                    SCL <= 1'b1;
                    SDA_OE <= 1'b0;
                    BUSY <= 1'b0;
                    if (START) begin
                        STATE <= START_S;
                        BUSY <= 1'b1;
                        SHIFT <= DATA_IN;
                    end
                end
                START_S: begin
                    SDA_OE <= 1'b1;
                    SDA_OUT <= 1'b0;
                    SCL <= 1'b1;
                    STATE <= TRANSFER;
                    BIT_IDX <= 4'd0;
                    DIV <= 4'd0;
                end
                TRANSFER: begin
                    DIV <= DIV + 4'd1;
                    if (DIV == 4'd3) begin
                        DIV <= 4'd0;
                        SCL <= ~SCL;
                        if (SCL == 1'b0) begin
                            SDA_OE <= 1'b1;
                            SDA_OUT <= SHIFT[7];
                            SHIFT <= {SHIFT[6:0], SDA_IN};
                            BIT_IDX <= BIT_IDX + 4'd1;
                            if (BIT_IDX == 4'd7) begin
                                ACK <= ~SDA_IN;
                                STATE <= STOP_S;
                            end
                        end
                    end
                end
                STOP_S: begin
                    SDA_OE <= 1'b1;
                    SDA_OUT <= 1'b0;
                    SCL <= 1'b1;
                    SDA_OE <= 1'b0;
                    STATE <= IDLE;
                    BUSY <= 1'b0;
                    DONE <= 1'b1;
                end
            endcase
        end
    end
endmodule
"""


def _fifo_spec(design_name: str) -> tuple[int, int]:
    match = re.fullmatch(r"fifo_(\d+)x(\d+)", design_name)
    if not match:
        return 4, 8
    depth = max(2, int(match.group(1)))
    width = max(1, int(match.group(2)))
    return depth, width


def _fifo_addr_width(depth: int) -> int:
    bits = 0
    span = 1
    while span < depth:
        span <<= 1
        bits += 1
    return max(1, bits)


def _fifo_family_verilog(design_name: str, style: str = "behavioral") -> str:
    depth, width = _fifo_spec(design_name)
    addr_w = _fifo_addr_width(depth)
    data_range = f"[{width - 1}:0] " if width > 1 else ""
    addr_range = f"[{addr_w - 1}:0] " if addr_w > 1 else ""
    count_range = f"[{addr_w}:0] " if addr_w > 0 else ""
    full_threshold = depth
    count_zero = f"{addr_w + 1}'b0"
    count_full = f"{addr_w + 1}'d{depth}"
    style = (style or "behavioral").strip().lower()

    if style == "behavioral":
        return f"""module {design_name}(
    input wire CLK,
    input wire RESET,
    input wire WR_EN,
    input wire RD_EN,
    input wire {data_range}DIN,
    output reg {data_range}DOUT,
    output reg FULL,
    output reg EMPTY
);

reg {data_range}mem [0:{depth - 1}];
reg {addr_range}wptr;
reg {addr_range}rptr;
reg {count_range}count;
wire {count_range}count_next;
wire push;
wire pop;

assign push = WR_EN & (~FULL | RD_EN);
assign pop = RD_EN & ~EMPTY;
assign count_next = (push && !pop) ? (count + 1'b1) :
                    (pop && !push) ? (count - 1'b1) :
                    count;

always @(posedge CLK) begin
    if (RESET) begin
        wptr <= {addr_w}'b0;
        rptr <= {addr_w}'b0;
        count <= {addr_w + 1}'b0;
        DOUT <= {width}'b0;
        FULL <= 1'b0;
        EMPTY <= 1'b1;
    end else begin
        if (push)
            mem[wptr] <= DIN;
        if (pop)
            DOUT <= mem[rptr];
        if (push)
            wptr <= wptr + 1'b1;
        if (pop)
            rptr <= rptr + 1'b1;
        count <= count_next;
        FULL <= (count_next == {count_full});
        EMPTY <= (count_next == {count_zero});
    end
end

endmodule
"""

    ctrl_body = """assign PUSH = WR_EN & ~FULL;
assign POP = RD_EN & ~EMPTY;
""" if style in {"dataflow", "structural"} else """not g1(nFULL, FULL);
not g2(nEMPTY, EMPTY);
and g3(PUSH, WR_EN, nFULL);
and g4(POP, RD_EN, nEMPTY);
"""

    return f"""module {design_name}(
    input wire CLK,
    input wire RESET,
    input wire WR_EN,
    input wire RD_EN,
    input wire {data_range}DIN,
    output wire {data_range}DOUT,
    output wire FULL,
    output wire EMPTY
);

wire PUSH;
wire POP;
wire {addr_range}WPTR;
wire {addr_range}RPTR;
wire {count_range}COUNT;

{design_name}_ctrl u_ctrl(.WR_EN(WR_EN), .RD_EN(RD_EN), .FULL(FULL), .EMPTY(EMPTY), .PUSH(PUSH), .POP(POP));
{design_name}_state u_state(.CLK(CLK), .RESET(RESET), .PUSH(PUSH), .POP(POP), .WPTR(WPTR), .RPTR(RPTR), .COUNT(COUNT), .FULL(FULL), .EMPTY(EMPTY));
{design_name}_mem u_mem(.CLK(CLK), .PUSH(PUSH), .POP(POP), .WPTR(WPTR), .RPTR(RPTR), .DIN(DIN), .DOUT(DOUT));

endmodule

module {design_name}_ctrl(
    input wire WR_EN,
    input wire RD_EN,
    input wire FULL,
    input wire EMPTY,
    output wire PUSH,
    output wire POP
);

assign PUSH = WR_EN & (~FULL | RD_EN);
assign POP = RD_EN & ~EMPTY;

endmodule

module {design_name}_state(
    input wire CLK,
    input wire RESET,
    input wire PUSH,
    input wire POP,
    output reg {addr_range}WPTR,
    output reg {addr_range}RPTR,
    output reg {count_range}COUNT,
    output reg FULL,
    output reg EMPTY
);

wire {count_range}count_next = (PUSH && !POP) ? (COUNT + 1'b1) :
                               (POP && !PUSH) ? (COUNT - 1'b1) :
                               COUNT;

always @(posedge CLK) begin
    if (RESET) begin
        WPTR <= {addr_w}'b0;
        RPTR <= {addr_w}'b0;
        COUNT <= {addr_w + 1}'b0;
        FULL <= 1'b0;
        EMPTY <= 1'b1;
    end else begin
        if (PUSH)
            WPTR <= WPTR + 1'b1;
        if (POP)
            RPTR <= RPTR + 1'b1;
        COUNT <= count_next;
        FULL <= (count_next == {count_full});
        EMPTY <= (count_next == {count_zero});
    end
end

endmodule

module {design_name}_mem(
    input wire CLK,
    input wire PUSH,
    input wire POP,
    input wire {addr_range}WPTR,
    input wire {addr_range}RPTR,
    input wire {data_range}DIN,
    output reg {data_range}DOUT
);

reg {data_range}mem [0:{depth - 1}];

always @(posedge CLK) begin
    if (PUSH)
        mem[WPTR] <= DIN;
    if (POP)
        DOUT <= mem[RPTR];
end

endmodule
"""


def _fifo_testbench(contract: Any) -> str:
    design_name = getattr(contract, "design_name", "")
    depth, width = _fifo_spec(design_name)
    tb_module = f"{design_name}_tb"
    data_range = f"[{width - 1}:0] " if width > 1 else ""
    fill_cycles = max(2, depth)
    drain_cycles = max(2, depth)
    return f"""`timescale 1ns/1ps
module {tb_module};
    reg CLK;
    reg RESET;
    reg WR_EN;
    reg RD_EN;
    reg {data_range}DIN;
    wire {data_range}DOUT;
    wire FULL;
    wire EMPTY;

    {design_name} dut(
        .CLK(CLK),
        .RESET(RESET),
        .WR_EN(WR_EN),
        .RD_EN(RD_EN),
        .DIN(DIN),
        .DOUT(DOUT),
        .FULL(FULL),
        .EMPTY(EMPTY)
    );

    always #5 CLK = ~CLK;

    initial begin
        $display("{tb_module}");
        $monitor("time=%0t WR_EN=%b RD_EN=%b DIN=%b DOUT=%b FULL=%b EMPTY=%b", $time, WR_EN, RD_EN, DIN, DOUT, FULL, EMPTY);
        CLK = 1'b0;
        RESET = 1'b1;
        WR_EN = 1'b0;
        RD_EN = 1'b0;
        DIN = {width}'d0;
        #12 RESET = 1'b0;
        WR_EN = 1'b1;
        RD_EN = 1'b0;
        repeat ({fill_cycles}) begin
            DIN = DIN + 1'b1;
            @(posedge CLK);
        end
        DIN = DIN + 1'b1;
        @(posedge CLK);
        WR_EN = 1'b1;
        RD_EN = 1'b1;
        DIN = DIN + 1'b1;
        @(posedge CLK);
        WR_EN = 1'b0;
        RD_EN = 1'b1;
        repeat ({drain_cycles}) @(posedge CLK);
        repeat (2) @(posedge CLK);
        $finish;
    end
endmodule
"""


def _mux_tree_verilog(design_name: str, style: str = "structural") -> str:
    style = (style or "structural").strip().lower()
    spec = _mux_spec(design_name)
    if not spec:
        return _mux_direct_verilog(design_name, style)

    size, is_tree = spec
    if not is_tree or size & (size - 1) != 0:
        return _mux_direct_verilog(design_name, style)

    if style == "behavioral":
        leaf_impl = """module mux_2to1(
    input wire S0,
    input wire D0,
    input wire D1,
    output reg Y
);

always @* begin
    if (S0)
        Y = D1;
    else
        Y = D0;
end

endmodule
"""
    elif style == "dataflow":
        leaf_impl = """module mux_2to1(
    input wire S0,
    input wire D0,
    input wire D1,
    output wire Y
);

assign Y = S0 ? D1 : D0;

endmodule
"""
    else:
        leaf_impl = """module mux_2to1(
    input wire S0,
    input wire D0,
    input wire D1,
    output wire Y
);

wire nS0, w0, w1;

not g1(nS0, S0);
and g2(w0, nS0, D0);
and g3(w1, S0, D1);
or g4(Y, w0, w1);

endmodule
"""

    select_names, data_names = _mux_input_names(size)
    levels = _mux_select_bits(size)
    module_name = _verilog_module_name(design_name)
    lines = [f"module {module_name}("]
    lines.extend([f"    input wire {name}," for name in select_names])
    lines.extend([f"    input wire {name}," for name in data_names[:-1]])
    lines.append(f"    input wire {data_names[-1]},")
    lines.append("    output wire Y")
    lines.append(");")
    lines.append("")

    current = data_names[:]
    for level in range(levels):
        next_level: list[str] = []
        pair_count = len(current) // 2
        level_wires: list[str] = []
        for pair_index in range(pair_count):
            out_name = "Y" if (level == levels - 1 and pair_index == 0) else f"l{level}_{pair_index}"
            if not (level == levels - 1 and pair_index == 0):
                level_wires.append(out_name)
            next_level.append(out_name)
        if level_wires:
            lines.append(f"wire {', '.join(level_wires)};")
        lines.append("")
        for pair_index in range(pair_count):
            left = current[pair_index * 2]
            right = current[pair_index * 2 + 1]
            out_name = next_level[pair_index]
            lines.append(
                f"mux_2to1 m{level}_{pair_index}(.S0({select_names[level]}), .D0({left}), .D1({right}), .Y({out_name}));"
            )
        lines.append("")
        current = next_level

    lines.append("endmodule")
    return "\n".join(lines) + "\n"


def generate_truth_table(design_name: str) -> list[TruthTableRow]:
    if design_name == "not":
        return _combine_rows([({"A": 0}, {"Y": 1}), ({"A": 1}, {"Y": 0})])
    if design_name == "buffer":
        return _combine_rows([({"A": 0}, {"Y": 0}), ({"A": 1}, {"Y": 1})])
    if design_name == "nand":
        return _combine_rows(
            [
                ({"A": 0, "B": 0}, {"Y": 1}),
                ({"A": 0, "B": 1}, {"Y": 1}),
                ({"A": 1, "B": 0}, {"Y": 1}),
                ({"A": 1, "B": 1}, {"Y": 0}),
            ]
        )
    if design_name == "nor":
        return _combine_rows(
            [
                ({"A": 0, "B": 0}, {"Y": 1}),
                ({"A": 0, "B": 1}, {"Y": 0}),
                ({"A": 1, "B": 0}, {"Y": 0}),
                ({"A": 1, "B": 1}, {"Y": 0}),
            ]
        )
    if design_name == "and":
        return _combine_rows(
            [
                ({"A": 0, "B": 0}, {"Y": 0}),
                ({"A": 0, "B": 1}, {"Y": 0}),
                ({"A": 1, "B": 0}, {"Y": 0}),
                ({"A": 1, "B": 1}, {"Y": 1}),
            ]
        )
    if design_name == "or":
        return _combine_rows(
            [
                ({"A": 0, "B": 0}, {"Y": 0}),
                ({"A": 0, "B": 1}, {"Y": 1}),
                ({"A": 1, "B": 0}, {"Y": 1}),
                ({"A": 1, "B": 1}, {"Y": 1}),
            ]
        )
    if design_name == "xor":
        return _combine_rows(
            [
                ({"A": 0, "B": 0}, {"Y": 0}),
                ({"A": 0, "B": 1}, {"Y": 1}),
                ({"A": 1, "B": 0}, {"Y": 1}),
                ({"A": 1, "B": 1}, {"Y": 0}),
            ]
        )
    if design_name == "xnor":
        return _combine_rows(
            [
                ({"A": 0, "B": 0}, {"Y": 1}),
                ({"A": 0, "B": 1}, {"Y": 0}),
                ({"A": 1, "B": 0}, {"Y": 0}),
                ({"A": 1, "B": 1}, {"Y": 1}),
            ]
        )
    if design_name == "half_adder":
        return _combine_rows(
            [
                ({"A": 0, "B": 0}, {"SUM": 0, "COUT": 0}),
                ({"A": 0, "B": 1}, {"SUM": 1, "COUT": 0}),
                ({"A": 1, "B": 0}, {"SUM": 1, "COUT": 0}),
                ({"A": 1, "B": 1}, {"SUM": 0, "COUT": 1}),
            ]
        )
    if design_name == "full_adder":
        rows: list[TruthTableRow] = []
        for a, b, cin in product([0, 1], repeat=3):
            total = a + b + cin
            rows.append(
                TruthTableRow(
                    inputs={"A": a, "B": b, "CIN": cin},
                    outputs={"SUM": total % 2, "COUT": 1 if total >= 2 else 0},
                )
            )
        return rows
    if mux_spec := _mux_spec(design_name):
        size, _is_tree = mux_spec
        return _mux_truth_rows(size)
    if design_name == "demux_1to2":
        return _combine_rows(
            [
                ({"SEL": 0, "D": 0}, {"Y0": 0, "Y1": 0}),
                ({"SEL": 0, "D": 1}, {"Y0": 1, "Y1": 0}),
                ({"SEL": 1, "D": 0}, {"Y0": 0, "Y1": 0}),
                ({"SEL": 1, "D": 1}, {"Y0": 0, "Y1": 1}),
            ]
        )
    if design_name == "comparator":
        return _combine_rows(
            [
                ({"A": 0, "B": 0}, {"EQ": 1, "GT": 0, "LT": 0}),
                ({"A": 0, "B": 1}, {"EQ": 0, "GT": 0, "LT": 1}),
                ({"A": 1, "B": 0}, {"EQ": 0, "GT": 1, "LT": 0}),
                ({"A": 1, "B": 1}, {"EQ": 1, "GT": 0, "LT": 0}),
            ]
        )
    if design_name == "decoder_2to4":
        return _combine_rows(
            [
                ({"A": 0, "B": 0}, {"Y0": 1, "Y1": 0, "Y2": 0, "Y3": 0}),
                ({"A": 0, "B": 1}, {"Y0": 0, "Y1": 1, "Y2": 0, "Y3": 0}),
                ({"A": 1, "B": 0}, {"Y0": 0, "Y1": 0, "Y2": 1, "Y3": 0}),
                ({"A": 1, "B": 1}, {"Y0": 0, "Y1": 0, "Y2": 0, "Y3": 1}),
            ]
        )
    if design_name == "encoder_4to2":
        return _combine_rows(
            [
                ({"D0": 1, "D1": 0, "D2": 0, "D3": 0}, {"Y1": 0, "Y0": 0}),
                ({"D0": 0, "D1": 1, "D2": 0, "D3": 0}, {"Y1": 0, "Y0": 1}),
                ({"D0": 0, "D1": 0, "D2": 1, "D3": 0}, {"Y1": 1, "Y0": 0}),
                ({"D0": 0, "D1": 0, "D2": 0, "D3": 1}, {"Y1": 1, "Y0": 1}),
            ]
        )
    if design_name == "priority_encoder_4to2":
        return _combine_rows(
            [
                ({"D3": 1, "D2": 0, "D1": 0, "D0": 0}, {"Y1": 1, "Y0": 1, "VALID": 1}),
                ({"D3": 0, "D2": 1, "D1": 0, "D0": 0}, {"Y1": 1, "Y0": 0, "VALID": 1}),
                ({"D3": 0, "D2": 0, "D1": 1, "D0": 0}, {"Y1": 0, "Y0": 1, "VALID": 1}),
                ({"D3": 0, "D2": 0, "D1": 0, "D0": 1}, {"Y1": 0, "Y0": 0, "VALID": 1}),
            ]
        )
    if design_name == "dff":
        return _combine_rows(
            [
                ({"CLK": "posedge", "D": 0, "Q_prev": 0}, {"Q_next": 0}),
                ({"CLK": "posedge", "D": 1, "Q_prev": 0}, {"Q_next": 1}),
                ({"CLK": "posedge", "D": 0, "Q_prev": 1}, {"Q_next": 0}),
                ({"CLK": "posedge", "D": 1, "Q_prev": 1}, {"Q_next": 1}),
            ]
        )
    if design_name == "tff":
        return _combine_rows(
            [
                ({"CLK": "posedge", "T": 0, "Q_prev": 0}, {"Q_next": 0}),
                ({"CLK": "posedge", "T": 1, "Q_prev": 0}, {"Q_next": 1}),
                ({"CLK": "posedge", "T": 0, "Q_prev": 1}, {"Q_next": 1}),
                ({"CLK": "posedge", "T": 1, "Q_prev": 1}, {"Q_next": 0}),
            ]
        )
    if design_name == "jkff":
        return _combine_rows(
            [
                ({"CLK": "posedge", "J": 0, "K": 0, "Q_prev": 0}, {"Q_next": 0}),
                ({"CLK": "posedge", "J": 0, "K": 1, "Q_prev": 0}, {"Q_next": 0}),
                ({"CLK": "posedge", "J": 1, "K": 0, "Q_prev": 0}, {"Q_next": 1}),
                ({"CLK": "posedge", "J": 1, "K": 1, "Q_prev": 0}, {"Q_next": 1}),
            ]
        )
    if design_name == "srff":
        return _combine_rows(
            [
                ({"CLK": "posedge", "S": 0, "R": 0, "Q_prev": 0}, {"Q_next": 0}),
                ({"CLK": "posedge", "S": 0, "R": 1, "Q_prev": 0}, {"Q_next": 0}),
                ({"CLK": "posedge", "S": 1, "R": 0, "Q_prev": 0}, {"Q_next": 1}),
                ({"CLK": "posedge", "S": 1, "R": 1, "Q_prev": 0}, {"Q_next": "X"}),
            ]
        )
    if design_name == "counter_4bit":
        rows: list[TruthTableRow] = []
        for value in range(16):
            q_prev = format(value, "04b")
            q_next = format((value + 1) % 16, "04b")
            rows.append(
                TruthTableRow(
                    inputs={"CLK": "posedge", "EN": 1, "RST": 0, "Q_prev": q_prev},
                    outputs={"Q_next": q_next},
                )
            )
        rows.append(
            TruthTableRow(
                inputs={"CLK": "posedge", "EN": 1, "RST": 1, "Q_prev": "0000"},
                outputs={"Q_next": "0000"},
            )
        )
        rows.append(
            TruthTableRow(
                inputs={"CLK": "posedge", "EN": 0, "RST": 0, "Q_prev": "0101"},
                outputs={"Q_next": "0101"},
            )
        )
        return rows
    if design_name.startswith("counter_") and "bit" in design_name:
        width, _ff_kind = _counter_spec(design_name)
        zero = "0" * width
        rows: list[TruthTableRow] = []
        for value in range(1 << width):
            q_prev = format(value, f"0{width}b")
            q_next = format((value + 1) % (1 << width), f"0{width}b")
            rows.append(
                TruthTableRow(
                    inputs={"CLK": "posedge", "EN": 1, "RST": 0, "Q_prev": q_prev},
                    outputs={"Q_next": q_next},
                )
            )
        rows.append(
            TruthTableRow(
                inputs={"CLK": "posedge", "EN": 1, "RST": 1, "Q_prev": zero},
                outputs={"Q_next": zero},
            )
        )
        hold_state = format(min(5, (1 << width) - 1), f"0{width}b")
        rows.append(
            TruthTableRow(
                inputs={"CLK": "posedge", "EN": 0, "RST": 0, "Q_prev": hold_state},
                outputs={"Q_next": hold_state},
            )
        )
        return rows
    if design_name.startswith("shift_register_") and "bit" in design_name:
        width = _shift_register_spec(design_name)
        zero = "0" * width
        rows: list[TruthTableRow] = []
        rows.append(TruthTableRow(inputs={"CLK": "posedge", "RST": 1, "EN": 0, "D": 0, "Q_prev": zero}, outputs={"Q_next": zero}))
        rows.append(TruthTableRow(inputs={"CLK": "posedge", "RST": 0, "EN": 1, "D": 0, "Q_prev": zero}, outputs={"Q_next": zero[1:] + "0" if width > 1 else "0"}))
        rows.append(TruthTableRow(inputs={"CLK": "posedge", "RST": 0, "EN": 1, "D": 1, "Q_prev": zero}, outputs={"Q_next": zero[1:] + "1" if width > 1 else "1"}))
        sample_prev = ("10" * ((width + 1) // 2))[:width]
        sample_next = (sample_prev[1:] + "0") if width > 1 else "0"
        rows.append(TruthTableRow(inputs={"CLK": "posedge", "RST": 0, "EN": 1, "D": 0, "Q_prev": sample_prev}, outputs={"Q_next": sample_next}))
        rows.append(TruthTableRow(inputs={"CLK": "posedge", "RST": 0, "EN": 0, "D": 1, "Q_prev": sample_prev}, outputs={"Q_next": sample_prev}))
        return rows
    if design_name == "fsm_traffic_light":
        return _combine_rows(
            [
                ({"CLK": "posedge", "RESET": 1, "STATE": "S0", "TIMER_DONE": 0}, {"NEXT_STATE": "S0", "OUT": "NS_GREEN"}),
                ({"CLK": "posedge", "RESET": 0, "STATE": "S0", "TIMER_DONE": 1}, {"NEXT_STATE": "S1", "OUT": "NS_YELLOW"}),
                ({"CLK": "posedge", "RESET": 0, "STATE": "S1", "TIMER_DONE": 1}, {"NEXT_STATE": "S2", "OUT": "EW_GREEN"}),
                ({"CLK": "posedge", "RESET": 0, "STATE": "S2", "TIMER_DONE": 1}, {"NEXT_STATE": "S0", "OUT": "NS_GREEN"}),
            ]
        )
    if design_name.startswith("fifo_"):
        return _combine_rows(
            [
                ({"CLK": "posedge", "WR_EN": 1, "RD_EN": 0, "EMPTY": 1, "FULL": 0}, {"NEXT_EMPTY": 0, "NEXT_FULL": 0}),
                ({"CLK": "posedge", "WR_EN": 1, "RD_EN": 0, "EMPTY": 0, "FULL": 0}, {"NEXT_EMPTY": 0, "NEXT_FULL": 0}),
                ({"CLK": "posedge", "WR_EN": 0, "RD_EN": 1, "EMPTY": 0, "FULL": 0}, {"NEXT_EMPTY": 1, "NEXT_FULL": 0}),
                ({"CLK": "posedge", "WR_EN": 0, "RD_EN": 0, "EMPTY": 0, "FULL": 1}, {"NEXT_EMPTY": 0, "NEXT_FULL": 1}),
            ]
        )
    if design_name == "uart_tx_8n1":
        return _combine_rows(
            [
                ({"CLK": "posedge", "RST": 1, "START": 0, "STATE": "IDLE"}, {"NEXT_STATE": "IDLE", "TX": 1, "BUSY": 0, "DONE": 0}),
                ({"CLK": "posedge", "RST": 0, "START": 1, "STATE": "IDLE"}, {"NEXT_STATE": "START", "TX": 0, "BUSY": 1, "DONE": 0}),
                ({"CLK": "posedge", "RST": 0, "START": 0, "STATE": "START"}, {"NEXT_STATE": "DATA", "TX": "shift", "BUSY": 1, "DONE": 0}),
                ({"CLK": "posedge", "RST": 0, "START": 0, "STATE": "STOP"}, {"NEXT_STATE": "IDLE", "TX": 1, "BUSY": 0, "DONE": 1}),
            ]
        )
    if design_name == "uart_rx_8n1":
        return _combine_rows(
            [
                ({"CLK": "posedge", "RST": 1, "RX": 1, "STATE": "IDLE"}, {"NEXT_STATE": "IDLE", "DATA_READY": 0, "FRAME_ERR": 0}),
                ({"CLK": "posedge", "RST": 0, "RX": 0, "STATE": "IDLE"}, {"NEXT_STATE": "START", "DATA_READY": 0, "FRAME_ERR": 0}),
                ({"CLK": "posedge", "RST": 0, "RX": 0, "STATE": "DATA"}, {"NEXT_STATE": "DATA", "DATA_READY": 0, "FRAME_ERR": 0}),
                ({"CLK": "posedge", "RST": 0, "RX": 1, "STATE": "STOP"}, {"NEXT_STATE": "IDLE", "DATA_READY": 1, "FRAME_ERR": 0}),
            ]
        )
    if design_name == "spi_master_8bit":
        return _combine_rows(
            [
                ({"CLK": "posedge", "RST": 1, "START": 0, "STATE": "IDLE"}, {"NEXT_STATE": "IDLE", "CS": 1, "BUSY": 0, "DONE": 0}),
                ({"CLK": "posedge", "RST": 0, "START": 1, "STATE": "IDLE"}, {"NEXT_STATE": "SHIFT", "CS": 0, "BUSY": 1, "DONE": 0}),
                ({"CLK": "posedge", "RST": 0, "START": 0, "STATE": "SHIFT"}, {"NEXT_STATE": "SHIFT", "CS": 0, "BUSY": 1, "DONE": 0}),
                ({"CLK": "posedge", "RST": 0, "START": 0, "STATE": "DONE"}, {"NEXT_STATE": "IDLE", "CS": 1, "BUSY": 0, "DONE": 1}),
            ]
        )
    if design_name == "spi_slave_8bit":
        return _combine_rows(
            [
                ({"CLK": "posedge", "RST": 1, "SS_N": 1, "SCLK": 0, "STATE": "IDLE"}, {"NEXT_STATE": "IDLE", "MISO": 0, "DATA_READY": 0}),
                ({"CLK": "posedge", "RST": 0, "SS_N": 0, "SCLK": 0, "STATE": "CAPTURE"}, {"NEXT_STATE": "CAPTURE", "MISO": 0, "DATA_READY": 0}),
                ({"CLK": "posedge", "RST": 0, "SS_N": 0, "SCLK": 1, "STATE": "CAPTURE"}, {"NEXT_STATE": "CAPTURE", "MISO": "shift", "DATA_READY": 0}),
                ({"CLK": "posedge", "RST": 0, "SS_N": 1, "SCLK": 0, "STATE": "DONE"}, {"NEXT_STATE": "IDLE", "MISO": 0, "DATA_READY": 1}),
            ]
        )
    if design_name == "i2c_master_simple":
        return _combine_rows(
            [
                ({"CLK": "posedge", "RST": 1, "START": 0, "STATE": "IDLE"}, {"NEXT_STATE": "IDLE", "SCL": 1, "BUSY": 0, "DONE": 0}),
                ({"CLK": "posedge", "RST": 0, "START": 1, "STATE": "IDLE"}, {"NEXT_STATE": "START", "SCL": 1, "BUSY": 1, "DONE": 0}),
                ({"CLK": "posedge", "RST": 0, "START": 0, "STATE": "START"}, {"NEXT_STATE": "TRANSFER", "SCL": 0, "BUSY": 1, "DONE": 0}),
                ({"CLK": "posedge", "RST": 0, "START": 0, "STATE": "STOP"}, {"NEXT_STATE": "IDLE", "SCL": 1, "BUSY": 0, "DONE": 1}),
            ]
        )
    if design_name == "i2c_slave_simple":
        return _combine_rows(
            [
                ({"CLK": "posedge", "RST": 1, "SCL": 1, "SDA": 1, "STATE": "IDLE"}, {"NEXT_STATE": "IDLE", "ACK": 0, "DATA_READY": 0}),
                ({"CLK": "posedge", "RST": 0, "SCL": 1, "SDA": 0, "STATE": "ADDR"}, {"NEXT_STATE": "ADDR", "ACK": 0, "DATA_READY": 0}),
                ({"CLK": "posedge", "RST": 0, "SCL": 0, "SDA": 0, "STATE": "DATA"}, {"NEXT_STATE": "DATA", "ACK": 1, "DATA_READY": 0}),
                ({"CLK": "posedge", "RST": 0, "SCL": 1, "SDA": 1, "STATE": "STOP"}, {"NEXT_STATE": "IDLE", "ACK": 0, "DATA_READY": 1}),
            ]
        )
    if design_name == "axi_lite_slave_simple":
        return _combine_rows(
            [
                ({"CLK": "posedge", "ARESETN": 0, "AWVALID": 0, "WVALID": 0, "ARVALID": 0, "STATE": "IDLE"}, {"NEXT_STATE": "IDLE", "AWREADY": 0, "WREADY": 0, "BVALID": 0, "RVALID": 0}),
                ({"CLK": "posedge", "ARESETN": 1, "AWVALID": 1, "WVALID": 1, "ARVALID": 0, "STATE": "IDLE"}, {"NEXT_STATE": "WRITE", "AWREADY": 1, "WREADY": 1, "BVALID": 1, "RVALID": 0}),
                ({"CLK": "posedge", "ARESETN": 1, "AWVALID": 0, "WVALID": 0, "ARVALID": 1, "STATE": "IDLE"}, {"NEXT_STATE": "READ", "AWREADY": 0, "WREADY": 0, "BVALID": 0, "RVALID": 1}),
                ({"CLK": "posedge", "ARESETN": 1, "AWVALID": 0, "WVALID": 0, "ARVALID": 0, "STATE": "DONE"}, {"NEXT_STATE": "IDLE", "AWREADY": 0, "WREADY": 0, "BVALID": 0, "RVALID": 0}),
            ]
        )
    return []


def boolean_equation(design_name: str) -> str:
    if design_name.startswith("fifo_"):
        depth, width = _fifo_spec(design_name)
        return f"FIFO_{depth}x{width}: WR_EN advances write pointer, RD_EN advances read pointer; FULL/EMPTY derive from occupancy and reset clears pointers"
    if design_name.startswith("shift_register_") and "bit" in design_name:
        width = _shift_register_spec(design_name)
        return f"Q_next = {{Q_prev[{width - 2}:0], D}} when EN=1, else Q_next = Q_prev; reset drives Q_next = 0"
    if design_name == "uart_tx_8n1":
        return "FSM serializes 8 data bits with start and stop bits over TX using a baud tick and DONE/BUSY handshaking"
    if design_name == "uart_rx_8n1":
        return "FSM samples RX, detects start/stop bits, reconstructs 8 data bits, and asserts DATA_READY/BUSY/FRAME_ERR"
    if design_name == "spi_master_8bit":
        return "FSM shifts 8-bit data out on MOSI with SCLK and CS control, capturing MISO into DATA_OUT"
    if design_name == "spi_slave_8bit":
        return "FSM captures MOSI on SCLK edges when SS_N is low and shifts response data on MISO"
    if design_name == "i2c_master_simple":
        return "FSM sequences START, TRANSFER, and STOP phases using SCL/SDA open-drain control and ACK sampling"
    if design_name == "i2c_slave_simple":
        return "FSM detects START, samples address/data on SDA with SCL, and drives ACK on an open-drain SDA line"
    if design_name == "axi_lite_slave_simple":
        return "AXI-Lite slave handshake logic decodes write/read channels with address, data, and valid/ready signals"
    if mux_spec := _mux_spec(design_name):
        size, is_tree = mux_spec
        if is_tree:
            return f"Y = 2x1 mux tree of {size} inputs"
        select_bits = _mux_select_bits(size)
        terms = []
        for index in range(size):
            select_code = format(index, f"0{select_bits}b")
            literals = []
            for bit_index, bit in enumerate(select_code):
                sel_name = f"S{bit_index}"
                literals.append(f"~{sel_name}" if bit == "0" else sel_name)
            terms.append("(" + " & ".join(literals + [f"D{index}"]) + ")")
        return "Y = " + " | ".join(terms)
    equations = {
        "not": "Y = ~A",
        "buffer": "Y = A",
        "nand": "Y = ~(A & B)",
        "nor": "Y = ~(A | B)",
        "and": "Y = A & B",
        "or": "Y = A | B",
        "xor": "Y = A ^ B",
        "xnor": "Y = ~(A ^ B)",
        "half_adder": "SUM = A ^ B; COUT = A & B",
        "full_adder": "SUM = A ^ B ^ CIN; COUT = (A & B) | (CIN & (A ^ B))",
        "mux_2to1": "Y = (~S0 & D0) | (S0 & D1)",
        "mux_4to1": "Y = (~S1 & ~S0 & D0) | (~S1 & S0 & D1) | (S1 & ~S0 & D2) | (S1 & S0 & D3)",
        "mux_8to1": "Y = (~S2 & ~S1 & ~S0 & D0) | (~S2 & ~S1 & S0 & D1) | (~S2 & S1 & ~S0 & D2) | (~S2 & S1 & S0 & D3) | (S2 & ~S1 & ~S0 & D4) | (S2 & ~S1 & S0 & D5) | (S2 & S1 & ~S0 & D6) | (S2 & S1 & S0 & D7)",
        "mux_4to1_tree": "Y = mux_2to1 tree of 4 inputs",
        "mux_8to1_tree": "Y = mux_2to1 tree of 8 inputs",
        "demux_1to2": "Y0 = ~SEL & D; Y1 = SEL & D",
        "comparator": "EQ = ~(A ^ B); GT = A & ~B; LT = ~A & B",
        "decoder_2to4": "Y0 = ~A & ~B; Y1 = ~A & B; Y2 = A & ~B; Y3 = A & B",
        "encoder_4to2": "Y1 = D2 | D3; Y0 = D1 | D3",
        "priority_encoder_4to2": "Y1 = D2 | D3; Y0 = D1 | D3; VALID = D0 | D1 | D2 | D3",
        "dff": "Q_next = D on rising edge of CLK",
        "tff": "Q_next = T ? ~Q_prev : Q_prev on rising edge of CLK",
        "jkff": "Q_next = J ? ~Q_prev : (K ? 0 : Q_prev) on rising edge of CLK",
        "srff": "Q_next = S ? 1 : (R ? 0 : Q_prev) on rising edge of CLK",
        "counter_4bit": "Q_next = Q_prev + 1 when EN=1, else Q_next = Q_prev; reset drives Q_next = 0",
        "counter_3bit_dff": "Q_next = Q_prev + 1 when EN=1, else Q_next = Q_prev; reset drives Q_next = 0",
        "counter_3bit_tff": "Q_next = Q_prev + 1 when EN=1, else Q_next = Q_prev; T inputs toggle selected bits",
        "counter_3bit_jkff": "Q_next = Q_prev + 1 when EN=1, else Q_next = Q_prev; J/K inputs toggle selected bits",
        "counter_3bit_srff": "Q_next = Q_prev + 1 when EN=1, else Q_next = Q_prev; SR inputs drive set/reset",
        "shift_register_4bit": "Q_next = {Q_prev[2:0], D} when EN=1, else Q_next = Q_prev",
        "fsm_traffic_light": "STATE transitions through encoded traffic-light states based on TIMER_DONE and RESET",
        "fifo_4x8": "Write pointer and read pointer advance on WR_EN and RD_EN; status flags derive from occupancy",
        "uart_tx_8n1": "UART TX FSM: IDLE -> START -> DATA -> STOP with baud counter and shift register",
        "uart_rx_8n1": "UART RX FSM: IDLE -> START -> DATA -> STOP with baud counter, sample alignment, and shift register",
        "spi_master_8bit": "SPI master FSM: IDLE -> SHIFT -> DONE with SCLK, MOSI, CS, and shift register",
        "spi_slave_8bit": "SPI slave FSM: IDLE -> CAPTURE -> DONE with SS_N gating, SCLK edge sampling, and MISO drive",
        "i2c_master_simple": "I2C master FSM: IDLE -> START -> TRANSFER -> STOP with SCL/SDA open-drain behavior",
        "i2c_slave_simple": "I2C slave FSM: IDLE -> ADDRESS -> DATA -> ACK with open-drain SDA behavior",
        "axi_lite_slave_simple": "AXI-Lite slave FSM: IDLE -> WRITE/READ -> RESP with ready/valid handshakes and register file access",
    }
    return equations.get(design_name, "")


def gate_count_for(design_name: str) -> int:
    if design_name.startswith("fifo_"):
        depth, width = _fifo_spec(design_name)
        return max(24, depth * width // 2 + depth * 4)
    if design_name.startswith("shift_register_") and "bit" in design_name:
        width = _shift_register_spec(design_name)
        return max(4, width * 3)
    if design_name == "uart_tx_8n1":
        return 18
    if design_name == "uart_rx_8n1":
        return 20
    if design_name == "spi_master_8bit":
        return 24
    if design_name == "spi_slave_8bit":
        return 22
    if design_name == "i2c_master_simple":
        return 22
    if design_name == "i2c_slave_simple":
        return 20
    if design_name == "axi_lite_slave_simple":
        return 28
    if mux_spec := _mux_spec(design_name):
        size, is_tree = mux_spec
        return max(4, 3 * size - 3) if is_tree else max(4, 3 * size)
    counts = {
        "not": 1,
        "buffer": 2,
        "nand": 2,
        "nor": 2,
        "and": 3,
        "or": 3,
        "xor": 6,
        "xnor": 6,
        "half_adder": 6,
        "full_adder": 12,
        "mux_2to1": 4,
        "mux_4to1": 12,
        "mux_8to1": 24,
        "mux_16to1": 48,
        "mux_4to1_tree": 9,
        "mux_8to1_tree": 21,
        "mux_16to1_tree": 45,
        "demux_1to2": 4,
        "comparator": 5,
        "decoder_2to4": 4,
        "encoder_4to2": 4,
        "priority_encoder_4to2": 6,
        "dff": 1,
        "tff": 1,
        "jkff": 2,
        "srff": 2,
        "counter_4bit": 16,
        "counter_3bit_dff": 12,
        "counter_3bit_tff": 9,
        "counter_3bit_jkff": 9,
        "counter_3bit_srff": 9,
        "shift_register_4bit": 4,
        "fsm_traffic_light": 6,
        "fifo_4x8": 24,
        "uart_tx_8n1": 18,
        "uart_rx_8n1": 20,
        "spi_master_8bit": 24,
        "spi_slave_8bit": 22,
        "i2c_master_simple": 22,
        "i2c_slave_simple": 20,
        "axi_lite_slave_simple": 28,
    }
    return counts.get(design_name, 0)


def abstraction_for(gate_count: int) -> str:
    if gate_count <= 0:
        return "gate_level"
    return "transistor_level" if gate_count <= 10 else "gate_level"


def recommend_technology_node(gate_count: int, abstraction: str) -> str:
    if abstraction == "transistor_level":
        if gate_count <= 2:
            return "180nm"
        if gate_count <= 4:
            return "130nm"
        return "90nm"
    if gate_count <= 6:
        return "65nm"
    if gate_count <= 10:
        return "45nm"
    if gate_count <= 15:
        return "28nm"
    return "14nm"


def transistor_network(design_name: str) -> tuple[list[NetworkElement], list[NetworkElement]]:
    if design_name == "not":
        return (
            [NetworkElement(name="P1", source="VDD", drain="Y", gate="A", bulk="VDD", kind="pmos")],
            [NetworkElement(name="N1", source="Y", drain="GND", gate="A", bulk="GND", kind="nmos")],
        )
    if design_name == "buffer":
        return (
            [
                NetworkElement(name="P1", source="VDD", drain="N1", gate="A", bulk="VDD", kind="pmos"),
                NetworkElement(name="P2", source="N1", drain="Y", gate="N1", bulk="VDD", kind="pmos"),
            ],
            [
                NetworkElement(name="N1", source="Y", drain="N2", gate="A", bulk="GND", kind="nmos"),
                NetworkElement(name="N2", source="N2", drain="GND", gate="N2", bulk="GND", kind="nmos"),
            ],
        )
    if design_name == "nand":
        return (
            [
                NetworkElement(name="P1", source="VDD", drain="Y", gate="A", bulk="VDD", kind="pmos"),
                NetworkElement(name="P2", source="VDD", drain="Y", gate="B", bulk="VDD", kind="pmos"),
            ],
            [
                NetworkElement(name="N1", source="Y", drain="N1", gate="A", bulk="GND", kind="nmos"),
                NetworkElement(name="N2", source="N1", drain="GND", gate="B", bulk="GND", kind="nmos"),
            ],
        )
    if design_name == "nor":
        return (
            [
                NetworkElement(name="P1", source="VDD", drain="N1", gate="A", bulk="VDD", kind="pmos"),
                NetworkElement(name="P2", source="N1", drain="Y", gate="B", bulk="VDD", kind="pmos"),
            ],
            [
                NetworkElement(name="N1", source="Y", drain="GND", gate="A", bulk="GND", kind="nmos"),
                NetworkElement(name="N2", source="Y", drain="GND", gate="B", bulk="GND", kind="nmos"),
            ],
        )
    if design_name == "and":
        pmos, nmos = transistor_network("nand")
        return (
            pmos + [NetworkElement(name="P3", source="Y", drain="VDD", gate="N1", bulk="VDD", kind="pmos")],
            nmos + [NetworkElement(name="N3", source="N1", drain="GND", gate="N1", bulk="GND", kind="nmos")],
        )
    if design_name == "or":
        pmos, nmos = transistor_network("nor")
        return (
            pmos + [NetworkElement(name="P3", source="N1", drain="Y", gate="N1", bulk="VDD", kind="pmos")],
            nmos + [NetworkElement(name="N3", source="Y", drain="GND", gate="N1", bulk="GND", kind="nmos")],
        )
    return [], []


def transistor_sizing(technology_node: str, abstraction: str, design_name: str) -> dict[str, str]:
    node_scale = {
        "180nm": ("1.0u", "0.18u"),
        "130nm": ("0.8u", "0.13u"),
        "90nm": ("0.6u", "90nm"),
        "65nm": ("0.5u", "65nm"),
        "45nm": ("0.4u", "45nm"),
        "28nm": ("0.3u", "28nm"),
        "14nm": ("0.2u", "14nm"),
        "7nm": ("0.15u", "7nm"),
    }
    pmos_width, length = node_scale.get(technology_node, ("0.5u", technology_node))
    width_multiplier = "2x" if abstraction == "transistor_level" else "1.5x"
    if design_name in {"xor", "xnor", "full_adder"} or _mux_spec(design_name):
        width_multiplier = "2.5x"
    return {
        "pmos_width": f"{width_multiplier} {pmos_width}",
        "pmos_length": length,
        "nmos_width": f"1x {pmos_width}",
        "nmos_length": length,
    }


def build_gate_level_design(design_name: str, inputs: list[str], outputs: list[str], abstraction: str) -> dict[str, Any]:
    if abstraction == "transistor_level":
        return {
            "abstraction": abstraction,
            "blocks": [f"CMOS_{design_name.upper()}"],
            "connections": [],
        }

    if design_name.startswith("fifo_"):
        depth, width = _fifo_spec(design_name)
        return {
            "abstraction": abstraction,
            "blocks": [f"MEMORY[{depth}x{width}]", "WRITE PTR", "READ PTR", "FULL/EMPTY LOGIC"],
            "connections": [],
        }

    if design_name == "uart_tx_8n1":
        return {
            "abstraction": abstraction,
            "blocks": ["UART FSM", "BAUD COUNTER", "SHIFT REGISTER", "TX OUTPUT"],
            "connections": [],
            "inputs": inputs,
            "outputs": outputs,
        }
    if design_name == "uart_rx_8n1":
        return {
            "abstraction": abstraction,
            "blocks": ["UART RX FSM", "BAUD COUNTER", "SHIFT REGISTER", "START/STOP CHECK", "RX OUTPUT"],
            "connections": [],
            "inputs": inputs,
            "outputs": outputs,
        }
    if design_name == "spi_master_8bit":
        return {
            "abstraction": abstraction,
            "blocks": ["SPI FSM", "SCLK DIVIDER", "SHIFT REGISTER", "CS CONTROL"],
            "connections": [],
            "inputs": inputs,
            "outputs": outputs,
        }
    if design_name == "spi_slave_8bit":
        return {
            "abstraction": abstraction,
            "blocks": ["SPI SLAVE FSM", "SHIFT REGISTER", "SCLK EDGE DETECTOR", "MISO OUTPUT"],
            "connections": [],
            "inputs": inputs,
            "outputs": outputs,
        }
    if design_name == "i2c_master_simple":
        return {
            "abstraction": abstraction,
            "blocks": ["I2C FSM", "SCL GEN", "SDA OPEN-DRAIN CTRL", "ACK LOGIC"],
            "connections": [],
            "inputs": inputs,
            "outputs": outputs,
        }
    if design_name == "i2c_slave_simple":
        return {
            "abstraction": abstraction,
            "blocks": ["I2C SLAVE FSM", "START DETECTOR", "ADDRESS MATCH", "ACK DRIVER"],
            "connections": [],
            "inputs": inputs,
            "outputs": outputs,
        }
    if design_name == "axi_lite_slave_simple":
        return {
            "abstraction": abstraction,
            "blocks": ["AXI-LITE SLAVE FSM", "WRITE CHANNEL", "READ CHANNEL", "REGISTER FILE"],
            "connections": [],
            "inputs": inputs,
            "outputs": outputs,
        }

    if design_name.startswith("shift_register_") and "bit" in design_name:
        width = _shift_register_spec(design_name)
        return {
            "abstraction": abstraction,
            "blocks": ["DFF"] * width + ["MUX", "RST LOGIC"],
            "connections": [],
            "inputs": inputs,
            "outputs": outputs,
        }

    if mux_spec := _mux_spec(design_name):
        size, is_tree = mux_spec
        if is_tree:
            blocks = ["MUX_2TO1"] * max(1, size - 1)
        else:
            select_bits = _mux_select_bits(size)
            blocks = ["NOT"] * select_bits + ["AND"] * size + ["OR"] * max(1, size - 1)
        return {
            "abstraction": abstraction,
            "blocks": blocks,
            "connections": [],
            "inputs": inputs,
            "outputs": outputs,
        }

    blocks = {
        "half_adder": ["XOR", "AND"],
        "full_adder": ["XOR", "AND", "OR"],
        "demux_1to2": ["NOT", "AND"],
        "comparator": ["XNOR", "AND", "NOT"],
        "decoder_2to4": ["NOT", "NOT", "AND", "AND", "AND", "AND"],
        "encoder_4to2": ["OR", "OR"],
        "priority_encoder_4to2": ["OR", "OR", "AND", "AND", "AND", "AND"],
        "dff": ["DFF"],
        "tff": ["XOR", "DFF"],
        "jkff": ["AND", "OR", "DFF"],
        "srff": ["AND", "OR", "DFF"],
        "counter_4bit": ["ADD", "MUX", "DFF"],
        "counter_3bit_dff": ["ADD", "MUX", "DFF"],
        "counter_3bit_tff": ["TFF", "AND"],
        "counter_3bit_jkff": ["JKFF", "AND"],
        "counter_3bit_srff": ["SRFF", "AND"],
        "shift_register_4bit": ["MUX", "DFF"],
        "fsm_traffic_light": ["STATE REG", "NEXT STATE LOGIC", "OUTPUT DECODE"],
        "fifo_4x8": ["MEMORY", "WRITE PTR", "READ PTR", "FULL/EMPTY LOGIC"],
    }.get(design_name, ["UNSUPPORTED_DESIGN"] if design_name == "unsupported_design" else [design_name.upper()])

    return {
        "abstraction": abstraction,
        "blocks": blocks,
        "connections": [],
        "inputs": inputs,
        "outputs": outputs,
    }


def _verilog_module_name(design_name: str) -> str:
    return design_name.replace(" ", "_")


def verilog_for(design_name: str) -> str:
    if design_name == "not":
        return """module not_gate(input wire A, output wire Y);
    assign Y = ~A;
endmodule
"""
    if design_name == "buffer":
        return """module buffer_gate(input wire A, output wire Y);
    assign Y = A;
endmodule
"""
    if design_name == "nand":
        return """module nand_gate(input wire A, input wire B, output wire Y);
    assign Y = ~(A & B);
endmodule
"""
    if design_name == "nor":
        return """module nor_gate(input wire A, input wire B, output wire Y);
    assign Y = ~(A | B);
endmodule
"""
    if design_name == "and":
        return """module and_gate(input wire A, input wire B, output wire Y);
    assign Y = A & B;
endmodule
"""
    if design_name == "or":
        return """module or_gate(input wire A, input wire B, output wire Y);
    assign Y = A | B;
endmodule
"""
    if design_name == "xor":
        return """module xor_gate(input wire A, input wire B, output wire Y);
    assign Y = A ^ B;
endmodule
"""
    if design_name == "xnor":
        return """module xnor_gate(input wire A, input wire B, output wire Y);
    assign Y = ~(A ^ B);
endmodule
"""
    if design_name == "half_adder":
        return """module half_adder(input wire A, input wire B, output wire SUM, output wire COUT);
    assign SUM = A ^ B;
    assign COUT = A & B;
endmodule
"""
    if design_name == "full_adder":
        return """module full_adder(input wire A, input wire B, input wire CIN, output wire SUM, output wire COUT);
    assign SUM = A ^ B ^ CIN;
    assign COUT = (A & B) | (CIN & (A ^ B));
endmodule
"""
    if design_name == "mux_2to1":
        return """module mux_2to1(input wire S0, input wire D0, input wire D1, output wire Y);
    assign Y = S0 ? D1 : D0;
endmodule
"""
    if design_name == "mux_4to1":
        return """module mux_4to1(
    input wire S0,
    input wire S1,
    input wire D0,
    input wire D1,
    input wire D2,
    input wire D3,
    output wire Y
);
    assign Y = (~S1 & ~S0 & D0) |
               (~S1 & S0 & D1) |
               (S1 & ~S0 & D2) |
               (S1 & S0 & D3);
endmodule
"""
    if design_name == "mux_8to1":
        return """module mux_8to1(
    input wire S0,
    input wire S1,
    input wire S2,
    input wire D0,
    input wire D1,
    input wire D2,
    input wire D3,
    input wire D4,
    input wire D5,
    input wire D6,
    input wire D7,
    output wire Y
);
    assign Y = (~S2 & ~S1 & ~S0 & D0) |
               (~S2 & ~S1 & S0 & D1) |
               (~S2 & S1 & ~S0 & D2) |
               (~S2 & S1 & S0 & D3) |
               (S2 & ~S1 & ~S0 & D4) |
               (S2 & ~S1 & S0 & D5) |
               (S2 & S1 & ~S0 & D6) |
               (S2 & S1 & S0 & D7);
endmodule
"""
    if design_name == "demux_1to2":
        return """module demux_1to2(input wire SEL, input wire D, output wire Y0, output wire Y1);
    assign Y0 = (~SEL) & D;
    assign Y1 = SEL & D;
endmodule
"""
    if design_name == "comparator":
        return """module comparator_1bit(input wire A, input wire B, output wire EQ, output wire GT, output wire LT);
    assign EQ = ~(A ^ B);
    assign GT = A & ~B;
    assign LT = ~A & B;
endmodule
"""
    if design_name == "decoder_2to4":
        return """module decoder_2to4(input wire A, input wire B, output wire Y0, output wire Y1, output wire Y2, output wire Y3);
    assign Y0 = ~A & ~B;
    assign Y1 = ~A & B;
    assign Y2 = A & ~B;
    assign Y3 = A & B;
endmodule
"""
    if design_name == "encoder_4to2":
        return """module encoder_4to2(input wire D0, input wire D1, input wire D2, input wire D3, output wire Y1, output wire Y0);
    assign Y1 = D2 | D3;
    assign Y0 = D1 | D3;
endmodule
"""
    if design_name == "priority_encoder_4to2":
        return """module priority_encoder_4to2(input wire D0, input wire D1, input wire D2, input wire D3, output wire Y1, output wire Y0, output wire VALID);
    assign VALID = D0 | D1 | D2 | D3;
    assign Y1 = D2 | D3;
    assign Y0 = D1 | D3;
endmodule
"""
    if design_name == "dff":
        return """module dff(input wire CLK, input wire D, output reg Q);
    wire Q_next;
    assign Q_next = D;
    always @(posedge CLK) begin
        Q <= Q_next;
    end
endmodule
"""
    if design_name == "tff":
        return """module tff(input wire CLK, input wire T, output reg Q);
    wire Q_next;
    assign Q_next = T ? ~Q : Q;
    always @(posedge CLK) begin
        Q <= Q_next;
    end
endmodule
"""
    if design_name == "jkff":
        return """module jkff(input wire CLK, input wire J, input wire K, output reg Q);
    wire Q_next;
    assign Q_next = ({J, K} == 2'b00) ? Q :
                    ({J, K} == 2'b01) ? 1'b0 :
                    ({J, K} == 2'b10) ? 1'b1 :
                    ~Q;
    always @(posedge CLK) begin
        Q <= Q_next;
    end
endmodule
"""
    if design_name == "srff":
        return """module srff(input wire CLK, input wire S, input wire R, output reg Q);
    wire Q_next;
    assign Q_next = ({S, R} == 2'b00) ? Q :
                    ({S, R} == 2'b01) ? 1'b0 :
                    ({S, R} == 2'b10) ? 1'b1 :
                    1'b0;
    always @(posedge CLK) begin
        Q <= Q_next;
    end
endmodule
"""
    if design_name.startswith("fifo_"):
        return _fifo_family_verilog(design_name, "dataflow")
    if design_name in {"counter_4bit", "shift_register_4bit", "fsm_traffic_light", "fifo_4x8"}:
        return _sequential_family_verilog(design_name, "dataflow")
    if design_name.startswith("counter_"):
        return _counter_family_verilog(design_name, "dataflow")
    if design_name in {"mux_4to1_tree", "mux_8to1_tree"}:
        return _mux_tree_verilog(design_name, "dataflow")
    return f"""module {_verilog_module_name(design_name)}(input wire A, input wire B, output wire Y);
    // Unsupported design placeholder: {design_name}
    assign Y = 1'b0;
endmodule
"""


def build_diagram(contract: Any) -> dict[str, Any]:
    title = contract.design_name.replace("_", " ").title() if contract.design_name else "Design"

    if contract.abstraction == "transistor_level":
        inputs = contract.inputs or ["A", "B"]
        nodes = [
            DiagramNode(id="input_0", type="input", position={"x": 40, "y": 120}, data={"label": inputs[0] if inputs else "A"}),
            DiagramNode(id="input_1", type="input", position={"x": 40, "y": 220}, data={"label": inputs[1] if len(inputs) > 1 else "B"}),
            DiagramNode(id="pmos", type="default", position={"x": 300, "y": 80}, data={"label": "PMOS Network"}),
            DiagramNode(id="nmos", type="default", position={"x": 300, "y": 240}, data={"label": "NMOS Network"}),
            DiagramNode(id="output_y", type="output", position={"x": 560, "y": 160}, data={"label": (contract.outputs[0] if contract.outputs else "Y")}),
        ]
        edges = [
            DiagramEdge(id="e1", source="input_0", target="pmos"),
            DiagramEdge(id="e2", source="input_1", target="pmos"),
            DiagramEdge(id="e3", source="input_0", target="nmos"),
            DiagramEdge(id="e4", source="input_1", target="nmos"),
            DiagramEdge(id="e5", source="pmos", target="output_y"),
            DiagramEdge(id="e6", source="nmos", target="output_y"),
        ]
    else:
        blocks = contract.gate_level_design.get("blocks", []) if isinstance(contract.gate_level_design, dict) else []
        nodes = [DiagramNode(id="input", type="input", position={"x": 40, "y": 160}, data={"label": "Inputs"})]
        for index, block in enumerate(blocks):
            nodes.append(
                DiagramNode(
                    id=f"block_{index}",
                    type="default",
                    position={"x": 240 + index * 180, "y": 140},
                    data={"label": block},
                )
            )
        nodes.append(
            DiagramNode(
                id="output",
                type="output",
                position={"x": 240 + max(len(blocks), 1) * 180, "y": 160},
                data={"label": "Outputs"},
            )
        )
        edges = []
        previous_id = "input"
        for index, _ in enumerate(blocks):
            current_id = f"block_{index}"
            edges.append(DiagramEdge(id=f"e{index}", source=previous_id, target=current_id))
            previous_id = current_id
        edges.append(DiagramEdge(id="e_out", source=previous_id, target="output"))

    return {
        "title": title,
        "nodes": [node.model_dump() for node in nodes],
        "edges": [edge.model_dump() for edge in edges],
    }


def build_documentation(contract: Any) -> str:
    truth_lines = [f"- Inputs: {row.inputs} -> Outputs: {row.outputs}" for row in contract.truth_table]
    truth_section = "\n".join(truth_lines) if truth_lines else "- No truth table generated."

    knowledge_lines = []
    for item in getattr(contract, "knowledge_contexts", []) or []:
        knowledge_lines.append(f"- {item.get('title', 'Knowledge')} [{item.get('source', 'unknown')}]: {item.get('snippet', '')}")
    knowledge_section = "\n".join(knowledge_lines) if knowledge_lines else "- No retrieved knowledge."

    rules = fpga_requirements_for(contract)
    implementation_plan = fpga_implementation_plan(contract)
    implementation_lines = [
        f"- Synthesizable: {implementation_plan.get('synthesizable', True)}",
        f"- Vivado compatible: {implementation_plan.get('vivado_compatible', True)}",
        f"- Board ready: {implementation_plan.get('board_ready', True)}",
        f"- Resource mapping: {', '.join(implementation_plan.get('resource_mapping', []))}",
        f"- Constraints needed: {', '.join(implementation_plan.get('constraints_needed', []))}",
        f"- Verification steps: {', '.join(implementation_plan.get('verification_steps', []))}",
        f"- Notes: {implementation_plan.get('notes', '')}",
    ]
    implementation_section = "\n".join(implementation_lines)

    return (
        "# Design Summary\n\n"
        f"- Design type: {contract.design_type}\n"
        f"- Selected abstraction: {contract.abstraction}\n"
        f"- Modeling style: {getattr(contract, 'modeling_style', 'dataflow')}\n"
        f"- Implementation profile: {getattr(contract, 'implementation_profile', 'combinational')}\n"
        f"- Technology node: {contract.technology_node}\n"
        f"- Gate count: {contract.gate_count}\n"
        f"- Boolean equation: {contract.boolean_equation}\n\n"
        "## FPGA Implementation Plan\n"
        f"{implementation_section}\n\n"
        "## FPGA Implementation Requirements\n"
        f"{rules}\n\n"
        "## Truth Table\n"
        f"{truth_section}\n"
        "\n## Retrieved Knowledge\n"
        f"{knowledge_section}\n"
    )


def _protocol_testbench(contract: Any) -> str:
    design_name = getattr(contract, "design_name", "").lower().strip()
    if design_name == "uart_tx_8n1":
        return """`timescale 1ns/1ps
module uart_tx_8n1_tb;
    reg CLK;
    reg RST;
    reg START;
    reg [7:0] DATA_IN;
    wire TX;
    wire BUSY;
    wire DONE;

    uart_tx_8n1 dut(
        .CLK(CLK),
        .RST(RST),
        .START(START),
        .DATA_IN(DATA_IN),
        .TX(TX),
        .BUSY(BUSY),
        .DONE(DONE)
    );

    always #5 CLK = ~CLK;

    initial begin
        $display("uart_tx_8n1_tb");
        CLK = 1'b0;
        RST = 1'b1;
        START = 1'b0;
        DATA_IN = 8'hA5;
        #12 RST = 1'b0;
        #10 START = 1'b1;
        #10 START = 1'b0;
        repeat (48) @(posedge CLK);
        $finish;
    end
endmodule
"""
    if design_name == "spi_master_8bit":
        return """`timescale 1ns/1ps
module spi_master_8bit_tb;
    reg CLK;
    reg RST;
    reg START;
    reg MISO;
    reg [7:0] DATA_IN;
    wire SCLK;
    wire MOSI;
    wire CS;
    wire BUSY;
    wire DONE;
    wire [7:0] DATA_OUT;

    spi_master_8bit dut(
        .CLK(CLK),
        .RST(RST),
        .START(START),
        .MISO(MISO),
        .DATA_IN(DATA_IN),
        .SCLK(SCLK),
        .MOSI(MOSI),
        .CS(CS),
        .BUSY(BUSY),
        .DONE(DONE),
        .DATA_OUT(DATA_OUT)
    );

    always #5 CLK = ~CLK;

    initial begin
        $display("spi_master_8bit_tb");
        CLK = 1'b0;
        RST = 1'b1;
        START = 1'b0;
        MISO = 1'b0;
        DATA_IN = 8'h3C;
        #12 RST = 1'b0;
        #10 START = 1'b1;
        #10 START = 1'b0;
        repeat (16) @(posedge CLK);
        MISO = 1'b1;
        repeat (24) @(posedge CLK);
        $finish;
    end
endmodule
"""
    if design_name == "i2c_master_simple":
        return """`timescale 1ns/1ps
module i2c_master_simple_tb;
    reg CLK;
    reg RST;
    reg START;
    reg SDA_IN;
    reg [6:0] ADDR;
    reg [7:0] DATA_IN;
    wire SCL;
    wire SDA_OUT;
    wire SDA_OE;
    wire BUSY;
    wire DONE;
    wire ACK;

    i2c_master_simple dut(
        .CLK(CLK),
        .RST(RST),
        .START(START),
        .SDA_IN(SDA_IN),
        .ADDR(ADDR),
        .DATA_IN(DATA_IN),
        .SCL(SCL),
        .SDA_OUT(SDA_OUT),
        .SDA_OE(SDA_OE),
        .BUSY(BUSY),
        .DONE(DONE),
        .ACK(ACK)
    );

    always #5 CLK = ~CLK;

    initial begin
        $display("i2c_master_simple_tb");
        CLK = 1'b0;
        RST = 1'b1;
        START = 1'b0;
        SDA_IN = 1'b1;
        ADDR = 7'h50;
        DATA_IN = 8'hC3;
        #12 RST = 1'b0;
        #10 START = 1'b1;
        #10 START = 1'b0;
        repeat (20) @(posedge CLK);
        SDA_IN = 1'b0;
        repeat (20) @(posedge CLK);
        $finish;
    end
endmodule
"""
    if design_name == "uart_rx_8n1":
        return """`timescale 1ns/1ps
module uart_rx_8n1_tb;
    reg CLK;
    reg RST;
    reg RX;
    reg ENABLE;
    wire [7:0] DATA_OUT;
    wire DATA_READY;
    wire BUSY;
    wire FRAME_ERR;

    uart_rx_8n1 dut(
        .CLK(CLK),
        .RST(RST),
        .RX(RX),
        .ENABLE(ENABLE),
        .DATA_OUT(DATA_OUT),
        .DATA_READY(DATA_READY),
        .BUSY(BUSY),
        .FRAME_ERR(FRAME_ERR)
    );

    always #5 CLK = ~CLK;

    initial begin
        $display("uart_rx_8n1_tb");
        CLK = 1'b0;
        RST = 1'b1;
        RX = 1'b1;
        ENABLE = 1'b0;
        #12 RST = 1'b0;
        ENABLE = 1'b1;
        #10 RX = 1'b0;
        repeat (8) @(posedge CLK);
        RX = 1'b1;
        repeat (24) @(posedge CLK);
        $finish;
    end
endmodule
"""
    if design_name == "spi_slave_8bit":
        return """`timescale 1ns/1ps
module spi_slave_8bit_tb;
    reg CLK;
    reg RST;
    reg SS_N;
    reg SCLK;
    reg MOSI;
    reg MISO_IN;
    wire MISO;
    wire [7:0] DATA_OUT;
    wire DATA_READY;
    wire BUSY;

    spi_slave_8bit dut(
        .CLK(CLK),
        .RST(RST),
        .SS_N(SS_N),
        .SCLK(SCLK),
        .MOSI(MOSI),
        .MISO_IN(MISO_IN),
        .MISO(MISO),
        .DATA_OUT(DATA_OUT),
        .DATA_READY(DATA_READY),
        .BUSY(BUSY)
    );

    always #5 CLK = ~CLK;

    initial begin
        $display("spi_slave_8bit_tb");
        CLK = 1'b0;
        RST = 1'b1;
        SS_N = 1'b1;
        SCLK = 1'b0;
        MOSI = 1'b0;
        MISO_IN = 1'b1;
        #12 RST = 1'b0;
        #10 SS_N = 1'b0;
        repeat (8) begin
            #5 SCLK = 1'b1;
            #5 SCLK = 1'b0;
        end
        #10 SS_N = 1'b1;
        repeat (8) @(posedge CLK);
        $finish;
    end
endmodule
"""
    if design_name == "i2c_slave_simple":
        return """`timescale 1ns/1ps
module i2c_slave_simple_tb;
    reg CLK;
    reg RST;
    reg SCL;
    reg SDA_IN;
    reg [6:0] ADDR;
    reg [7:0] DATA_IN;
    wire SDA_OUT;
    wire SDA_OE;
    wire BUSY;
    wire DONE;
    wire ACK;
    wire DATA_READY;

    i2c_slave_simple dut(
        .CLK(CLK),
        .RST(RST),
        .SCL(SCL),
        .SDA_IN(SDA_IN),
        .ADDR(ADDR),
        .DATA_IN(DATA_IN),
        .SDA_OUT(SDA_OUT),
        .SDA_OE(SDA_OE),
        .BUSY(BUSY),
        .DONE(DONE),
        .ACK(ACK),
        .DATA_READY(DATA_READY)
    );

    always #5 CLK = ~CLK;

    initial begin
        $display("i2c_slave_simple_tb");
        CLK = 1'b0;
        RST = 1'b1;
        SCL = 1'b1;
        SDA_IN = 1'b1;
        ADDR = 7'h50;
        DATA_IN = 8'hA5;
        #12 RST = 1'b0;
        #10 SDA_IN = 1'b0;
        repeat (16) begin
            #5 SCL = 1'b0;
            #5 SCL = 1'b1;
        end
        #10 SDA_IN = 1'b1;
        repeat (10) @(posedge CLK);
        $finish;
    end
endmodule
"""
    if design_name == "axi_lite_slave_simple":
        return """`timescale 1ns/1ps
module axi_lite_slave_simple_tb;
    reg ACLK;
    reg ARESETN;
    reg [31:0] AWADDR;
    reg AWVALID;
    reg [31:0] WDATA;
    reg WVALID;
    reg [31:0] ARADDR;
    reg ARVALID;
    reg RREADY;
    reg [3:0] WSTRB;
    wire AWREADY;
    wire WREADY;
    wire BVALID;
    wire [1:0] BRESP;
    wire ARREADY;
    wire [31:0] RDATA;
    wire RVALID;
    wire [1:0] RRESP;

    axi_lite_slave_simple dut(
        .ACLK(ACLK),
        .ARESETN(ARESETN),
        .AWADDR(AWADDR),
        .AWVALID(AWVALID),
        .WDATA(WDATA),
        .WVALID(WVALID),
        .ARADDR(ARADDR),
        .ARVALID(ARVALID),
        .RREADY(RREADY),
        .WSTRB(WSTRB),
        .AWREADY(AWREADY),
        .WREADY(WREADY),
        .BVALID(BVALID),
        .BRESP(BRESP),
        .ARREADY(ARREADY),
        .RDATA(RDATA),
        .RVALID(RVALID),
        .RRESP(RRESP)
    );

    always #5 ACLK = ~ACLK;

    initial begin
        $display("axi_lite_slave_simple_tb");
        ACLK = 1'b0;
        ARESETN = 1'b0;
        AWADDR = 32'h0000_0000;
        AWVALID = 1'b0;
        WDATA = 32'h0000_0001;
        WVALID = 1'b0;
        ARADDR = 32'h0000_0000;
        ARVALID = 1'b0;
        RREADY = 1'b0;
        WSTRB = 4'hF;
        #12 ARESETN = 1'b1;
        #10 AWVALID = 1'b1; WVALID = 1'b1;
        #10 AWVALID = 1'b0; WVALID = 1'b0;
        #20 ARVALID = 1'b1;
        #10 ARVALID = 1'b0;
        RREADY = 1'b1;
        repeat (8) @(posedge ACLK);
        $finish;
    end
endmodule
"""
    if design_name == "uart_rx_8n1":
        if style == "behavioral":
            return """module uart_rx_8n1(
    input wire CLK,
    input wire RST,
    input wire RX,
    input wire ENABLE,
    output reg [7:0] DATA_OUT,
    output reg DATA_READY,
    output reg BUSY,
    output reg FRAME_ERR
);
    localparam IDLE = 3'd0, START_BIT = 3'd1, DATA_BITS = 3'd2, STOP_BIT = 3'd3;
    reg [2:0] STATE;
    reg [2:0] BIT_IDX;
    reg [3:0] BAUD_CNT;
    reg [7:0] SHIFT;
    always @(posedge CLK) begin
        if (RST) begin
            STATE <= IDLE; BIT_IDX <= 3'd0; BAUD_CNT <= 4'd0; SHIFT <= 8'd0;
            DATA_OUT <= 8'd0; DATA_READY <= 1'b0; BUSY <= 1'b0; FRAME_ERR <= 1'b0;
        end else begin
            DATA_READY <= 1'b0; FRAME_ERR <= 1'b0;
            case (STATE)
                IDLE: begin BUSY <= 1'b0; if (ENABLE && !RX) begin STATE <= START_BIT; BUSY <= 1'b1; BAUD_CNT <= 4'd0; end end
                START_BIT: begin BUSY <= 1'b1; if (BAUD_CNT == 4'd3) begin STATE <= DATA_BITS; BAUD_CNT <= 4'd0; BIT_IDX <= 3'd0; end else BAUD_CNT <= BAUD_CNT + 4'd1; end
                DATA_BITS: begin BUSY <= 1'b1; if (BAUD_CNT == 4'd3) begin SHIFT <= {RX, SHIFT[7:1]}; BAUD_CNT <= 4'd0; if (BIT_IDX == 3'd7) STATE <= STOP_BIT; else BIT_IDX <= BIT_IDX + 3'd1; end else BAUD_CNT <= BAUD_CNT + 4'd1; end
                STOP_BIT: begin BUSY <= 1'b1; if (BAUD_CNT == 4'd3) begin STATE <= IDLE; DATA_OUT <= SHIFT; DATA_READY <= 1'b1; BUSY <= 1'b0; FRAME_ERR <= ~RX; end else BAUD_CNT <= BAUD_CNT + 4'd1; end
            endcase
        end
    end
endmodule
"""
        return """module uart_rx_8n1(
    input wire CLK,
    input wire RST,
    input wire RX,
    input wire ENABLE,
    output reg [7:0] DATA_OUT,
    output reg DATA_READY,
    output reg BUSY,
    output reg FRAME_ERR
);
    localparam IDLE = 3'd0, START_BIT = 3'd1, DATA_BITS = 3'd2, STOP_BIT = 3'd3;
    reg [2:0] STATE;
    reg [2:0] BIT_IDX;
    reg [3:0] BAUD_CNT;
    reg [7:0] SHIFT;
    wire [2:0] STATE_NEXT;
    wire [2:0] BIT_IDX_NEXT;
    wire [3:0] BAUD_CNT_NEXT;
    wire [7:0] SHIFT_NEXT;
    assign STATE_NEXT = (STATE == IDLE && ENABLE && !RX) ? START_BIT : (STATE == START_BIT && BAUD_CNT == 4'd3) ? DATA_BITS : (STATE == DATA_BITS && BAUD_CNT == 4'd3 && BIT_IDX == 3'd7) ? STOP_BIT : (STATE == DATA_BITS && BAUD_CNT == 4'd3) ? DATA_BITS : (STATE == STOP_BIT && BAUD_CNT == 4'd3) ? IDLE : STATE;
    assign BIT_IDX_NEXT = (STATE == DATA_BITS && BAUD_CNT == 4'd3 && BIT_IDX != 3'd7) ? (BIT_IDX + 3'd1) : BIT_IDX;
    assign BAUD_CNT_NEXT = (STATE == IDLE) ? 4'd0 : (BAUD_CNT == 4'd3 ? 4'd0 : BAUD_CNT + 4'd1);
    assign SHIFT_NEXT = (STATE == DATA_BITS && BAUD_CNT == 4'd3) ? {RX, SHIFT[7:1]} : SHIFT;
    always @(posedge CLK) begin
        if (RST) begin
            STATE <= IDLE; BIT_IDX <= 3'd0; BAUD_CNT <= 4'd0; SHIFT <= 8'd0;
            DATA_OUT <= 8'd0; DATA_READY <= 1'b0; BUSY <= 1'b0; FRAME_ERR <= 1'b0;
        end else begin
            STATE <= STATE_NEXT; BIT_IDX <= BIT_IDX_NEXT; BAUD_CNT <= BAUD_CNT_NEXT; SHIFT <= SHIFT_NEXT;
            DATA_OUT <= (STATE == STOP_BIT && BAUD_CNT == 4'd3) ? SHIFT_NEXT : DATA_OUT;
            DATA_READY <= (STATE == STOP_BIT && BAUD_CNT == 4'd3);
            BUSY <= (STATE != IDLE) || ENABLE;
            FRAME_ERR <= (STATE == STOP_BIT && BAUD_CNT == 4'd3) ? ~RX : 1'b0;
        end
    end
endmodule
"""
    if design_name == "spi_slave_8bit":
        if style == "behavioral":
            return """module spi_slave_8bit(
    input wire CLK,
    input wire RST,
    input wire SS_N,
    input wire SCLK,
    input wire MOSI,
    input wire MISO_IN,
    output reg MISO,
    output reg [7:0] DATA_OUT,
    output reg DATA_READY,
    output reg BUSY
);
    reg [7:0] SHIFT;
    reg [2:0] BIT_IDX;
    reg SCLK_D;
    always @(posedge CLK) begin
        if (RST) begin SHIFT <= 8'd0; BIT_IDX <= 3'd0; SCLK_D <= 1'b0; MISO <= 1'b0; DATA_OUT <= 8'd0; DATA_READY <= 1'b0; BUSY <= 1'b0; end
        else begin DATA_READY <= 1'b0; BUSY <= ~SS_N; if (SS_N) begin BIT_IDX <= 3'd0; SCLK_D <= SCLK; end else begin if (!SCLK_D && SCLK) begin SHIFT <= {SHIFT[6:0], MOSI}; MISO <= SHIFT[7]; if (BIT_IDX == 3'd7) begin DATA_OUT <= {SHIFT[6:0], MOSI}; DATA_READY <= 1'b1; end else BIT_IDX <= BIT_IDX + 3'd1; end SCLK_D <= SCLK; end end
    end
endmodule
"""
        return """module spi_slave_8bit(
    input wire CLK,
    input wire RST,
    input wire SS_N,
    input wire SCLK,
    input wire MOSI,
    input wire MISO_IN,
    output reg MISO,
    output reg [7:0] DATA_OUT,
    output reg DATA_READY,
    output reg BUSY
);
    reg [7:0] SHIFT;
    reg [2:0] BIT_IDX;
    reg SCLK_D;
    wire [7:0] SHIFT_NEXT = (!SS_N && !SCLK_D && SCLK) ? {SHIFT[6:0], MOSI} : SHIFT;
    always @(posedge CLK) begin
        if (RST) begin SHIFT <= 8'd0; BIT_IDX <= 3'd0; SCLK_D <= 1'b0; MISO <= 1'b0; DATA_OUT <= 8'd0; DATA_READY <= 1'b0; BUSY <= 1'b0; end
        else begin DATA_READY <= 1'b0; BUSY <= ~SS_N; if (SS_N) begin BIT_IDX <= 3'd0; end else if (!SCLK_D && SCLK) begin SHIFT <= SHIFT_NEXT; MISO <= SHIFT[7]; if (BIT_IDX == 3'd7) begin DATA_OUT <= SHIFT_NEXT; DATA_READY <= 1'b1; end else BIT_IDX <= BIT_IDX + 3'd1; end SCLK_D <= SCLK; end
    end
endmodule
"""
    if design_name == "i2c_slave_simple":
        if style == "behavioral":
            return """module i2c_slave_simple(
    input wire CLK,
    input wire RST,
    input wire SCL,
    input wire SDA_IN,
    input wire [6:0] ADDR,
    input wire [7:0] DATA_IN,
    output reg SDA_OUT,
    output reg SDA_OE,
    output reg BUSY,
    output reg DONE,
    output reg ACK,
    output reg DATA_READY
);
    reg [1:0] STATE;
    reg [3:0] BIT_IDX;
    reg [7:0] SHIFT;
    reg SCL_D;
    always @(posedge CLK) begin
        if (RST) begin STATE <= 2'd0; BIT_IDX <= 4'd0; SHIFT <= 8'd0; SCL_D <= 1'b1; SDA_OUT <= 1'b1; SDA_OE <= 1'b0; BUSY <= 1'b0; DONE <= 1'b0; ACK <= 1'b0; DATA_READY <= 1'b0; end
        else begin DATA_READY <= 1'b0; DONE <= 1'b0; if (STATE == 2'd0 && SCL && SCL_D && !SDA_IN) begin STATE <= 2'd1; BUSY <= 1'b1; end else if (STATE == 2'd1) begin STATE <= 2'd2; BIT_IDX <= 4'd0; end else if (STATE == 2'd2 && !SCL_D && SCL) begin SHIFT <= {SHIFT[6:0], SDA_IN}; if (BIT_IDX == 4'd7) begin ACK <= 1'b1; STATE <= 2'd3; end else BIT_IDX <= BIT_IDX + 4'd1; end else if (STATE == 2'd3) begin SDA_OE <= 1'b1; SDA_OUT <= 1'b0; DATA_READY <= 1'b1; DONE <= 1'b1; BUSY <= 1'b0; STATE <= 2'd0; end SCL_D <= SCL; end
    end
endmodule
"""
        return """module i2c_slave_simple(
    input wire CLK,
    input wire RST,
    input wire SCL,
    input wire SDA_IN,
    input wire [6:0] ADDR,
    input wire [7:0] DATA_IN,
    output reg SDA_OUT,
    output reg SDA_OE,
    output reg BUSY,
    output reg DONE,
    output reg ACK,
    output reg DATA_READY
);
    reg [1:0] STATE;
    reg [3:0] BIT_IDX;
    reg [7:0] SHIFT;
    reg SCL_D;
    always @(posedge CLK) begin
        if (RST) begin STATE <= 2'd0; BIT_IDX <= 4'd0; SHIFT <= 8'd0; SCL_D <= 1'b1; SDA_OUT <= 1'b1; SDA_OE <= 1'b0; BUSY <= 1'b0; DONE <= 1'b0; ACK <= 1'b0; DATA_READY <= 1'b0; end
        else begin DATA_READY <= 1'b0; DONE <= 1'b0; if (STATE == 2'd0 && SCL && SCL_D && !SDA_IN) begin STATE <= 2'd1; BUSY <= 1'b1; end else if (STATE == 2'd1) begin STATE <= 2'd2; BIT_IDX <= 4'd0; end else if (STATE == 2'd2 && !SCL_D && SCL) begin SHIFT <= {SHIFT[6:0], SDA_IN}; if (BIT_IDX == 4'd7) begin ACK <= 1'b1; STATE <= 2'd3; end else BIT_IDX <= BIT_IDX + 4'd1; end else if (STATE == 2'd3) begin SDA_OE <= 1'b1; SDA_OUT <= 1'b0; DATA_READY <= 1'b1; DONE <= 1'b1; BUSY <= 1'b0; STATE <= 2'd0; end SCL_D <= SCL; end
    end
endmodule
"""
    if design_name == "axi_lite_slave_simple":
        if style == "behavioral":
            return """module axi_lite_slave_simple(
    input wire ACLK,
    input wire ARESETN,
    input wire [31:0] AWADDR,
    input wire AWVALID,
    input wire [31:0] WDATA,
    input wire WVALID,
    input wire [31:0] ARADDR,
    input wire ARVALID,
    input wire RREADY,
    input wire [3:0] WSTRB,
    output reg AWREADY,
    output reg WREADY,
    output reg BVALID,
    output reg [1:0] BRESP,
    output reg ARREADY,
    output reg [31:0] RDATA,
    output reg RVALID,
    output reg [1:0] RRESP
);
    reg [31:0] regs[0:3];
    always @(posedge ACLK) begin
        if (!ARESETN) begin AWREADY <= 1'b0; WREADY <= 1'b0; BVALID <= 1'b0; BRESP <= 2'b00; ARREADY <= 1'b0; RDATA <= 32'd0; RVALID <= 1'b0; RRESP <= 2'b00; regs[0] <= 32'd0; regs[1] <= 32'd0; regs[2] <= 32'd0; regs[3] <= 32'd0; end
        else begin AWREADY <= AWVALID & WVALID; WREADY <= AWVALID & WVALID; if (AWVALID && WVALID) begin regs[AWADDR[3:2]] <= WDATA; BVALID <= 1'b1; end else if (BVALID) BVALID <= ~RREADY; if (ARVALID) begin ARREADY <= 1'b1; RDATA <= regs[ARADDR[3:2]]; RVALID <= 1'b1; end else if (RVALID && RREADY) RVALID <= 1'b0; end
    end
endmodule
"""
        return """module axi_lite_slave_simple(
    input wire ACLK,
    input wire ARESETN,
    input wire [31:0] AWADDR,
    input wire AWVALID,
    input wire [31:0] WDATA,
    input wire WVALID,
    input wire [31:0] ARADDR,
    input wire ARVALID,
    input wire RREADY,
    input wire [3:0] WSTRB,
    output reg AWREADY,
    output reg WREADY,
    output reg BVALID,
    output reg [1:0] BRESP,
    output reg ARREADY,
    output reg [31:0] RDATA,
    output reg RVALID,
    output reg [1:0] RRESP
);
    reg [31:0] regs[0:3];
    always @(posedge ACLK) begin
        if (!ARESETN) begin AWREADY <= 1'b0; WREADY <= 1'b0; BVALID <= 1'b0; BRESP <= 2'b00; ARREADY <= 1'b0; RDATA <= 32'd0; RVALID <= 1'b0; RRESP <= 2'b00; regs[0] <= 32'd0; regs[1] <= 32'd0; regs[2] <= 32'd0; regs[3] <= 32'd0; end
        else begin AWREADY <= AWVALID & WVALID; WREADY <= AWVALID & WVALID; if (AWVALID && WVALID) begin regs[AWADDR[3:2]] <= WDATA; BVALID <= 1'b1; end else if (BVALID) BVALID <= ~RREADY; if (ARVALID) begin ARREADY <= 1'b1; RDATA <= regs[ARADDR[3:2]]; RVALID <= 1'b1; end else if (RVALID && RREADY) RVALID <= 1'b0; end
    end
endmodule
"""
    if design_name == "uart_rx_8n1":
        if style == "behavioral":
            return """module uart_rx_8n1(
    input wire CLK, input wire RST, input wire RX, input wire ENABLE,
    output reg [7:0] DATA_OUT, output reg DATA_READY, output reg BUSY, output reg FRAME_ERR
);
    localparam IDLE = 3'd0, START_BIT = 3'd1, DATA_BITS = 3'd2, STOP_BIT = 3'd3;
    reg [2:0] STATE; reg [2:0] BIT_IDX; reg [3:0] BAUD_CNT; reg [7:0] SHIFT;
    always @(posedge CLK) begin
        if (RST) begin STATE <= IDLE; BIT_IDX <= 0; BAUD_CNT <= 0; SHIFT <= 0; DATA_OUT <= 0; DATA_READY <= 0; BUSY <= 0; FRAME_ERR <= 0; end
        else begin DATA_READY <= 0; FRAME_ERR <= 0;
            case (STATE)
                IDLE: if (ENABLE && !RX) begin STATE <= START_BIT; BUSY <= 1; BAUD_CNT <= 0; end else BUSY <= 0;
                START_BIT: if (BAUD_CNT == 4'd3) begin STATE <= DATA_BITS; BAUD_CNT <= 0; BIT_IDX <= 0; end else BAUD_CNT <= BAUD_CNT + 1;
                DATA_BITS: if (BAUD_CNT == 4'd3) begin SHIFT <= {RX, SHIFT[7:1]}; BAUD_CNT <= 0; if (BIT_IDX == 3'd7) STATE <= STOP_BIT; else BIT_IDX <= BIT_IDX + 1; end else BAUD_CNT <= BAUD_CNT + 1;
                STOP_BIT: if (BAUD_CNT == 4'd3) begin STATE <= IDLE; DATA_OUT <= SHIFT; DATA_READY <= 1; BUSY <= 0; FRAME_ERR <= ~RX; end else BAUD_CNT <= BAUD_CNT + 1;
            endcase
        end
    end
endmodule
"""
        return """module uart_rx_8n1(
    input wire CLK, input wire RST, input wire RX, input wire ENABLE,
    output reg [7:0] DATA_OUT, output reg DATA_READY, output reg BUSY, output reg FRAME_ERR
);
    localparam IDLE = 3'd0, START_BIT = 3'd1, DATA_BITS = 3'd2, STOP_BIT = 3'd3;
    reg [2:0] STATE; reg [2:0] BIT_IDX; reg [3:0] BAUD_CNT; reg [7:0] SHIFT;
    wire [2:0] STATE_NEXT = (STATE == IDLE && ENABLE && !RX) ? START_BIT : (STATE == START_BIT && BAUD_CNT == 4'd3) ? DATA_BITS : (STATE == DATA_BITS && BAUD_CNT == 4'd3 && BIT_IDX == 3'd7) ? STOP_BIT : (STATE == DATA_BITS && BAUD_CNT == 4'd3) ? DATA_BITS : (STATE == STOP_BIT && BAUD_CNT == 4'd3) ? IDLE : STATE;
    wire [2:0] BIT_IDX_NEXT = (STATE == DATA_BITS && BAUD_CNT == 4'd3 && BIT_IDX != 3'd7) ? (BIT_IDX + 1) : BIT_IDX;
    wire [3:0] BAUD_CNT_NEXT = (STATE == IDLE) ? 4'd0 : (BAUD_CNT == 4'd3 ? 4'd0 : BAUD_CNT + 1);
    wire [7:0] SHIFT_NEXT = (STATE == DATA_BITS && BAUD_CNT == 4'd3) ? {RX, SHIFT[7:1]} : SHIFT;
    always @(posedge CLK) begin
        if (RST) begin STATE <= IDLE; BIT_IDX <= 0; BAUD_CNT <= 0; SHIFT <= 0; DATA_OUT <= 0; DATA_READY <= 0; BUSY <= 0; FRAME_ERR <= 0; end
        else begin STATE <= STATE_NEXT; BIT_IDX <= BIT_IDX_NEXT; BAUD_CNT <= BAUD_CNT_NEXT; SHIFT <= SHIFT_NEXT; DATA_OUT <= (STATE == STOP_BIT && BAUD_CNT == 4'd3) ? SHIFT_NEXT : DATA_OUT; DATA_READY <= (STATE == STOP_BIT && BAUD_CNT == 4'd3); BUSY <= (STATE != IDLE) || ENABLE; FRAME_ERR <= (STATE == STOP_BIT && BAUD_CNT == 4'd3) ? ~RX : 0; end
    end
endmodule
"""
    if design_name == "spi_slave_8bit":
        if style == "behavioral":
            return """module spi_slave_8bit(
    input wire CLK, input wire RST, input wire SS_N, input wire SCLK, input wire MOSI, input wire MISO_IN,
    output reg MISO, output reg [7:0] DATA_OUT, output reg DATA_READY, output reg BUSY
);
    reg [7:0] SHIFT; reg [2:0] BIT_IDX; reg SCLK_D;
    always @(posedge CLK) begin
        if (RST) begin SHIFT <= 0; BIT_IDX <= 0; SCLK_D <= 0; MISO <= 0; DATA_OUT <= 0; DATA_READY <= 0; BUSY <= 0; end
        else begin DATA_READY <= 0; BUSY <= ~SS_N; if (SS_N) BIT_IDX <= 0; else if (!SCLK_D && SCLK) begin SHIFT <= {SHIFT[6:0], MOSI}; MISO <= SHIFT[7]; if (BIT_IDX == 3'd7) begin DATA_OUT <= {SHIFT[6:0], MOSI}; DATA_READY <= 1; end else BIT_IDX <= BIT_IDX + 1; end SCLK_D <= SCLK; end
    end
endmodule
"""
        return """module spi_slave_8bit(
    input wire CLK, input wire RST, input wire SS_N, input wire SCLK, input wire MOSI, input wire MISO_IN,
    output reg MISO, output reg [7:0] DATA_OUT, output reg DATA_READY, output reg BUSY
);
    reg [7:0] SHIFT; reg [2:0] BIT_IDX; reg SCLK_D;
    always @(posedge CLK) begin
        if (RST) begin SHIFT <= 0; BIT_IDX <= 0; SCLK_D <= 0; MISO <= 0; DATA_OUT <= 0; DATA_READY <= 0; BUSY <= 0; end
        else begin DATA_READY <= 0; BUSY <= ~SS_N; if (SS_N) BIT_IDX <= 0; else if (!SCLK_D && SCLK) begin SHIFT <= {SHIFT[6:0], MOSI}; MISO <= SHIFT[7]; if (BIT_IDX == 3'd7) begin DATA_OUT <= {SHIFT[6:0], MOSI}; DATA_READY <= 1; end else BIT_IDX <= BIT_IDX + 1; end SCLK_D <= SCLK; end
    end
endmodule
"""
    if design_name == "i2c_slave_simple":
        if style == "behavioral":
            return """module i2c_slave_simple(
    input wire CLK, input wire RST, input wire SCL, input wire SDA_IN, input wire [6:0] ADDR, input wire [7:0] DATA_IN,
    output reg SDA_OUT, output reg SDA_OE, output reg BUSY, output reg DONE, output reg ACK, output reg DATA_READY
);
    reg [1:0] STATE; reg [3:0] BIT_IDX; reg [7:0] SHIFT; reg SCL_D;
    always @(posedge CLK) begin
        if (RST) begin STATE <= 0; BIT_IDX <= 0; SHIFT <= 0; SCL_D <= 1; SDA_OUT <= 1; SDA_OE <= 0; BUSY <= 0; DONE <= 0; ACK <= 0; DATA_READY <= 0; end
        else begin DATA_READY <= 0; DONE <= 0;
            if (STATE == 2'd0 && SCL && SCL_D && !SDA_IN) begin STATE <= 2'd1; BUSY <= 1; end
            else if (STATE == 2'd1) begin STATE <= 2'd2; BIT_IDX <= 0; end
            else if (STATE == 2'd2 && !SCL_D && SCL) begin SHIFT <= {SHIFT[6:0], SDA_IN}; if (BIT_IDX == 4'd7) begin ACK <= 1; STATE <= 2'd3; end else BIT_IDX <= BIT_IDX + 1; end
            else if (STATE == 2'd3) begin SDA_OE <= 1; SDA_OUT <= 0; DATA_READY <= 1; DONE <= 1; BUSY <= 0; STATE <= 0; end
            SCL_D <= SCL;
        end
    end
endmodule
"""
        return """module i2c_slave_simple(
    input wire CLK, input wire RST, input wire SCL, input wire SDA_IN, input wire [6:0] ADDR, input wire [7:0] DATA_IN,
    output reg SDA_OUT, output reg SDA_OE, output reg BUSY, output reg DONE, output reg ACK, output reg DATA_READY
);
    reg [1:0] STATE; reg [3:0] BIT_IDX; reg [7:0] SHIFT; reg SCL_D;
    always @(posedge CLK) begin
        if (RST) begin STATE <= 0; BIT_IDX <= 0; SHIFT <= 0; SCL_D <= 1; SDA_OUT <= 1; SDA_OE <= 0; BUSY <= 0; DONE <= 0; ACK <= 0; DATA_READY <= 0; end
        else begin DATA_READY <= 0; DONE <= 0;
            if (STATE == 2'd0 && SCL && SCL_D && !SDA_IN) begin STATE <= 2'd1; BUSY <= 1; end
            else if (STATE == 2'd1) begin STATE <= 2'd2; BIT_IDX <= 0; end
            else if (STATE == 2'd2 && !SCL_D && SCL) begin SHIFT <= {SHIFT[6:0], SDA_IN}; if (BIT_IDX == 4'd7) begin ACK <= 1; STATE <= 2'd3; end else BIT_IDX <= BIT_IDX + 1; end
            else if (STATE == 2'd3) begin SDA_OE <= 1; SDA_OUT <= 0; DATA_READY <= 1; DONE <= 1; BUSY <= 0; STATE <= 0; end
            SCL_D <= SCL;
        end
    end
endmodule
"""
    if design_name == "axi_lite_slave_simple":
        if style == "behavioral":
            return """module axi_lite_slave_simple(
    input wire ACLK, input wire ARESETN, input wire [31:0] AWADDR, input wire AWVALID, input wire [31:0] WDATA, input wire WVALID,
    input wire [31:0] ARADDR, input wire ARVALID, input wire RREADY, input wire [3:0] WSTRB,
    output reg AWREADY, output reg WREADY, output reg BVALID, output reg [1:0] BRESP, output reg ARREADY, output reg [31:0] RDATA, output reg RVALID, output reg [1:0] RRESP
);
    reg [31:0] regs[0:3];
    always @(posedge ACLK) begin
        if (!ARESETN) begin AWREADY <= 0; WREADY <= 0; BVALID <= 0; BRESP <= 2'b00; ARREADY <= 0; RDATA <= 0; RVALID <= 0; RRESP <= 2'b00; regs[0] <= 0; regs[1] <= 0; regs[2] <= 0; regs[3] <= 0; end
        else begin AWREADY <= AWVALID & WVALID; WREADY <= AWVALID & WVALID; if (AWVALID && WVALID) begin regs[AWADDR[3:2]] <= WDATA; BVALID <= 1; end else if (BVALID && RREADY) BVALID <= 0; if (ARVALID) begin ARREADY <= 1; RDATA <= regs[ARADDR[3:2]]; RVALID <= 1; end else if (RVALID && RREADY) RVALID <= 0; end
    end
endmodule
"""
        return """module axi_lite_slave_simple(
    input wire ACLK, input wire ARESETN, input wire [31:0] AWADDR, input wire AWVALID, input wire [31:0] WDATA, input wire WVALID,
    input wire [31:0] ARADDR, input wire ARVALID, input wire RREADY, input wire [3:0] WSTRB,
    output reg AWREADY, output reg WREADY, output reg BVALID, output reg [1:0] BRESP, output reg ARREADY, output reg [31:0] RDATA, output reg RVALID, output reg [1:0] RRESP
);
    reg [31:0] regs[0:3];
    always @(posedge ACLK) begin
        if (!ARESETN) begin AWREADY <= 0; WREADY <= 0; BVALID <= 0; BRESP <= 2'b00; ARREADY <= 0; RDATA <= 0; RVALID <= 0; RRESP <= 2'b00; regs[0] <= 0; regs[1] <= 0; regs[2] <= 0; regs[3] <= 0; end
        else begin AWREADY <= AWVALID & WVALID; WREADY <= AWVALID & WVALID; if (AWVALID && WVALID) begin regs[AWADDR[3:2]] <= WDATA; BVALID <= 1; end else if (BVALID && RREADY) BVALID <= 0; if (ARVALID) begin ARREADY <= 1; RDATA <= regs[ARADDR[3:2]]; RVALID <= 1; end else if (RVALID && RREADY) RVALID <= 0; end
    end
endmodule
"""
    if design_name == "uart_rx_8n1":
        if style == "behavioral":
            return """module uart_rx_8n1(
    input wire CLK, input wire RST, input wire RX, input wire ENABLE,
    output reg [7:0] DATA_OUT, output reg DATA_READY, output reg BUSY, output reg FRAME_ERR
);
    localparam IDLE = 3'd0, START_BIT = 3'd1, DATA_BITS = 3'd2, STOP_BIT = 3'd3;
    reg [2:0] STATE; reg [2:0] BIT_IDX; reg [3:0] BAUD_CNT; reg [7:0] SHIFT;
    always @(posedge CLK) begin
        if (RST) begin STATE <= IDLE; BIT_IDX <= 0; BAUD_CNT <= 0; SHIFT <= 0; DATA_OUT <= 0; DATA_READY <= 0; BUSY <= 0; FRAME_ERR <= 0; end
        else begin DATA_READY <= 0; FRAME_ERR <= 0;
            case (STATE)
                IDLE: if (ENABLE && !RX) begin STATE <= START_BIT; BUSY <= 1; BAUD_CNT <= 0; end else BUSY <= 0;
                START_BIT: if (BAUD_CNT == 4'd3) begin STATE <= DATA_BITS; BAUD_CNT <= 0; BIT_IDX <= 0; end else BAUD_CNT <= BAUD_CNT + 1;
                DATA_BITS: if (BAUD_CNT == 4'd3) begin SHIFT <= {RX, SHIFT[7:1]}; BAUD_CNT <= 0; if (BIT_IDX == 3'd7) STATE <= STOP_BIT; else BIT_IDX <= BIT_IDX + 1; end else BAUD_CNT <= BAUD_CNT + 1;
                STOP_BIT: if (BAUD_CNT == 4'd3) begin STATE <= IDLE; DATA_OUT <= SHIFT; DATA_READY <= 1; BUSY <= 0; FRAME_ERR <= ~RX; end else BAUD_CNT <= BAUD_CNT + 1;
            endcase
        end
    end
endmodule
"""
        return """module uart_rx_8n1(
    input wire CLK, input wire RST, input wire RX, input wire ENABLE,
    output reg [7:0] DATA_OUT, output reg DATA_READY, output reg BUSY, output reg FRAME_ERR
);
    localparam IDLE = 3'd0, START_BIT = 3'd1, DATA_BITS = 3'd2, STOP_BIT = 3'd3;
    reg [2:0] STATE; reg [2:0] BIT_IDX; reg [3:0] BAUD_CNT; reg [7:0] SHIFT;
    wire [2:0] STATE_NEXT = (STATE == IDLE && ENABLE && !RX) ? START_BIT : (STATE == START_BIT && BAUD_CNT == 4'd3) ? DATA_BITS : (STATE == DATA_BITS && BAUD_CNT == 4'd3 && BIT_IDX == 3'd7) ? STOP_BIT : (STATE == DATA_BITS && BAUD_CNT == 4'd3) ? DATA_BITS : (STATE == STOP_BIT && BAUD_CNT == 4'd3) ? IDLE : STATE;
    wire [2:0] BIT_IDX_NEXT = (STATE == DATA_BITS && BAUD_CNT == 4'd3 && BIT_IDX != 3'd7) ? (BIT_IDX + 1) : BIT_IDX;
    wire [3:0] BAUD_CNT_NEXT = (STATE == IDLE) ? 4'd0 : (BAUD_CNT == 4'd3 ? 4'd0 : BAUD_CNT + 1);
    wire [7:0] SHIFT_NEXT = (STATE == DATA_BITS && BAUD_CNT == 4'd3) ? {RX, SHIFT[7:1]} : SHIFT;
    always @(posedge CLK) begin
        if (RST) begin STATE <= IDLE; BIT_IDX <= 0; BAUD_CNT <= 0; SHIFT <= 0; DATA_OUT <= 0; DATA_READY <= 0; BUSY <= 0; FRAME_ERR <= 0; end
        else begin STATE <= STATE_NEXT; BIT_IDX <= BIT_IDX_NEXT; BAUD_CNT <= BAUD_CNT_NEXT; SHIFT <= SHIFT_NEXT; DATA_OUT <= (STATE == STOP_BIT && BAUD_CNT == 4'd3) ? SHIFT_NEXT : DATA_OUT; DATA_READY <= (STATE == STOP_BIT && BAUD_CNT == 4'd3); BUSY <= (STATE != IDLE) || ENABLE; FRAME_ERR <= (STATE == STOP_BIT && BAUD_CNT == 4'd3) ? ~RX : 1'b0; end
    end
endmodule
"""
    if design_name == "spi_slave_8bit":
        if style == "behavioral":
            return """module spi_slave_8bit(
    input wire CLK, input wire RST, input wire SS_N, input wire SCLK, input wire MOSI, input wire MISO_IN,
    output reg MISO, output reg [7:0] DATA_OUT, output reg DATA_READY, output reg BUSY
);
    reg [7:0] SHIFT; reg [2:0] BIT_IDX; reg SCLK_D;
    always @(posedge CLK) begin
        if (RST) begin SHIFT <= 0; BIT_IDX <= 0; SCLK_D <= 0; MISO <= 0; DATA_OUT <= 0; DATA_READY <= 0; BUSY <= 0; end
        else begin DATA_READY <= 0; BUSY <= ~SS_N; if (SS_N) BIT_IDX <= 0; else if (!SCLK_D && SCLK) begin SHIFT <= {SHIFT[6:0], MOSI}; MISO <= SHIFT[7]; if (BIT_IDX == 3'd7) begin DATA_OUT <= {SHIFT[6:0], MOSI}; DATA_READY <= 1; end else BIT_IDX <= BIT_IDX + 1; end SCLK_D <= SCLK; end
    end
endmodule
"""
        return """module spi_slave_8bit(
    input wire CLK, input wire RST, input wire SS_N, input wire SCLK, input wire MOSI, input wire MISO_IN,
    output reg MISO, output reg [7:0] DATA_OUT, output reg DATA_READY, output reg BUSY
);
    reg [7:0] SHIFT; reg [2:0] BIT_IDX; reg SCLK_D;
    always @(posedge CLK) begin
        if (RST) begin SHIFT <= 0; BIT_IDX <= 0; SCLK_D <= 0; MISO <= 0; DATA_OUT <= 0; DATA_READY <= 0; BUSY <= 0; end
        else begin DATA_READY <= 0; BUSY <= ~SS_N; if (SS_N) BIT_IDX <= 0; else if (!SCLK_D && SCLK) begin SHIFT <= {SHIFT[6:0], MOSI}; MISO <= SHIFT[7]; if (BIT_IDX == 3'd7) begin DATA_OUT <= {SHIFT[6:0], MOSI}; DATA_READY <= 1; end else BIT_IDX <= BIT_IDX + 1; end SCLK_D <= SCLK; end
    end
endmodule
"""
    if design_name == "i2c_slave_simple":
        if style == "behavioral":
            return """module i2c_slave_simple(
    input wire CLK, input wire RST, input wire SCL, input wire SDA_IN, input wire [6:0] ADDR, input wire [7:0] DATA_IN,
    output reg SDA_OUT, output reg SDA_OE, output reg BUSY, output reg DONE, output reg ACK, output reg DATA_READY
);
    reg [1:0] STATE; reg [3:0] BIT_IDX; reg [7:0] SHIFT; reg SCL_D;
    always @(posedge CLK) begin
        if (RST) begin STATE <= 0; BIT_IDX <= 0; SHIFT <= 0; SCL_D <= 1; SDA_OUT <= 1; SDA_OE <= 0; BUSY <= 0; DONE <= 0; ACK <= 0; DATA_READY <= 0; end
        else begin DATA_READY <= 0; DONE <= 0;
            if (STATE == 2'd0 && SCL && SCL_D && !SDA_IN) begin STATE <= 2'd1; BUSY <= 1; end
            else if (STATE == 2'd1) begin STATE <= 2'd2; BIT_IDX <= 0; end
            else if (STATE == 2'd2 && !SCL_D && SCL) begin SHIFT <= {SHIFT[6:0], SDA_IN}; if (BIT_IDX == 4'd7) begin ACK <= 1; STATE <= 2'd3; end else BIT_IDX <= BIT_IDX + 1; end
            else if (STATE == 2'd3) begin SDA_OE <= 1; SDA_OUT <= 0; DATA_READY <= 1; DONE <= 1; BUSY <= 0; STATE <= 0; end
            SCL_D <= SCL;
        end
    end
endmodule
"""
        return """module i2c_slave_simple(
    input wire CLK, input wire RST, input wire SCL, input wire SDA_IN, input wire [6:0] ADDR, input wire [7:0] DATA_IN,
    output reg SDA_OUT, output reg SDA_OE, output reg BUSY, output reg DONE, output reg ACK, output reg DATA_READY
);
    reg [1:0] STATE; reg [3:0] BIT_IDX; reg [7:0] SHIFT; reg SCL_D;
    always @(posedge CLK) begin
        if (RST) begin STATE <= 0; BIT_IDX <= 0; SHIFT <= 0; SCL_D <= 1; SDA_OUT <= 1; SDA_OE <= 0; BUSY <= 0; DONE <= 0; ACK <= 0; DATA_READY <= 0; end
        else begin DATA_READY <= 0; DONE <= 0;
            if (STATE == 2'd0 && SCL && SCL_D && !SDA_IN) begin STATE <= 2'd1; BUSY <= 1; end
            else if (STATE == 2'd1) begin STATE <= 2'd2; BIT_IDX <= 0; end
            else if (STATE == 2'd2 && !SCL_D && SCL) begin SHIFT <= {SHIFT[6:0], SDA_IN}; if (BIT_IDX == 4'd7) begin ACK <= 1; STATE <= 2'd3; end else BIT_IDX <= BIT_IDX + 1; end
            else if (STATE == 2'd3) begin SDA_OE <= 1; SDA_OUT <= 0; DATA_READY <= 1; DONE <= 1; BUSY <= 0; STATE <= 0; end
            SCL_D <= SCL;
        end
    end
endmodule
"""
    if design_name == "axi_lite_slave_simple":
        if style == "behavioral":
            return """module axi_lite_slave_simple(
    input wire ACLK, input wire ARESETN, input wire [31:0] AWADDR, input wire AWVALID, input wire [31:0] WDATA, input wire WVALID,
    input wire [31:0] ARADDR, input wire ARVALID, input wire RREADY, input wire [3:0] WSTRB,
    output reg AWREADY, output reg WREADY, output reg BVALID, output reg [1:0] BRESP, output reg ARREADY, output reg [31:0] RDATA, output reg RVALID, output reg [1:0] RRESP
);
    reg [31:0] regs[0:3];
    always @(posedge ACLK) begin
        if (!ARESETN) begin AWREADY <= 0; WREADY <= 0; BVALID <= 0; BRESP <= 2'b00; ARREADY <= 0; RDATA <= 0; RVALID <= 0; RRESP <= 2'b00; regs[0] <= 0; regs[1] <= 0; regs[2] <= 0; regs[3] <= 0; end
        else begin AWREADY <= AWVALID & WVALID; WREADY <= AWVALID & WVALID; if (AWVALID && WVALID) begin regs[AWADDR[3:2]] <= WDATA; BVALID <= 1; end else if (BVALID && RREADY) BVALID <= 0; if (ARVALID) begin ARREADY <= 1; RDATA <= regs[ARADDR[3:2]]; RVALID <= 1; end else if (RVALID && RREADY) RVALID <= 0; end
    end
endmodule
"""
        return """module axi_lite_slave_simple(
    input wire ACLK, input wire ARESETN, input wire [31:0] AWADDR, input wire AWVALID, input wire [31:0] WDATA, input wire WVALID,
    input wire [31:0] ARADDR, input wire ARVALID, input wire RREADY, input wire [3:0] WSTRB,
    output reg AWREADY, output reg WREADY, output reg BVALID, output reg [1:0] BRESP, output reg ARREADY, output reg [31:0] RDATA, output reg RVALID, output reg [1:0] RRESP
);
    reg [31:0] regs[0:3];
    always @(posedge ACLK) begin
        if (!ARESETN) begin AWREADY <= 0; WREADY <= 0; BVALID <= 0; BRESP <= 2'b00; ARREADY <= 0; RDATA <= 0; RVALID <= 0; RRESP <= 2'b00; regs[0] <= 0; regs[1] <= 0; regs[2] <= 0; regs[3] <= 0; end
        else begin AWREADY <= AWVALID & WVALID; WREADY <= AWVALID & WVALID; if (AWVALID && WVALID) begin regs[AWADDR[3:2]] <= WDATA; BVALID <= 1; end else if (BVALID && RREADY) BVALID <= 0; if (ARVALID) begin ARREADY <= 1; RDATA <= regs[ARADDR[3:2]]; RVALID <= 1; end else if (RVALID && RREADY) RVALID <= 0; end
    end
endmodule
"""
    if design_name == "uart_rx_8n1":
        if style == "behavioral":
            return """module uart_rx_8n1(
    input wire CLK, input wire RST, input wire RX, input wire ENABLE,
    output reg [7:0] DATA_OUT, output reg DATA_READY, output reg BUSY, output reg FRAME_ERR
);
    localparam IDLE = 3'd0, START_BIT = 3'd1, DATA_BITS = 3'd2, STOP_BIT = 3'd3;
    reg [2:0] STATE; reg [2:0] BIT_IDX; reg [3:0] BAUD_CNT; reg [7:0] SHIFT;
    always @(posedge CLK) begin
        if (RST) begin STATE <= IDLE; BIT_IDX <= 0; BAUD_CNT <= 0; SHIFT <= 0; DATA_OUT <= 0; DATA_READY <= 0; BUSY <= 0; FRAME_ERR <= 0; end
        else begin DATA_READY <= 0; FRAME_ERR <= 0;
            case (STATE)
                IDLE: if (ENABLE && !RX) begin STATE <= START_BIT; BUSY <= 1; BAUD_CNT <= 0; end else BUSY <= 0;
                START_BIT: if (BAUD_CNT == 4'd3) begin STATE <= DATA_BITS; BAUD_CNT <= 0; BIT_IDX <= 0; end else BAUD_CNT <= BAUD_CNT + 1;
                DATA_BITS: if (BAUD_CNT == 4'd3) begin SHIFT <= {RX, SHIFT[7:1]}; BAUD_CNT <= 0; if (BIT_IDX == 3'd7) STATE <= STOP_BIT; else BIT_IDX <= BIT_IDX + 1; end else BAUD_CNT <= BAUD_CNT + 1;
                STOP_BIT: if (BAUD_CNT == 4'd3) begin STATE <= IDLE; DATA_OUT <= SHIFT; DATA_READY <= 1; BUSY <= 0; FRAME_ERR <= ~RX; end else BAUD_CNT <= BAUD_CNT + 1;
            endcase
        end
    end
endmodule
"""
        return """module uart_rx_8n1(
    input wire CLK, input wire RST, input wire RX, input wire ENABLE,
    output reg [7:0] DATA_OUT, output reg DATA_READY, output reg BUSY, output reg FRAME_ERR
);
    localparam IDLE = 3'd0, START_BIT = 3'd1, DATA_BITS = 3'd2, STOP_BIT = 3'd3;
    reg [2:0] STATE; reg [2:0] BIT_IDX; reg [3:0] BAUD_CNT; reg [7:0] SHIFT;
    wire [2:0] STATE_NEXT = (STATE == IDLE && ENABLE && !RX) ? START_BIT : (STATE == START_BIT && BAUD_CNT == 4'd3) ? DATA_BITS : (STATE == DATA_BITS && BAUD_CNT == 4'd3 && BIT_IDX == 3'd7) ? STOP_BIT : (STATE == DATA_BITS && BAUD_CNT == 4'd3) ? DATA_BITS : (STATE == STOP_BIT && BAUD_CNT == 4'd3) ? IDLE : STATE;
    wire [2:0] BIT_IDX_NEXT = (STATE == DATA_BITS && BAUD_CNT == 4'd3 && BIT_IDX != 3'd7) ? (BIT_IDX + 1) : BIT_IDX;
    wire [3:0] BAUD_CNT_NEXT = (STATE == IDLE) ? 4'd0 : (BAUD_CNT == 4'd3 ? 4'd0 : BAUD_CNT + 1);
    wire [7:0] SHIFT_NEXT = (STATE == DATA_BITS && BAUD_CNT == 4'd3) ? {RX, SHIFT[7:1]} : SHIFT;
    always @(posedge CLK) begin
        if (RST) begin STATE <= IDLE; BIT_IDX <= 0; BAUD_CNT <= 0; SHIFT <= 0; DATA_OUT <= 0; DATA_READY <= 0; BUSY <= 0; FRAME_ERR <= 0; end
        else begin STATE <= STATE_NEXT; BIT_IDX <= BIT_IDX_NEXT; BAUD_CNT <= BAUD_CNT_NEXT; SHIFT <= SHIFT_NEXT; DATA_OUT <= (STATE == STOP_BIT && BAUD_CNT == 4'd3) ? SHIFT_NEXT : DATA_OUT; DATA_READY <= (STATE == STOP_BIT && BAUD_CNT == 4'd3); BUSY <= (STATE != IDLE) || ENABLE; FRAME_ERR <= (STATE == STOP_BIT && BAUD_CNT == 4'd3) ? ~RX : 1'b0; end
    end
endmodule
"""
    if design_name == "spi_slave_8bit":
        if style == "behavioral":
            return """module spi_slave_8bit(
    input wire CLK, input wire RST, input wire SS_N, input wire SCLK, input wire MOSI, input wire MISO_IN,
    output reg MISO, output reg [7:0] DATA_OUT, output reg DATA_READY, output reg BUSY
);
    reg [7:0] SHIFT; reg [2:0] BIT_IDX; reg SCLK_D;
    always @(posedge CLK) begin
        if (RST) begin SHIFT <= 0; BIT_IDX <= 0; SCLK_D <= 0; MISO <= 0; DATA_OUT <= 0; DATA_READY <= 0; BUSY <= 0; end
        else begin DATA_READY <= 0; BUSY <= ~SS_N; if (SS_N) BIT_IDX <= 0; else if (!SCLK_D && SCLK) begin SHIFT <= {SHIFT[6:0], MOSI}; MISO <= SHIFT[7]; if (BIT_IDX == 3'd7) begin DATA_OUT <= {SHIFT[6:0], MOSI}; DATA_READY <= 1; end else BIT_IDX <= BIT_IDX + 1; end SCLK_D <= SCLK; end
    end
endmodule
"""
        return """module spi_slave_8bit(
    input wire CLK, input wire RST, input wire SS_N, input wire SCLK, input wire MOSI, input wire MISO_IN,
    output reg MISO, output reg [7:0] DATA_OUT, output reg DATA_READY, output reg BUSY
);
    reg [7:0] SHIFT; reg [2:0] BIT_IDX; reg SCLK_D;
    always @(posedge CLK) begin
        if (RST) begin SHIFT <= 0; BIT_IDX <= 0; SCLK_D <= 0; MISO <= 0; DATA_OUT <= 0; DATA_READY <= 0; BUSY <= 0; end
        else begin DATA_READY <= 0; BUSY <= ~SS_N; if (SS_N) BIT_IDX <= 0; else if (!SCLK_D && SCLK) begin SHIFT <= {SHIFT[6:0], MOSI}; MISO <= SHIFT[7]; if (BIT_IDX == 3'd7) begin DATA_OUT <= {SHIFT[6:0], MOSI}; DATA_READY <= 1; end else BIT_IDX <= BIT_IDX + 1; end SCLK_D <= SCLK; end
    end
endmodule
"""
    if design_name == "i2c_slave_simple":
        if style == "behavioral":
            return """module i2c_slave_simple(
    input wire CLK, input wire RST, input wire SCL, input wire SDA_IN, input wire [6:0] ADDR, input wire [7:0] DATA_IN,
    output reg SDA_OUT, output reg SDA_OE, output reg BUSY, output reg DONE, output reg ACK, output reg DATA_READY
);
    reg [1:0] STATE; reg [3:0] BIT_IDX; reg [7:0] SHIFT; reg SCL_D;
    always @(posedge CLK) begin
        if (RST) begin STATE <= 0; BIT_IDX <= 0; SHIFT <= 0; SCL_D <= 1; SDA_OUT <= 1; SDA_OE <= 0; BUSY <= 0; DONE <= 0; ACK <= 0; DATA_READY <= 0; end
        else begin DATA_READY <= 0; DONE <= 0;
            if (STATE == 2'd0 && SCL && SCL_D && !SDA_IN) begin STATE <= 2'd1; BUSY <= 1; end
            else if (STATE == 2'd1) begin STATE <= 2'd2; BIT_IDX <= 0; end
            else if (STATE == 2'd2 && !SCL_D && SCL) begin SHIFT <= {SHIFT[6:0], SDA_IN}; if (BIT_IDX == 4'd7) begin ACK <= 1; STATE <= 2'd3; end else BIT_IDX <= BIT_IDX + 1; end
            else if (STATE == 2'd3) begin SDA_OE <= 1; SDA_OUT <= 0; DATA_READY <= 1; DONE <= 1; BUSY <= 0; STATE <= 0; end
            SCL_D <= SCL;
        end
    end
endmodule
"""
        return """module i2c_slave_simple(
    input wire CLK, input wire RST, input wire SCL, input wire SDA_IN, input wire [6:0] ADDR, input wire [7:0] DATA_IN,
    output reg SDA_OUT, output reg SDA_OE, output reg BUSY, output reg DONE, output reg ACK, output reg DATA_READY
);
    reg [1:0] STATE; reg [3:0] BIT_IDX; reg [7:0] SHIFT; reg SCL_D;
    always @(posedge CLK) begin
        if (RST) begin STATE <= 0; BIT_IDX <= 0; SHIFT <= 0; SCL_D <= 1; SDA_OUT <= 1; SDA_OE <= 0; BUSY <= 0; DONE <= 0; ACK <= 0; DATA_READY <= 0; end
        else begin DATA_READY <= 0; DONE <= 0;
            if (STATE == 2'd0 && SCL && SCL_D && !SDA_IN) begin STATE <= 2'd1; BUSY <= 1; end
            else if (STATE == 2'd1) begin STATE <= 2'd2; BIT_IDX <= 0; end
            else if (STATE == 2'd2 && !SCL_D && SCL) begin SHIFT <= {SHIFT[6:0], SDA_IN}; if (BIT_IDX == 4'd7) begin ACK <= 1; STATE <= 2'd3; end else BIT_IDX <= BIT_IDX + 1; end
            else if (STATE == 2'd3) begin SDA_OE <= 1; SDA_OUT <= 0; DATA_READY <= 1; DONE <= 1; BUSY <= 0; STATE <= 0; end
            SCL_D <= SCL;
        end
    end
endmodule
"""
    if design_name == "axi_lite_slave_simple":
        if style == "behavioral":
            return """module axi_lite_slave_simple(
    input wire ACLK, input wire ARESETN, input wire [31:0] AWADDR, input wire AWVALID, input wire [31:0] WDATA, input wire WVALID,
    input wire [31:0] ARADDR, input wire ARVALID, input wire RREADY, input wire [3:0] WSTRB,
    output reg AWREADY, output reg WREADY, output reg BVALID, output reg [1:0] BRESP, output reg ARREADY, output reg [31:0] RDATA, output reg RVALID, output reg [1:0] RRESP
);
    reg [31:0] regs[0:3];
    always @(posedge ACLK) begin
        if (!ARESETN) begin AWREADY <= 0; WREADY <= 0; BVALID <= 0; BRESP <= 2'b00; ARREADY <= 0; RDATA <= 0; RVALID <= 0; RRESP <= 2'b00; regs[0] <= 0; regs[1] <= 0; regs[2] <= 0; regs[3] <= 0; end
        else begin AWREADY <= AWVALID & WVALID; WREADY <= AWVALID & WVALID; if (AWVALID && WVALID) begin regs[AWADDR[3:2]] <= WDATA; BVALID <= 1; end else if (BVALID && RREADY) BVALID <= 0; if (ARVALID) begin ARREADY <= 1; RDATA <= regs[ARADDR[3:2]]; RVALID <= 1; end else if (RVALID && RREADY) RVALID <= 0; end
    end
endmodule
"""
        return """module axi_lite_slave_simple(
    input wire ACLK, input wire ARESETN, input wire [31:0] AWADDR, input wire AWVALID, input wire [31:0] WDATA, input wire WVALID,
    input wire [31:0] ARADDR, input wire ARVALID, input wire RREADY, input wire [3:0] WSTRB,
    output reg AWREADY, output reg WREADY, output reg BVALID, output reg [1:0] BRESP, output reg ARREADY, output reg [31:0] RDATA, output reg RVALID, output reg [1:0] RRESP
);
    reg [31:0] regs[0:3];
    always @(posedge ACLK) begin
        if (!ARESETN) begin AWREADY <= 0; WREADY <= 0; BVALID <= 0; BRESP <= 2'b00; ARREADY <= 0; RDATA <= 0; RVALID <= 0; RRESP <= 2'b00; regs[0] <= 0; regs[1] <= 0; regs[2] <= 0; regs[3] <= 0; end
        else begin AWREADY <= AWVALID & WVALID; WREADY <= AWVALID & WVALID; if (AWVALID && WVALID) begin regs[AWADDR[3:2]] <= WDATA; BVALID <= 1; end else if (BVALID && RREADY) BVALID <= 0; if (ARVALID) begin ARREADY <= 1; RDATA <= regs[ARADDR[3:2]]; RVALID <= 1; end else if (RVALID && RREADY) RVALID <= 0; end
    end
endmodule
"""
    if design_name == "uart_rx_8n1":
        if style == "behavioral":
            return """module uart_rx_8n1(
    input wire CLK, input wire RST, input wire RX, input wire ENABLE,
    output reg [7:0] DATA_OUT, output reg DATA_READY, output reg BUSY, output reg FRAME_ERR
);
    localparam IDLE = 3'd0, START_BIT = 3'd1, DATA_BITS = 3'd2, STOP_BIT = 3'd3;
    reg [2:0] STATE; reg [2:0] BIT_IDX; reg [3:0] BAUD_CNT; reg [7:0] SHIFT;
    always @(posedge CLK) begin
        if (RST) begin STATE <= IDLE; BIT_IDX <= 0; BAUD_CNT <= 0; SHIFT <= 0; DATA_OUT <= 0; DATA_READY <= 0; BUSY <= 0; FRAME_ERR <= 0; end
        else begin DATA_READY <= 0; FRAME_ERR <= 0;
            case (STATE)
                IDLE: if (ENABLE && !RX) begin STATE <= START_BIT; BUSY <= 1; BAUD_CNT <= 0; end else BUSY <= 0;
                START_BIT: if (BAUD_CNT == 4'd3) begin STATE <= DATA_BITS; BAUD_CNT <= 0; BIT_IDX <= 0; end else BAUD_CNT <= BAUD_CNT + 1;
                DATA_BITS: if (BAUD_CNT == 4'd3) begin SHIFT <= {RX, SHIFT[7:1]}; BAUD_CNT <= 0; if (BIT_IDX == 3'd7) STATE <= STOP_BIT; else BIT_IDX <= BIT_IDX + 1; end else BAUD_CNT <= BAUD_CNT + 1;
                STOP_BIT: if (BAUD_CNT == 4'd3) begin STATE <= IDLE; DATA_OUT <= SHIFT; DATA_READY <= 1; BUSY <= 0; FRAME_ERR <= ~RX; end else BAUD_CNT <= BAUD_CNT + 1;
            endcase
        end
    end
endmodule
"""
        return """module uart_rx_8n1(
    input wire CLK, input wire RST, input wire RX, input wire ENABLE,
    output reg [7:0] DATA_OUT, output reg DATA_READY, output reg BUSY, output reg FRAME_ERR
);
    localparam IDLE = 3'd0, START_BIT = 3'd1, DATA_BITS = 3'd2, STOP_BIT = 3'd3;
    reg [2:0] STATE; reg [2:0] BIT_IDX; reg [3:0] BAUD_CNT; reg [7:0] SHIFT;
    wire [2:0] STATE_NEXT = (STATE == IDLE && ENABLE && !RX) ? START_BIT : (STATE == START_BIT && BAUD_CNT == 4'd3) ? DATA_BITS : (STATE == DATA_BITS && BAUD_CNT == 4'd3 && BIT_IDX == 3'd7) ? STOP_BIT : (STATE == DATA_BITS && BAUD_CNT == 4'd3) ? DATA_BITS : (STATE == STOP_BIT && BAUD_CNT == 4'd3) ? IDLE : STATE;
    wire [2:0] BIT_IDX_NEXT = (STATE == DATA_BITS && BAUD_CNT == 4'd3 && BIT_IDX != 3'd7) ? (BIT_IDX + 1) : BIT_IDX;
    wire [3:0] BAUD_CNT_NEXT = (STATE == IDLE) ? 4'd0 : (BAUD_CNT == 4'd3 ? 4'd0 : BAUD_CNT + 1);
    wire [7:0] SHIFT_NEXT = (STATE == DATA_BITS && BAUD_CNT == 4'd3) ? {RX, SHIFT[7:1]} : SHIFT;
    always @(posedge CLK) begin
        if (RST) begin STATE <= IDLE; BIT_IDX <= 0; BAUD_CNT <= 0; SHIFT <= 0; DATA_OUT <= 0; DATA_READY <= 0; BUSY <= 0; FRAME_ERR <= 0; end
        else begin STATE <= STATE_NEXT; BIT_IDX <= BIT_IDX_NEXT; BAUD_CNT <= BAUD_CNT_NEXT; SHIFT <= SHIFT_NEXT; DATA_OUT <= (STATE == STOP_BIT && BAUD_CNT == 4'd3) ? SHIFT_NEXT : DATA_OUT; DATA_READY <= (STATE == STOP_BIT && BAUD_CNT == 4'd3); BUSY <= (STATE != IDLE) || ENABLE; FRAME_ERR <= (STATE == STOP_BIT && BAUD_CNT == 4'd3) ? ~RX : 1'b0; end
    end
endmodule
"""
    if design_name == "spi_slave_8bit":
        if style == "behavioral":
            return """module spi_slave_8bit(
    input wire CLK, input wire RST, input wire SS_N, input wire SCLK, input wire MOSI, input wire MISO_IN,
    output reg MISO, output reg [7:0] DATA_OUT, output reg DATA_READY, output reg BUSY
);
    reg [7:0] SHIFT; reg [2:0] BIT_IDX; reg SCLK_D;
    always @(posedge CLK) begin
        if (RST) begin SHIFT <= 0; BIT_IDX <= 0; SCLK_D <= 0; MISO <= 0; DATA_OUT <= 0; DATA_READY <= 0; BUSY <= 0; end
        else begin DATA_READY <= 0; BUSY <= ~SS_N; if (SS_N) BIT_IDX <= 0; else if (!SCLK_D && SCLK) begin SHIFT <= {SHIFT[6:0], MOSI}; MISO <= SHIFT[7]; if (BIT_IDX == 3'd7) begin DATA_OUT <= {SHIFT[6:0], MOSI}; DATA_READY <= 1; end else BIT_IDX <= BIT_IDX + 1; end SCLK_D <= SCLK; end
    end
endmodule
"""
        return """module spi_slave_8bit(
    input wire CLK, input wire RST, input wire SS_N, input wire SCLK, input wire MOSI, input wire MISO_IN,
    output reg MISO, output reg [7:0] DATA_OUT, output reg DATA_READY, output reg BUSY
);
    reg [7:0] SHIFT; reg [2:0] BIT_IDX; reg SCLK_D;
    always @(posedge CLK) begin
        if (RST) begin SHIFT <= 0; BIT_IDX <= 0; SCLK_D <= 0; MISO <= 0; DATA_OUT <= 0; DATA_READY <= 0; BUSY <= 0; end
        else begin DATA_READY <= 0; BUSY <= ~SS_N; if (SS_N) BIT_IDX <= 0; else if (!SCLK_D && SCLK) begin SHIFT <= {SHIFT[6:0], MOSI}; MISO <= SHIFT[7]; if (BIT_IDX == 3'd7) begin DATA_OUT <= {SHIFT[6:0], MOSI}; DATA_READY <= 1; end else BIT_IDX <= BIT_IDX + 1; end SCLK_D <= SCLK; end
    end
endmodule
"""
    if design_name == "i2c_slave_simple":
        if style == "behavioral":
            return """module i2c_slave_simple(
    input wire CLK, input wire RST, input wire SCL, input wire SDA_IN, input wire [6:0] ADDR, input wire [7:0] DATA_IN,
    output reg SDA_OUT, output reg SDA_OE, output reg BUSY, output reg DONE, output reg ACK, output reg DATA_READY
);
    reg [1:0] STATE; reg [3:0] BIT_IDX; reg [7:0] SHIFT; reg SCL_D;
    always @(posedge CLK) begin
        if (RST) begin STATE <= 0; BIT_IDX <= 0; SHIFT <= 0; SCL_D <= 1; SDA_OUT <= 1; SDA_OE <= 0; BUSY <= 0; DONE <= 0; ACK <= 0; DATA_READY <= 0; end
        else begin DATA_READY <= 0; DONE <= 0;
            if (STATE == 2'd0 && SCL && SCL_D && !SDA_IN) begin STATE <= 2'd1; BUSY <= 1; end
            else if (STATE == 2'd1) begin STATE <= 2'd2; BIT_IDX <= 0; end
            else if (STATE == 2'd2 && !SCL_D && SCL) begin SHIFT <= {SHIFT[6:0], SDA_IN}; if (BIT_IDX == 4'd7) begin ACK <= 1; STATE <= 2'd3; end else BIT_IDX <= BIT_IDX + 1; end
            else if (STATE == 2'd3) begin SDA_OE <= 1; SDA_OUT <= 0; DATA_READY <= 1; DONE <= 1; BUSY <= 0; STATE <= 0; end
            SCL_D <= SCL;
        end
    end
endmodule
"""
        return """module i2c_slave_simple(
    input wire CLK, input wire RST, input wire SCL, input wire SDA_IN, input wire [6:0] ADDR, input wire [7:0] DATA_IN,
    output reg SDA_OUT, output reg SDA_OE, output reg BUSY, output reg DONE, output reg ACK, output reg DATA_READY
);
    reg [1:0] STATE; reg [3:0] BIT_IDX; reg [7:0] SHIFT; reg SCL_D;
    always @(posedge CLK) begin
        if (RST) begin STATE <= 0; BIT_IDX <= 0; SHIFT <= 0; SCL_D <= 1; SDA_OUT <= 1; SDA_OE <= 0; BUSY <= 0; DONE <= 0; ACK <= 0; DATA_READY <= 0; end
        else begin DATA_READY <= 0; DONE <= 0;
            if (STATE == 2'd0 && SCL && SCL_D && !SDA_IN) begin STATE <= 2'd1; BUSY <= 1; end
            else if (STATE == 2'd1) begin STATE <= 2'd2; BIT_IDX <= 0; end
            else if (STATE == 2'd2 && !SCL_D && SCL) begin SHIFT <= {SHIFT[6:0], SDA_IN}; if (BIT_IDX == 4'd7) begin ACK <= 1; STATE <= 2'd3; end else BIT_IDX <= BIT_IDX + 1; end
            else if (STATE == 2'd3) begin SDA_OE <= 1; SDA_OUT <= 0; DATA_READY <= 1; DONE <= 1; BUSY <= 0; STATE <= 0; end
            SCL_D <= SCL;
        end
    end
endmodule
"""
    if design_name == "axi_lite_slave_simple":
        if style == "behavioral":
            return """module axi_lite_slave_simple(
    input wire ACLK, input wire ARESETN, input wire [31:0] AWADDR, input wire AWVALID, input wire [31:0] WDATA, input wire WVALID,
    input wire [31:0] ARADDR, input wire ARVALID, input wire RREADY, input wire [3:0] WSTRB,
    output reg AWREADY, output reg WREADY, output reg BVALID, output reg [1:0] BRESP, output reg ARREADY, output reg [31:0] RDATA, output reg RVALID, output reg [1:0] RRESP
);
    reg [31:0] regs[0:3];
    always @(posedge ACLK) begin
        if (!ARESETN) begin AWREADY <= 0; WREADY <= 0; BVALID <= 0; BRESP <= 2'b00; ARREADY <= 0; RDATA <= 0; RVALID <= 0; RRESP <= 2'b00; regs[0] <= 0; regs[1] <= 0; regs[2] <= 0; regs[3] <= 0; end
        else begin AWREADY <= AWVALID & WVALID; WREADY <= AWVALID & WVALID; if (AWVALID && WVALID) begin regs[AWADDR[3:2]] <= WDATA; BVALID <= 1; end else if (BVALID && RREADY) BVALID <= 0; if (ARVALID) begin ARREADY <= 1; RDATA <= regs[ARADDR[3:2]]; RVALID <= 1; end else if (RVALID && RREADY) RVALID <= 0; end
    end
endmodule
"""
        return """module axi_lite_slave_simple(
    input wire ACLK, input wire ARESETN, input wire [31:0] AWADDR, input wire AWVALID, input wire [31:0] WDATA, input wire WVALID,
    input wire [31:0] ARADDR, input wire ARVALID, input wire RREADY, input wire [3:0] WSTRB,
    output reg AWREADY, output reg WREADY, output reg BVALID, output reg [1:0] BRESP, output reg ARREADY, output reg [31:0] RDATA, output reg RVALID, output reg [1:0] RRESP
);
    reg [31:0] regs[0:3];
    always @(posedge ACLK) begin
        if (!ARESETN) begin AWREADY <= 0; WREADY <= 0; BVALID <= 0; BRESP <= 2'b00; ARREADY <= 0; RDATA <= 0; RVALID <= 0; RRESP <= 2'b00; regs[0] <= 0; regs[1] <= 0; regs[2] <= 0; regs[3] <= 0; end
        else begin AWREADY <= AWVALID & WVALID; WREADY <= AWVALID & WVALID; if (AWVALID && WVALID) begin regs[AWADDR[3:2]] <= WDATA; BVALID <= 1; end else if (BVALID && RREADY) BVALID <= 0; if (ARVALID) begin ARREADY <= 1; RDATA <= regs[ARADDR[3:2]]; RVALID <= 1; end else if (RVALID && RREADY) RVALID <= 0; end
    end
endmodule
"""
    return ""


def build_testbench(contract: Any) -> str:
    design_name = getattr(contract, "design_name", "")
    top = design_name if design_name else "design"

    if design_name == "not":
        return """`timescale 1ns/1ps
module not_tb;
    reg A;
    wire Y;

    not_gate dut(.A(A), .Y(Y));

    initial begin
        $display("not_tb");
        A = 1'b0; #10;
        A = 1'b1; #10;
        $finish;
    end
endmodule
"""
    if design_name == "buffer":
        return """`timescale 1ns/1ps
module buffer_tb;
    reg A;
    wire Y;

    buffer_gate dut(.A(A), .Y(Y));

    initial begin
        $display("buffer_tb");
        A = 1'b0; #10;
        A = 1'b1; #10;
        $finish;
    end
endmodule
"""
    if design_name in {"nand", "nor", "and", "or", "xor", "xnor", "half_adder", "full_adder", "mux_2to1", "mux_4to1", "mux_8to1", "mux_4to1_tree", "mux_8to1_tree", "demux_1to2", "comparator", "decoder_2to4", "encoder_4to2", "priority_encoder_4to2"}:
        return _combinational_testbench(contract)
    if design_name in {"uart_tx_8n1", "spi_master_8bit", "i2c_master_simple"}:
        return _protocol_testbench(contract)
    if design_name in {"uart_rx_8n1", "spi_slave_8bit", "i2c_slave_simple", "axi_lite_slave_simple"}:
        return _protocol_testbench(contract)
    if design_name.startswith("counter_"):
        return _counter_testbench(contract)
    if design_name.startswith("shift_register_") and "bit" in design_name:
        width = _shift_register_spec(design_name)
        tb_module = f"{design_name}_tb"
        q_decl = f"[{width - 1}:0] " if width > 1 else ""
        dut_decl = f"    wire {q_decl}Q;\n"
        cycles = max(width, 4)
        sample_value = "1'b1"
        return f"""`timescale 1ns/1ps
module {tb_module};
    reg CLK;
    reg RST;
    reg EN;
    reg D;
{dut_decl}
    {design_name} dut(.CLK(CLK), .RST(RST), .EN(EN), .D(D), .Q(Q));

    always #5 CLK = ~CLK;

    initial begin
        $display("{tb_module}");
        CLK = 1'b0;
        RST = 1'b1;
        EN = 1'b0;
        D = 1'b0;
        #12 RST = 1'b0;
        EN = 1'b1;
        D = {sample_value};
        repeat ({cycles}) @(posedge CLK);
        D = 1'b0;
        repeat ({max(1, cycles // 2)}) @(posedge CLK);
        EN = 1'b0;
        repeat (2) @(posedge CLK);
        $finish;
    end
endmodule
"""
    if design_name in {"dff", "tff", "jkff", "srff"}:
        return _sequential_ff_testbench(contract)
    if design_name == "fsm_traffic_light":
        return """`timescale 1ns/1ps
module fsm_traffic_light_tb;
    reg CLK;
    reg RESET;
    reg TIMER_DONE;
    wire [1:0] STATE;
    wire NS_GREEN;
    wire NS_YELLOW;
    wire EW_GREEN;

    fsm_traffic_light dut(
        .CLK(CLK),
        .RESET(RESET),
        .TIMER_DONE(TIMER_DONE),
        .STATE(STATE),
        .NS_GREEN(NS_GREEN),
        .NS_YELLOW(NS_YELLOW),
        .EW_GREEN(EW_GREEN)
    );

    always #5 CLK = ~CLK;

    initial begin
        $display("fsm_traffic_light_tb");
        CLK = 1'b0;
        RESET = 1'b1;
        TIMER_DONE = 1'b0;
        #12 RESET = 1'b0;
        TIMER_DONE = 1'b1;
        repeat (3) @(posedge CLK);
        TIMER_DONE = 1'b0;
        repeat (2) @(posedge CLK);
        $finish;
    end
endmodule
"""
    if design_name.startswith("fifo_"):
        return _fifo_testbench(contract)
    if design_name.startswith("fifo_"):
        return _fifo_testbench(contract)
    if design_name == "fifo_4x8":
        return """`timescale 1ns/1ps
module fifo_4x8_tb;
    reg CLK;
    reg RESET;
    reg WR_EN;
    reg RD_EN;
    reg [7:0] DIN;
    wire [7:0] DOUT;
    wire FULL;
    wire EMPTY;

    fifo_4x8 dut(
        .CLK(CLK),
        .RESET(RESET),
        .WR_EN(WR_EN),
        .RD_EN(RD_EN),
        .DIN(DIN),
        .DOUT(DOUT),
        .FULL(FULL),
        .EMPTY(EMPTY)
    );

    always #5 CLK = ~CLK;

    initial begin
        $display("fifo_4x8_tb");
        CLK = 1'b0;
        RESET = 1'b1;
        WR_EN = 1'b0;
        RD_EN = 1'b0;
        DIN = 8'h00;
        #12 RESET = 1'b0;
        DIN = 8'hA5;
        WR_EN = 1'b1;
        @(posedge CLK);
        DIN = 8'h3C;
        @(posedge CLK);
        WR_EN = 1'b0;
        RD_EN = 1'b1;
        repeat (2) @(posedge CLK);
        $finish;
    end
endmodule
"""

    return _combinational_testbench(contract)


def _counter_testbench(contract: Any) -> str:
    design_name = getattr(contract, "design_name", "")
    width, _ff_kind = _counter_spec(design_name)
    tb_module = f"{design_name}_tb"
    q_decl = f"[{width - 1}:0] " if width > 1 else ""
    dut_decl = f"    wire {q_decl}Q;\n"
    dut_name = design_name
    cycles = max(1 << width, 1)

    return f"""`timescale 1ns/1ps
module {tb_module};
    reg CLK;
    reg RST;
    reg EN;
{dut_decl}
    {dut_name} dut(.CLK(CLK), .RST(RST), .EN(EN), .Q(Q));

    always #5 CLK = ~CLK;

    initial begin
        $display("{tb_module}");
        CLK = 1'b0;
        RST = 1'b1;
        EN = 1'b0;
        #12 RST = 1'b0;
        EN = 1'b1;
        repeat ({cycles}) @(posedge CLK);
        EN = 1'b0;
        repeat (2) @(posedge CLK);
        $finish;
    end
endmodule
"""


def _combinational_testbench(contract: Any) -> str:
    design_name = getattr(contract, "design_name", "")
    _, inputs, outputs = _module_ports(design_name)
    tb_module = f"{design_name}_tb"
    dut_module = _dut_module_name(design_name)

    reg_lines = [f"    reg {item};" for item in inputs]
    wire_lines = [f"    wire {item};" for item in outputs]
    port_lines = [f"        .{item}({item})" for item in inputs + outputs]
    declarations = "\n".join(reg_lines + wire_lines)
    ports = ",\n".join(port_lines)

    stimulus_lines = [
        f"        $display(\"{tb_module}\");",
        "        $monitor(\"time=%0t inputs=%b outputs=%b\", $time, {" + ", ".join(inputs) + "}, {" + ", ".join(outputs) + "});",
    ]
    stimulus_lines.extend([f"        {item} = 1'b0;" for item in inputs])

    mux_spec = _mux_spec(design_name)
    if mux_spec:
        size, _is_tree = mux_spec
        select_count = _mux_select_bits(size)
        select_names = [f"S{i}" for i in range(select_count)]
        data_names = [f"D{i}" for i in range(size)]
        stimulus_lines += [
            "        " + "; ".join(f"{name} = 1'b{index % 2}" for index, name in enumerate(data_names)) + ";",
        ]
        for selection in range(1 << select_count):
            bits = format(selection, f"0{select_count}b")
            assigns = []
            for bit_index, bit in enumerate(bits):
                assigns.append(f"{select_names[bit_index]} = 1'b{bit}")
            stimulus_lines.append("        " + "; ".join(assigns) + "; #10;")
        return f"""`timescale 1ns/1ps
module {tb_module};
{declarations}

    {dut_module} dut(
{ports}
    );

    initial begin
{chr(10).join(stimulus_lines)}
        $finish;
    end
endmodule
"""

    if design_name in {"mux_4to1", "mux_4to1_tree"}:
        stimulus_lines += [
            "        S1 = 1'b0; S0 = 1'b0; D0 = 1'b0; D1 = 1'b1; D2 = 1'b0; D3 = 1'b0; #10;",
            "        S1 = 1'b0; S0 = 1'b1; D0 = 1'b0; D1 = 1'b1; D2 = 1'b0; D3 = 1'b0; #10;",
            "        S1 = 1'b1; S0 = 1'b0; D0 = 1'b0; D1 = 1'b1; D2 = 1'b0; D3 = 1'b0; #10;",
            "        S1 = 1'b1; S0 = 1'b1; D0 = 1'b0; D1 = 1'b1; D2 = 1'b0; D3 = 1'b0; #10;",
        ]
    elif design_name == "mux_2to1":
        stimulus_lines += [
            "        S0 = 1'b0; D0 = 1'b0; D1 = 1'b1; #10;",
            "        S0 = 1'b1; D0 = 1'b0; D1 = 1'b1; #10;",
        ]
    elif design_name in {"mux_8to1", "mux_8to1_tree"}:
        stimulus_lines += [
            "        S2 = 1'b0; S1 = 1'b0; S0 = 1'b0; D0 = 1'b0; D1 = 1'b1; D2 = 1'b0; D3 = 1'b0; D4 = 1'b0; D5 = 1'b0; D6 = 1'b0; D7 = 1'b0; #10;",
            "        S2 = 1'b0; S1 = 1'b0; S0 = 1'b1; D0 = 1'b0; D1 = 1'b1; D2 = 1'b0; D3 = 1'b0; D4 = 1'b0; D5 = 1'b0; D6 = 1'b0; D7 = 1'b0; #10;",
            "        S2 = 1'b0; S1 = 1'b1; S0 = 1'b0; D0 = 1'b0; D1 = 1'b1; D2 = 1'b0; D3 = 1'b0; D4 = 1'b0; D5 = 1'b0; D6 = 1'b0; D7 = 1'b0; #10;",
            "        S2 = 1'b0; S1 = 1'b1; S0 = 1'b1; D0 = 1'b0; D1 = 1'b1; D2 = 1'b0; D3 = 1'b0; D4 = 1'b0; D5 = 1'b0; D6 = 1'b0; D7 = 1'b0; #10;",
        ]
    elif design_name in {"half_adder", "full_adder"}:
        stimulus_lines += [
            "        A = 1'b0; B = 1'b0; #10;",
            "        A = 1'b0; B = 1'b1; #10;",
            "        A = 1'b1; B = 1'b0; #10;",
            "        A = 1'b1; B = 1'b1; #10;",
        ]
    elif design_name == "encoder_4to2":
        stimulus_lines += [
            "        D0 = 1'b1; D1 = 1'b0; D2 = 1'b0; D3 = 1'b0; #10;",
            "        D0 = 1'b0; D1 = 1'b1; D2 = 1'b0; D3 = 1'b0; #10;",
            "        D0 = 1'b0; D1 = 1'b0; D2 = 1'b1; D3 = 1'b0; #10;",
            "        D0 = 1'b0; D1 = 1'b0; D2 = 1'b0; D3 = 1'b1; #10;",
        ]
    elif design_name == "priority_encoder_4to2":
        stimulus_lines += [
            "        D0 = 1'b1; D1 = 1'b0; D2 = 1'b0; D3 = 1'b0; #10;",
            "        D0 = 1'b0; D1 = 1'b1; D2 = 1'b0; D3 = 1'b0; #10;",
            "        D0 = 1'b0; D1 = 1'b0; D2 = 1'b1; D3 = 1'b0; #10;",
            "        D0 = 1'b0; D1 = 1'b0; D2 = 1'b0; D3 = 1'b1; #10;",
        ]
    elif design_name == "decoder_2to4":
        stimulus_lines += [
            "        A = 1'b0; B = 1'b0; #10;",
            "        A = 1'b0; B = 1'b1; #10;",
            "        A = 1'b1; B = 1'b0; #10;",
            "        A = 1'b1; B = 1'b1; #10;",
        ]
    elif design_name == "comparator":
        stimulus_lines += [
            "        A = 1'b0; B = 1'b0; #10;",
            "        A = 1'b0; B = 1'b1; #10;",
            "        A = 1'b1; B = 1'b0; #10;",
            "        A = 1'b1; B = 1'b1; #10;",
        ]
    else:
        stimulus_lines += [
            "        A = 1'b0; B = 1'b0; #10;",
            "        A = 1'b0; B = 1'b1; #10;",
            "        A = 1'b1; B = 1'b0; #10;",
            "        A = 1'b1; B = 1'b1; #10;",
        ]

    return f"""`timescale 1ns/1ps
module {tb_module};
{declarations}

    {dut_module} dut(
{ports}
    );

    initial begin
{chr(10).join(stimulus_lines)}
        $finish;
    end
endmodule
"""


def _sequential_ff_testbench(contract: Any) -> str:
    design_name = getattr(contract, "design_name", "")
    if design_name == "dff":
        return """`timescale 1ns/1ps
module dff_tb;
    reg CLK;
    reg D;
    wire Q;

    dff dut(.CLK(CLK), .D(D), .Q(Q));

    always #5 CLK = ~CLK;

    initial begin
        $display("dff_tb");
        CLK = 1'b0;
        D = 1'b0;
        #12 D = 1'b1;
        repeat (3) @(posedge CLK);
        D = 1'b0;
        repeat (2) @(posedge CLK);
        $finish;
    end
endmodule
"""
    if design_name == "tff":
        return """`timescale 1ns/1ps
module tff_tb;
    reg CLK;
    reg T;
    wire Q;

    tff dut(.CLK(CLK), .T(T), .Q(Q));

    always #5 CLK = ~CLK;

    initial begin
        $display("tff_tb");
        CLK = 1'b0;
        T = 1'b0;
        #12 T = 1'b1;
        repeat (4) @(posedge CLK);
        T = 1'b0;
        repeat (2) @(posedge CLK);
        $finish;
    end
endmodule
"""
    if design_name == "jkff":
        return """`timescale 1ns/1ps
module jkff_tb;
    reg CLK;
    reg J;
    reg K;
    wire Q;

    jkff dut(.CLK(CLK), .J(J), .K(K), .Q(Q));

    always #5 CLK = ~CLK;

    initial begin
        $display("jkff_tb");
        CLK = 1'b0;
        J = 1'b0;
        K = 1'b0;
        #12 J = 1'b1; K = 1'b0;
        repeat (2) @(posedge CLK);
        J = 1'b0; K = 1'b1;
        repeat (2) @(posedge CLK);
        J = 1'b1; K = 1'b1;
        repeat (2) @(posedge CLK);
        $finish;
    end
endmodule
"""
    return """`timescale 1ns/1ps
module srff_tb;
    reg CLK;
    reg S;
    reg R;
    wire Q;

    srff dut(.CLK(CLK), .S(S), .R(R), .Q(Q));

    always #5 CLK = ~CLK;

    initial begin
        $display("srff_tb");
        CLK = 1'b0;
        S = 1'b0;
        R = 1'b0;
        #12 S = 1'b1; R = 1'b0;
        repeat (2) @(posedge CLK);
        S = 1'b0; R = 1'b1;
        repeat (2) @(posedge CLK);
        S = 1'b0; R = 1'b0;
        repeat (2) @(posedge CLK);
        $finish;
    end
endmodule
"""

def fpga_requirements_for(contract: Any) -> str:
    profile = str(getattr(contract, "implementation_profile", "combinational") or "combinational").lower()
    shared_rules = [
        "- Generate only synthesizable Verilog.",
        "- Avoid simulation-only constructs unless explicitly requested.",
        "- Avoid delays (#), force/release, and initial blocks for hardware logic.",
        "- Keep designs Vivado-compatible and FPGA-ready.",
        "- Prevent unintended combinational loops and multiple drivers.",
    ]
    sequential_rules = [
        "- Use proper clocked logic for sequential circuits.",
        "- Use non-blocking assignments (<=) in sequential always blocks.",
        "- Generate reset logic when required.",
        "- Separate state register, next-state, and output logic for FSMs.",
        "- Use parameter or localparam state encoding where appropriate.",
        "- Infer registers, memories, or DSP resources when the design requires them.",
    ]
    combinational_rules = [
        "- Use blocking assignments (=) in combinational always blocks.",
        "- Ensure all combinational outputs are assigned.",
        "- Avoid latch inference unless explicitly requested.",
        "- Prefer direct Boolean equations, gate instances, and mux trees.",
    ]
    if profile == "sequential":
        rules = shared_rules + sequential_rules
    else:
        rules = shared_rules + combinational_rules
    return "\n".join(rules)


def fpga_implementation_plan(contract: Any) -> dict[str, Any]:
    design_name = getattr(contract, "design_name", "")
    profile = str(getattr(contract, "implementation_profile", "combinational") or "combinational").lower()
    abstraction = str(getattr(contract, "abstraction", "gate_level") or "gate_level").lower()
    modeling_style = str(getattr(contract, "modeling_style", "dataflow") or "dataflow").lower()
    technology_node = str(getattr(contract, "technology_node", "") or "")

    if profile == "sequential":
        resource_mapping = [
            "Registers map to flip-flops in the FPGA fabric.",
            "State and counters map to synchronous registers and LUT-based next-state logic.",
            "FIFO/shift-register style designs can infer memory or SRL resources when appropriate.",
            "Arithmetic and compare logic remain synthesizable and Vivado-compatible.",
        ]
    else:
        resource_mapping = [
            "Combinational logic maps to LUTs and carry chains.",
            "Mux trees infer clean LUT-based selection networks.",
            "Encoders, decoders, and adders are synthesized into FPGA-friendly primitives.",
        ]

    return {
        "design_name": design_name,
        "modeling_style": modeling_style,
        "implementation_profile": profile,
        "abstraction": abstraction,
        "technology_node": technology_node,
        "synthesizable": True,
        "vivado_compatible": True,
        "board_ready": True,
        "resource_mapping": resource_mapping,
        "constraints_needed": [
            "Add .xdc pin constraints for the target board.",
            "Assign the top-level ports to board switches, buttons, LEDs, or clocks.",
            "Use the provided Vivado testbench for simulation before bitstream generation.",
        ],
        "verification_steps": [
            "Run Vivado elaboration.",
            "Run synthesis and check for warnings or latches.",
            "Inspect timing/utilization reports.",
            "Generate a netlist and confirm top-level port mapping.",
        ],
        "notes": (
            "This design is emitted as FPGA-ready synthesizable Verilog with a matching testbench "
            "and Vivado verification path."
        ),
    }


verilog_for_dataflow_legacy = verilog_for


def _module_ports(design_name: str) -> tuple[str, list[str], list[str]]:
    if mux_spec := _mux_spec(design_name):
        size, _is_tree = mux_spec
        select_names, data_names = _mux_input_names(size)
        return _verilog_module_name(design_name), select_names + data_names, ["Y"]
    if design_name.startswith("shift_register_") and "bit" in design_name:
        return _verilog_module_name(design_name), ["CLK", "RST", "EN", "D"], ["Q"]
    ports = {
        "not": (["A"], ["Y"]),
        "buffer": (["A"], ["Y"]),
        "nand": (["A", "B"], ["Y"]),
        "nor": (["A", "B"], ["Y"]),
        "and": (["A", "B"], ["Y"]),
        "or": (["A", "B"], ["Y"]),
        "xor": (["A", "B"], ["Y"]),
        "xnor": (["A", "B"], ["Y"]),
        "half_adder": (["A", "B"], ["SUM", "COUT"]),
        "full_adder": (["A", "B", "CIN"], ["SUM", "COUT"]),
        "demux_1to2": (["SEL", "D"], ["Y0", "Y1"]),
        "comparator": (["A", "B"], ["EQ", "GT", "LT"]),
        "decoder_2to4": (["A", "B"], ["Y0", "Y1", "Y2", "Y3"]),
        "encoder_4to2": (["D0", "D1", "D2", "D3"], ["Y1", "Y0"]),
        "priority_encoder_4to2": (["D0", "D1", "D2", "D3"], ["Y1", "Y0", "VALID"]),
        "uart_tx_8n1": (["CLK", "RST", "START", "DATA_IN"], ["TX", "BUSY", "DONE"]),
        "uart_rx_8n1": (["CLK", "RST", "RX", "ENABLE"], ["DATA_OUT", "DATA_READY", "BUSY", "FRAME_ERR"]),
        "spi_master_8bit": (["CLK", "RST", "START", "MISO", "DATA_IN"], ["SCLK", "MOSI", "CS", "BUSY", "DONE", "DATA_OUT"]),
        "spi_slave_8bit": (["CLK", "RST", "SS_N", "SCLK", "MOSI", "MISO_IN"], ["MISO", "DATA_OUT", "DATA_READY", "BUSY"]),
        "i2c_master_simple": (["CLK", "RST", "START", "SDA_IN", "ADDR", "DATA_IN"], ["SCL", "SDA_OUT", "SDA_OE", "BUSY", "DONE", "ACK"]),
        "i2c_slave_simple": (["CLK", "RST", "SCL", "SDA_IN", "ADDR", "DATA_IN"], ["SDA_OUT", "SDA_OE", "BUSY", "DONE", "ACK", "DATA_READY"]),
        "axi_lite_slave_simple": (["ACLK", "ARESETN", "AWADDR", "AWVALID", "WDATA", "WVALID", "ARADDR", "ARVALID", "RREADY", "WSTRB"], ["AWREADY", "WREADY", "BVALID", "BRESP", "ARREADY", "RDATA", "RVALID", "RRESP"]),
    }.get(design_name)
    if ports is None:
        return _verilog_module_name(design_name), ["A", "B"], ["Y"]
    return _verilog_module_name(design_name), ports[0], ports[1]


def _port_decl(inputs: list[str], outputs: list[str]) -> str:
    parts = [f"input wire {item}" for item in inputs] + [f"output wire {item}" for item in outputs]
    return ", ".join(parts)


def _dut_module_name(design_name: str) -> str:
    return {
        "not": "not_gate",
        "buffer": "buffer_gate",
        "nand": "nand_gate",
        "nor": "nor_gate",
        "and": "and_gate",
        "or": "or_gate",
        "xor": "xor_gate",
        "xnor": "xnor_gate",
        "comparator": "comparator_1bit",
    }.get(design_name, design_name)


def _sequential_family_verilog(design_name: str, style: str = "dataflow") -> str:
    style = (style or "dataflow").strip().lower()

    if design_name.startswith("shift_register_") and "bit" in design_name:
        return _shift_register_family_verilog(design_name, style)

    if design_name == "counter_4bit":
        if style == "behavioral":
            return """module counter_4bit(input wire CLK, input wire RST, input wire EN, output reg [3:0] Q);
    always @(posedge CLK) begin
        if (RST)
            Q <= 4'b0000;
        else if (EN)
            Q <= Q + 4'd1;
        else
            Q <= Q;
    end
endmodule
"""
        if style == "structural":
            return """module counter_4bit(input wire CLK, input wire RST, input wire EN, output wire [3:0] Q);
    wire [3:0] q_next;

    counter_4bit_next u_next(.Q(Q), .RST(RST), .EN(EN), .Q_NEXT(q_next));
    counter_4bit_reg u_reg(.CLK(CLK), .D(q_next), .Q(Q));
endmodule

module counter_4bit_next(input wire [3:0] Q, input wire RST, input wire EN, output wire [3:0] Q_NEXT);
    assign Q_NEXT = RST ? 4'b0000 : (EN ? (Q + 4'd1) : Q);
endmodule

module counter_4bit_reg(input wire CLK, input wire [3:0] D, output reg [3:0] Q);
    always @(posedge CLK) begin
        Q <= D;
    end
endmodule
"""
        return """module counter_4bit(input wire CLK, input wire RST, input wire EN, output reg [3:0] Q);
    wire [3:0] Q_next;
    assign Q_next = RST ? 4'b0000 : (EN ? (Q + 4'd1) : Q);
    always @(posedge CLK) begin
        Q <= Q_next;
    end
endmodule
"""

    if design_name == "shift_register_4bit":
        if style == "behavioral":
            return """module shift_register_4bit(input wire CLK, input wire RST, input wire EN, input wire D, output reg [3:0] Q);
    always @(posedge CLK) begin
        if (RST)
            Q <= 4'b0000;
        else if (EN)
            Q <= {Q[2:0], D};
        else
            Q <= Q;
    end
endmodule
"""
        if style == "structural":
            return """module shift_register_4bit(input wire CLK, input wire RST, input wire EN, input wire D, output wire [3:0] Q);
    wire [3:0] q_next;

    shift_register_4bit_next u_next(.Q(Q), .RST(RST), .EN(EN), .D(D), .Q_NEXT(q_next));
    shift_register_4bit_reg u_reg(.CLK(CLK), .D(q_next), .Q(Q));
endmodule

module shift_register_4bit_next(input wire [3:0] Q, input wire RST, input wire EN, input wire D, output wire [3:0] Q_NEXT);
    assign Q_NEXT = RST ? 4'b0000 : (EN ? {Q[2:0], D} : Q);
endmodule

module shift_register_4bit_reg(input wire CLK, input wire [3:0] D, output reg [3:0] Q);
    always @(posedge CLK) begin
        Q <= D;
    end
endmodule
"""
        return """module shift_register_4bit(input wire CLK, input wire RST, input wire EN, input wire D, output reg [3:0] Q);
    wire [3:0] Q_next;
    assign Q_next = RST ? 4'b0000 : (EN ? {Q[2:0], D} : Q);
    always @(posedge CLK) begin
        Q <= Q_next;
    end
endmodule
"""

    if design_name == "fsm_traffic_light":
        if style == "behavioral":
            return """module fsm_traffic_light(
    input wire CLK,
    input wire RESET,
    input wire TIMER_DONE,
    output reg [1:0] STATE,
    output reg NS_GREEN,
    output reg NS_YELLOW,
    output reg EW_GREEN
);

localparam S0 = 2'b00;
localparam S1 = 2'b01;
localparam S2 = 2'b10;

always @(posedge CLK) begin
    if (RESET)
        STATE <= S0;
    else if (TIMER_DONE) begin
        case (STATE)
            S0: STATE <= S1;
            S1: STATE <= S2;
            default: STATE <= S0;
        endcase
    end else begin
        STATE <= STATE;
    end
end

always @* begin
    NS_GREEN = 1'b0;
    NS_YELLOW = 1'b0;
    EW_GREEN = 1'b0;
    case (STATE)
        S0: NS_GREEN = 1'b1;
        S1: NS_YELLOW = 1'b1;
        default: EW_GREEN = 1'b1;
    endcase
end

endmodule
"""
        if style == "structural":
            return """module fsm_traffic_light(
    input wire CLK,
    input wire RESET,
    input wire TIMER_DONE,
    output wire [1:0] STATE,
    output wire NS_GREEN,
    output wire NS_YELLOW,
    output wire EW_GREEN
);

wire [1:0] next_state;

fsm_traffic_light_next u_next(.STATE(STATE), .RESET(RESET), .TIMER_DONE(TIMER_DONE), .NEXT_STATE(next_state));
fsm_traffic_light_reg u_reg(.CLK(CLK), .RESET(RESET), .D(next_state), .STATE(STATE));
fsm_traffic_light_decode u_decode(.STATE(STATE), .NS_GREEN(NS_GREEN), .NS_YELLOW(NS_YELLOW), .EW_GREEN(EW_GREEN));
endmodule

module fsm_traffic_light_next(
    input wire [1:0] STATE,
    input wire RESET,
    input wire TIMER_DONE,
    output wire [1:0] NEXT_STATE
);

localparam S0 = 2'b00;
localparam S1 = 2'b01;
localparam S2 = 2'b10;

assign NEXT_STATE = RESET ? S0 :
                    (STATE == S0) ? (TIMER_DONE ? S1 : S0) :
                    (STATE == S1) ? (TIMER_DONE ? S2 : S1) :
                    (TIMER_DONE ? S0 : S2);
endmodule

module fsm_traffic_light_reg(
    input wire CLK,
    input wire RESET,
    input wire [1:0] D,
    output reg [1:0] STATE
);

always @(posedge CLK) begin
    if (RESET)
        STATE <= 2'b00;
    else
        STATE <= D;
end
endmodule

module fsm_traffic_light_decode(
    input wire [1:0] STATE,
    output wire NS_GREEN,
    output wire NS_YELLOW,
    output wire EW_GREEN
);

assign NS_GREEN = (STATE == 2'b00);
assign NS_YELLOW = (STATE == 2'b01);
assign EW_GREEN = (STATE == 2'b10);
endmodule
"""
        return """module fsm_traffic_light(
    input wire CLK,
    input wire RESET,
    input wire TIMER_DONE,
    output reg [1:0] STATE,
    output reg NS_GREEN,
    output reg NS_YELLOW,
    output reg EW_GREEN
);

wire [1:0] next_state;

localparam S0 = 2'b00;
localparam S1 = 2'b01;
localparam S2 = 2'b10;

assign next_state = RESET ? S0 :
                    (STATE == S0) ? (TIMER_DONE ? S1 : S0) :
                    (STATE == S1) ? (TIMER_DONE ? S2 : S1) :
                    (TIMER_DONE ? S0 : S2);

always @(posedge CLK) begin
    STATE <= next_state;
end

always @* begin
    NS_GREEN = 1'b0;
    NS_YELLOW = 1'b0;
    EW_GREEN = 1'b0;
    case (STATE)
        S0: NS_GREEN = 1'b1;
        S1: NS_YELLOW = 1'b1;
        default: EW_GREEN = 1'b1;
    endcase
end

endmodule
"""

    if design_name.startswith("fifo_"):
        return _fifo_family_verilog(design_name, "behavioral")
    if design_name.startswith("fifo_"):
        return _fifo_family_verilog(design_name, "behavioral")
    if design_name == "fifo_4x8":
        if style == "behavioral":
            return """module fifo_4x8(
    input wire CLK,
    input wire RESET,
    input wire WR_EN,
    input wire RD_EN,
    input wire [7:0] DIN,
    output reg [7:0] DOUT,
    output reg FULL,
    output reg EMPTY
);

reg [7:0] mem [0:3];
reg [1:0] wptr;
reg [1:0] rptr;
reg [2:0] count;
wire [2:0] count_next;

wire push = WR_EN & (~FULL | RD_EN);
wire pop = RD_EN & ~EMPTY;
assign count_next = (push && !pop) ? (count + 3'd1) :
                    (pop && !push) ? (count - 3'd1) :
                    count;

always @(posedge CLK) begin
    if (RESET) begin
        wptr <= 2'b00;
        rptr <= 2'b00;
        count <= 3'b000;
        DOUT <= 8'b0000_0000;
        FULL <= 1'b0;
        EMPTY <= 1'b1;
    end else begin
        if (push)
            mem[wptr] <= DIN;
        if (pop)
            DOUT <= mem[rptr];
        if (push)
            wptr <= wptr + 2'd1;
        if (pop)
            rptr <= rptr + 2'd1;
        count <= count_next;
        FULL <= (count_next == 3'd4);
        EMPTY <= (count_next == 3'd0);
    end
end

endmodule
"""
        if style == "structural":
            return """module fifo_4x8(
    input wire CLK,
    input wire RESET,
    input wire WR_EN,
    input wire RD_EN,
    input wire [7:0] DIN,
    output wire [7:0] DOUT,
    output wire FULL,
    output wire EMPTY
);

wire push, pop;
wire [1:0] wptr;
wire [1:0] rptr;
wire [2:0] count;

fifo_4x8_ctrl u_ctrl(.WR_EN(WR_EN), .RD_EN(RD_EN), .FULL(FULL), .EMPTY(EMPTY), .PUSH(push), .POP(pop));
fifo_4x8_ptrs u_ptrs(.CLK(CLK), .RESET(RESET), .PUSH(push), .POP(pop), .WPTR(wptr), .RPTR(rptr), .COUNT(count), .FULL(FULL), .EMPTY(EMPTY));
fifo_4x8_mem u_mem(.CLK(CLK), .PUSH(push), .POP(pop), .WPTR(wptr), .RPTR(rptr), .DIN(DIN), .DOUT(DOUT));
endmodule

module fifo_4x8_ctrl(
    input wire WR_EN,
    input wire RD_EN,
    input wire FULL,
    input wire EMPTY,
    output wire PUSH,
    output wire POP
);

assign PUSH = WR_EN & ~FULL;
assign POP = RD_EN & ~EMPTY;
endmodule

module fifo_4x8_ptrs(
    input wire CLK,
    input wire RESET,
    input wire PUSH,
    input wire POP,
    output reg [1:0] WPTR,
    output reg [1:0] RPTR,
    output reg [2:0] COUNT,
    output reg FULL,
    output reg EMPTY
);

always @(posedge CLK) begin
    if (RESET) begin
        WPTR <= 2'b00;
        RPTR <= 2'b00;
        COUNT <= 3'b000;
        FULL <= 1'b0;
        EMPTY <= 1'b1;
    end else begin
        if (PUSH && !POP)
            COUNT <= COUNT + 3'd1;
        else if (POP && !PUSH)
            COUNT <= COUNT - 3'd1;
        if (PUSH)
            WPTR <= WPTR + 2'd1;
        if (POP)
            RPTR <= RPTR + 2'd1;
        FULL <= (COUNT == 3'd3);
        EMPTY <= (COUNT == 3'd0);
    end
end
endmodule

module fifo_4x8_mem(
    input wire CLK,
    input wire PUSH,
    input wire POP,
    input wire [1:0] WPTR,
    input wire [1:0] RPTR,
    input wire [7:0] DIN,
    output reg [7:0] DOUT
);

reg [7:0] mem [0:3];

always @(posedge CLK) begin
    if (PUSH)
        mem[WPTR] <= DIN;
    if (POP)
        DOUT <= mem[RPTR];
end
endmodule
"""
        return """module fifo_4x8(
    input wire CLK,
    input wire RESET,
    input wire WR_EN,
    input wire RD_EN,
    input wire [7:0] DIN,
    output reg [7:0] DOUT,
    output reg FULL,
    output reg EMPTY
);

reg [7:0] mem [0:3];
reg [1:0] wptr;
reg [1:0] rptr;
reg [2:0] count;
wire push, pop;

assign push = WR_EN & ~FULL;
assign pop = RD_EN & ~EMPTY;

always @(posedge CLK) begin
    if (RESET) begin
        wptr <= 2'b00;
        rptr <= 2'b00;
        count <= 3'b000;
        DOUT <= 8'b0000_0000;
        FULL <= 1'b0;
        EMPTY <= 1'b1;
    end else begin
        if (push)
            mem[wptr] <= DIN;
        if (pop)
            DOUT <= mem[rptr];
        if (push && !pop)
            count <= count + 3'd1;
        else if (pop && !push)
            count <= count - 3'd1;
        if (push)
            wptr <= wptr + 2'd1;
        if (pop)
            rptr <= rptr + 2'd1;
        FULL <= (count == 3'd3);
        EMPTY <= (count == 3'd0);
    end
end

endmodule
"""

    return ""


def _behavioral_verilog(design_name: str) -> str:
    if design_name in {"uart_tx_8n1", "spi_master_8bit", "i2c_master_simple"}:
        return _protocol_family_verilog(design_name, "behavioral")
    if _mux_spec(design_name):
        return _mux_direct_verilog(design_name, "behavioral")
    if design_name.startswith("shift_register_") and "bit" in design_name:
        return _shift_register_family_verilog(design_name, "behavioral")
    if design_name == "not":
        return """module not_gate(input wire A, output reg Y);
    always @* begin
        Y = ~A;
    end
endmodule
"""
    if design_name == "buffer":
        return """module buffer_gate(input wire A, output reg Y);
    always @* begin
        Y = A;
    end
endmodule
"""
    if design_name == "nand":
        return """module nand_gate(input wire A, input wire B, output reg Y);
    always @* begin
        Y = ~(A & B);
    end
endmodule
"""
    if design_name == "nor":
        return """module nor_gate(input wire A, input wire B, output reg Y);
    always @* begin
        Y = ~(A | B);
    end
endmodule
"""
    if design_name == "and":
        return """module and_gate(input wire A, input wire B, output reg Y);
    always @* begin
        Y = A & B;
    end
endmodule
"""
    if design_name == "or":
        return """module or_gate(input wire A, input wire B, output reg Y);
    always @* begin
        Y = A | B;
    end
endmodule
"""
    if design_name == "xor":
        return """module xor_gate(input wire A, input wire B, output reg Y);
    always @* begin
        Y = A ^ B;
    end
endmodule
"""
    if design_name == "xnor":
        return """module xnor_gate(input wire A, input wire B, output reg Y);
    always @* begin
        Y = ~(A ^ B);
    end
endmodule
"""
    if design_name == "half_adder":
        return """module half_adder(input wire A, input wire B, output reg SUM, output reg COUT);
    always @* begin
        SUM = A ^ B;
        COUT = A & B;
    end
endmodule
"""
    if design_name == "full_adder":
        return """module full_adder(input wire A, input wire B, input wire CIN, output reg SUM, output reg COUT);
    always @* begin
        SUM = A ^ B ^ CIN;
        COUT = (A & B) | (CIN & (A ^ B));
    end
endmodule
"""
    if design_name == "mux_2to1":
        return """module mux_2to1(input wire S0, input wire D0, input wire D1, output reg Y);
    always @* begin
        case (S0)
            1'b0: Y = D0;
            default: Y = D1;
        endcase
    end
endmodule
"""
    if design_name == "mux_4to1":
        return """module mux_4to1(input wire S0, input wire S1, input wire D0, input wire D1, input wire D2, input wire D3, output reg Y);
    always @* begin
        case ({S1, S0})
            2'b00: Y = D0;
            2'b01: Y = D1;
            2'b10: Y = D2;
            default: Y = D3;
        endcase
    end
endmodule
"""
    if design_name == "mux_8to1":
        return """module mux_8to1(
    input wire S0,
    input wire S1,
    input wire S2,
    input wire D0,
    input wire D1,
    input wire D2,
    input wire D3,
    input wire D4,
    input wire D5,
    input wire D6,
    input wire D7,
    output reg Y
);
    always @* begin
        case ({S2, S1, S0})
            3'b000: Y = D0;
            3'b001: Y = D1;
            3'b010: Y = D2;
            3'b011: Y = D3;
            3'b100: Y = D4;
            3'b101: Y = D5;
            3'b110: Y = D6;
            default: Y = D7;
        endcase
    end
endmodule
"""
    if design_name == "demux_1to2":
        return """module demux_1to2(input wire SEL, input wire D, output reg Y0, output reg Y1);
    always @* begin
        Y0 = 1'b0;
        Y1 = 1'b0;
        if (SEL == 1'b0) Y0 = D;
        else Y1 = D;
    end
endmodule
"""
    if design_name == "comparator":
        return """module comparator_1bit(input wire A, input wire B, output reg EQ, output reg GT, output reg LT);
    always @* begin
        EQ = (A == B);
        GT = (A == 1'b1) && (B == 1'b0);
        LT = (A == 1'b0) && (B == 1'b1);
    end
endmodule
"""
    if design_name == "decoder_2to4":
        return """module decoder_2to4(input wire A, input wire B, output reg Y0, output reg Y1, output reg Y2, output reg Y3);
    always @* begin
        Y0 = 1'b0; Y1 = 1'b0; Y2 = 1'b0; Y3 = 1'b0;
        case ({A, B})
            2'b00: Y0 = 1'b1;
            2'b01: Y1 = 1'b1;
            2'b10: Y2 = 1'b1;
            default: Y3 = 1'b1;
        endcase
    end
endmodule
"""
    if design_name == "encoder_4to2":
        return """module encoder_4to2(input wire D0, input wire D1, input wire D2, input wire D3, output reg Y1, output reg Y0);
    always @* begin
        Y1 = D2 | D3;
        Y0 = D1 | D3;
    end
endmodule
"""
    if design_name == "priority_encoder_4to2":
        return """module priority_encoder_4to2(input wire D0, input wire D1, input wire D2, input wire D3, output reg Y1, output reg Y0, output reg VALID);
    always @* begin
        VALID = D0 | D1 | D2 | D3;
        Y1 = D2 | D3;
        Y0 = D1 | D3;
    end
endmodule
"""
    if design_name == "dff":
        return """module dff(input wire CLK, input wire D, output reg Q);
    always @(posedge CLK) begin
        Q <= D;
    end
endmodule
"""
    if design_name == "tff":
        return """module tff(input wire CLK, input wire T, output reg Q);
    always @(posedge CLK) begin
        if (T)
            Q <= ~Q;
        else
            Q <= Q;
    end
endmodule
"""
    if design_name == "jkff":
        return """module jkff(input wire CLK, input wire J, input wire K, output reg Q);
    always @(posedge CLK) begin
        case ({J, K})
            2'b00: Q <= Q;
            2'b01: Q <= 1'b0;
            2'b10: Q <= 1'b1;
            default: Q <= ~Q;
        endcase
    end
endmodule
"""
    if design_name == "srff":
        return """module srff(input wire CLK, input wire S, input wire R, output reg Q);
    always @(posedge CLK) begin
        case ({S, R})
            2'b00: Q <= Q;
            2'b01: Q <= 1'b0;
            2'b10: Q <= 1'b1;
            default: Q <= 1'b0;
        endcase
    end
endmodule
"""
    if design_name in {"counter_4bit", "shift_register_4bit", "fsm_traffic_light", "fifo_4x8"}:
        return _sequential_family_verilog(design_name, "behavioral")
    if design_name.startswith("counter_"):
        return _counter_family_verilog(design_name, "behavioral")
    if design_name in {"mux_4to1_tree", "mux_8to1_tree"}:
        return _mux_tree_verilog(design_name, "behavioral")
    return verilog_for_dataflow_legacy(design_name)


def _gate_level_verilog(design_name: str) -> str:
    if design_name in {"uart_tx_8n1", "spi_master_8bit", "i2c_master_simple"}:
        return _protocol_family_verilog(design_name, "gate_level")
    if _mux_spec(design_name):
        return _mux_direct_verilog(design_name, "gate_level")
    if design_name.startswith("shift_register_") and "bit" in design_name:
        return _shift_register_family_verilog(design_name, "gate_level")
    if design_name in {"not", "buffer", "nand", "nor", "and", "or", "xor", "xnor"}:
        if design_name == "not":
            return """module not_gate(input wire A, output wire Y);
    not g1(Y, A);
endmodule
"""
        if design_name == "buffer":
            return """module buffer_gate(input wire A, output wire Y);
    buf g1(Y, A);
endmodule
"""
        if design_name == "nand":
            return """module nand_gate(input wire A, input wire B, output wire Y);
    nand g1(Y, A, B);
endmodule
"""
        if design_name == "nor":
            return """module nor_gate(input wire A, input wire B, output wire Y);
    nor g1(Y, A, B);
endmodule
"""
        if design_name == "and":
            return """module and_gate(input wire A, input wire B, output wire Y);
    and g1(Y, A, B);
endmodule
"""
        if design_name == "or":
            return """module or_gate(input wire A, input wire B, output wire Y);
    or g1(Y, A, B);
endmodule
"""
        if design_name == "xor":
            return """module xor_gate(input wire A, input wire B, output wire Y);
    xor g1(Y, A, B);
endmodule
"""
        return """module xnor_gate(input wire A, input wire B, output wire Y);
    xnor g1(Y, A, B);
endmodule
"""
    if design_name == "half_adder":
        return """module half_adder(input wire A, input wire B, output wire SUM, output wire COUT);
    xor g1(SUM, A, B);
    and g2(COUT, A, B);
endmodule
"""
    if design_name == "full_adder":
        return """module full_adder(input wire A, input wire B, input wire CIN, output wire SUM, output wire COUT);
    wire axb, ab, cin_xor;
    xor g1(axb, A, B);
    xor g2(SUM, axb, CIN);
    and g3(ab, A, B);
    and g4(cin_xor, CIN, axb);
    or g5(COUT, ab, cin_xor);
endmodule
"""
    if design_name == "mux_2to1":
        return """module mux_2to1(input wire S0, input wire D0, input wire D1, output wire Y);
    wire nS0, w0, w1;
    not g1(nS0, S0);
    and g2(w0, nS0, D0);
    and g3(w1, S0, D1);
    or g4(Y, w0, w1);
endmodule
"""
    if design_name == "mux_4to1":
        return """module mux_4to1(
    input wire S0,
    input wire S1,
    input wire D0,
    input wire D1,
    input wire D2,
    input wire D3,
    output wire Y
);
    wire nS0, nS1, w0, w1, w2, w3, t0, t1;
    not g1(nS0, S0);
    not g2(nS1, S1);
    and g3(w0, nS1, nS0, D0);
    and g4(w1, nS1, S0, D1);
    and g5(w2, S1, nS0, D2);
    and g6(w3, S1, S0, D3);
    or g7(t0, w0, w1);
    or g8(t1, w2, w3);
    or g9(Y, t0, t1);
endmodule
"""
    if design_name == "mux_8to1":
        return """module mux_8to1(
    input wire S0,
    input wire S1,
    input wire S2,
    input wire D0,
    input wire D1,
    input wire D2,
    input wire D3,
    input wire D4,
    input wire D5,
    input wire D6,
    input wire D7,
    output wire Y
);
    wire nS0, nS1, nS2;
    wire w0, w1, w2, w3, w4, w5, w6, w7;
    wire t0, t1, t2, t3;
    not g1(nS0, S0);
    not g2(nS1, S1);
    not g3(nS2, S2);
    and g4(w0, nS2, nS1, nS0, D0);
    and g5(w1, nS2, nS1, S0, D1);
    and g6(w2, nS2, S1, nS0, D2);
    and g7(w3, nS2, S1, S0, D3);
    and g8(w4, S2, nS1, nS0, D4);
    and g9(w5, S2, nS1, S0, D5);
    and g10(w6, S2, S1, nS0, D6);
    and g11(w7, S2, S1, S0, D7);
    or g12(t0, w0, w1);
    or g13(t1, w2, w3);
    or g14(t2, w4, w5);
    or g15(t3, w6, w7);
    or g16(Y, t0, t1, t2, t3);
endmodule
"""
    if design_name == "demux_1to2":
        return """module demux_1to2(input wire SEL, input wire D, output wire Y0, output wire Y1);
    wire nSEL;
    not g1(nSEL, SEL);
    and g2(Y0, nSEL, D);
    and g3(Y1, SEL, D);
endmodule
"""
    if design_name == "comparator":
        return """module comparator_1bit(input wire A, input wire B, output wire EQ, output wire GT, output wire LT);
    wire nA, nB, axb;
    not g1(nA, A);
    not g2(nB, B);
    xnor g3(EQ, A, B);
    and g4(GT, A, nB);
    and g5(LT, nA, B);
endmodule
"""
    if design_name == "decoder_2to4":
        return """module decoder_2to4(input wire A, input wire B, output wire Y0, output wire Y1, output wire Y2, output wire Y3);
    wire nA, nB;
    not g1(nA, A);
    not g2(nB, B);
    and g3(Y0, nA, nB);
    and g4(Y1, nA, B);
    and g5(Y2, A, nB);
    and g6(Y3, A, B);
endmodule
"""
    if design_name == "encoder_4to2":
        return """module encoder_4to2(input wire D0, input wire D1, input wire D2, input wire D3, output wire Y1, output wire Y0);
    or g1(Y1, D2, D3);
    or g2(Y0, D1, D3);
endmodule
"""
    if design_name == "priority_encoder_4to2":
        return """module priority_encoder_4to2(input wire D0, input wire D1, input wire D2, input wire D3, output wire Y1, output wire Y0, output wire VALID);
    or g1(VALID, D0, D1, D2, D3);
    or g2(Y1, D2, D3);
    or g3(Y0, D1, D3);
endmodule
"""
    ff_cell = """module dff_cell(
    input wire CLK,
    input wire D,
    output reg Q
);

always @(posedge CLK) begin
    Q <= D;
end

endmodule
"""
    if design_name == "dff":
        return """module dff(
    input wire CLK,
    input wire D,
    output wire Q
);

dff_cell ff1(.CLK(CLK), .D(D), .Q(Q));

endmodule
""" + ff_cell
    if design_name == "tff":
        return """module tff(
    input wire CLK,
    input wire T,
    output wire Q
);

wire d_next;

xor g1(d_next, T, Q);
dff_cell ff1(.CLK(CLK), .D(d_next), .Q(Q));

endmodule
""" + ff_cell
    if design_name == "jkff":
        return """module jkff(
    input wire CLK,
    input wire J,
    input wire K,
    output wire Q
);

wire nQ, nK, set_term, reset_term, d_next;

not g1(nQ, Q);
and g2(set_term, J, nQ);
not g3(nK, K);
and g4(reset_term, nK, Q);
or g5(d_next, set_term, reset_term);
dff_cell ff1(.CLK(CLK), .D(d_next), .Q(Q));

endmodule
""" + ff_cell
    if design_name == "srff":
        return """module srff(
    input wire CLK,
    input wire S,
    input wire R,
    output wire Q
);

wire nR, hold_term, d_next;

not g1(nR, R);
and g2(hold_term, nR, Q);
or g3(d_next, S, hold_term);
dff_cell ff1(.CLK(CLK), .D(d_next), .Q(Q));

endmodule
""" + ff_cell
    if design_name.startswith("fifo_"):
        return _fifo_family_verilog(design_name, "gate_level")
    if design_name in {"counter_4bit", "shift_register_4bit", "fsm_traffic_light", "fifo_4x8"}:
        return _sequential_family_verilog(design_name, "gate_level")
    if design_name.startswith("counter_"):
        return _counter_family_verilog(design_name, "gate_level")
    if design_name in {"mux_4to1_tree", "mux_8to1_tree"}:
        return _mux_tree_verilog(design_name, "gate_level")
    return verilog_for_dataflow_legacy(design_name)


def _structural_verilog(design_name: str) -> str:
    if design_name in {"uart_tx_8n1", "spi_master_8bit", "i2c_master_simple"}:
        return _protocol_family_verilog(design_name, "structural")
    if mux_spec := _mux_spec(design_name):
        size, is_tree = mux_spec
        if is_tree or size & (size - 1) == 0:
            return _mux_tree_verilog(design_name, "structural")
        return _mux_direct_verilog(design_name, "gate_level")
    if design_name.startswith("shift_register_") and "bit" in design_name:
        return _shift_register_family_verilog(design_name, "structural")
    if design_name == "not":
        return """module not_gate(input wire A, output wire Y);
    buf g1(Y, A);
endmodule
"""
    if design_name == "buffer":
        return """module buffer_gate(input wire A, output wire Y);
    buf g1(Y, A);
endmodule
"""
    if design_name == "nand":
        return """module nand_gate(
    input wire A,
    input wire B,
    output wire Y
);

wire w1;

and g1(w1, A, B);
not g2(Y, w1);

endmodule
"""
    if design_name == "nor":
        return """module nor_gate(
    input wire A,
    input wire B,
    output wire Y
);

wire w1;

or g1(w1, A, B);
not g2(Y, w1);

endmodule
"""
    if design_name == "and":
        return """module and_gate(
    input wire A,
    input wire B,
    output wire Y
);

wire w1;

nand g1(w1, A, B);
not g2(Y, w1);

endmodule
"""
    if design_name == "or":
        return """module or_gate(
    input wire A,
    input wire B,
    output wire Y
);

wire w1;

nor g1(w1, A, B);
not g2(Y, w1);

endmodule
"""
    if design_name == "xor":
        return """module xor_gate(
    input wire A,
    input wire B,
    output wire Y
);

wire w1, w2, w3;

nand g1(w1, A, B);
nand g2(w2, A, w1);
nand g3(w3, B, w1);
nand g4(Y, w2, w3);

endmodule
"""
    if design_name == "xnor":
        return """module xnor_gate(
    input wire A,
    input wire B,
    output wire Y
);

wire w1, w2, w3, w4;

nand g1(w1, A, B);
nand g2(w2, A, w1);
nand g3(w3, B, w1);
nand g4(w4, w2, w3);
not g5(Y, w4);

endmodule
"""
    if design_name == "half_adder":
        return """module half_adder(
    input wire A,
    input wire B,
    output wire SUM,
    output wire COUT
);

wire w1, w2, w3;

nand g1(w1, A, B);
nand g2(w2, A, w1);
nand g3(w3, B, w1);
nand g4(SUM, w2, w3);
and g5(COUT, A, B);

endmodule
"""
    if design_name == "full_adder":
        return """module full_adder(
    input wire A,
    input wire B,
    input wire CIN,
    output wire SUM,
    output wire COUT
);

wire x1, x2, x3, c1, c2;

xor g1(x1, A, B);
xor g2(SUM, x1, CIN);
and g3(c1, A, B);
and g4(c2, x1, CIN);
or g5(COUT, c1, c2);

endmodule
"""
    if design_name == "mux_2to1":
        return """module mux_2to1(
    input wire S0,
    input wire D0,
    input wire D1,
    output wire Y
);

wire nS0, w0, w1;

not g1(nS0, S0);
and g2(w0, nS0, D0);
and g3(w1, S0, D1);
or g4(Y, w0, w1);

endmodule
"""
    if design_name == "mux_4to1":
        return """module mux_4to1(
    input wire S0,
    input wire S1,
    input wire D0,
    input wire D1,
    input wire D2,
    input wire D3,
    output wire Y
);

wire nS0, nS1, w0, w1, w2, w3, t0, t1;

not g1(nS0, S0);
not g2(nS1, S1);
and g3(w0, nS1, nS0, D0);
and g4(w1, nS1, S0, D1);
and g5(w2, S1, nS0, D2);
and g6(w3, S1, S0, D3);
or g7(t0, w0, w1);
or g8(t1, w2, w3);
or g9(Y, t0, t1);

endmodule
"""
    if design_name == "mux_8to1":
        return """module mux_8to1(
    input wire S0,
    input wire S1,
    input wire S2,
    input wire D0,
    input wire D1,
    input wire D2,
    input wire D3,
    input wire D4,
    input wire D5,
    input wire D6,
    input wire D7,
    output wire Y
);

wire nS0, nS1, nS2;
wire w0, w1, w2, w3, w4, w5, w6, w7;
wire t0, t1, t2, t3;

not g1(nS0, S0);
not g2(nS1, S1);
not g3(nS2, S2);
and g4(w0, nS2, nS1, nS0, D0);
and g5(w1, nS2, nS1, S0, D1);
and g6(w2, nS2, S1, nS0, D2);
and g7(w3, nS2, S1, S0, D3);
and g8(w4, S2, nS1, nS0, D4);
and g9(w5, S2, nS1, S0, D5);
and g10(w6, S2, S1, nS0, D6);
and g11(w7, S2, S1, S0, D7);
or g12(t0, w0, w1);
or g13(t1, w2, w3);
or g14(t2, w4, w5);
or g15(t3, w6, w7);
or g16(Y, t0, t1, t2, t3);

endmodule
"""
    if design_name == "demux_1to2":
        return """module demux_1to2(
    input wire SEL,
    input wire D,
    output wire Y0,
    output wire Y1
);

wire nSEL;

not g1(nSEL, SEL);
and g2(Y0, nSEL, D);
and g3(Y1, SEL, D);

endmodule
"""
    if design_name == "comparator":
        return """module comparator_1bit(
    input wire A,
    input wire B,
    output wire EQ,
    output wire GT,
    output wire LT
);

wire nA, nB;

not g1(nA, A);
not g2(nB, B);
xnor g3(EQ, A, B);
and g4(GT, A, nB);
and g5(LT, nA, B);

endmodule
"""
    if design_name == "decoder_2to4":
        return """module decoder_2to4(
    input wire A,
    input wire B,
    output wire Y0,
    output wire Y1,
    output wire Y2,
    output wire Y3
);

wire nA, nB;

not g1(nA, A);
not g2(nB, B);
and g3(Y0, nA, nB);
and g4(Y1, nA, B);
and g5(Y2, A, nB);
and g6(Y3, A, B);

endmodule
"""
    if design_name == "encoder_4to2":
        return """module encoder_4to2(
    input wire D0,
    input wire D1,
    input wire D2,
    input wire D3,
    output wire Y1,
    output wire Y0
);

or g1(Y1, D2, D3);
or g2(Y0, D1, D3);

endmodule
"""
    if design_name == "priority_encoder_4to2":
        return """module priority_encoder_4to2(
    input wire D0,
    input wire D1,
    input wire D2,
    input wire D3,
    output wire Y1,
    output wire Y0,
    output wire VALID
);

or g1(VALID, D0, D1, D2, D3);
or g2(Y1, D2, D3);
or g3(Y0, D1, D3);

endmodule
"""
    if design_name == "dff":
        return """module dff(
    input wire CLK,
    input wire D,
    output wire Q
);

dff_cell ff1(.CLK(CLK), .D(D), .Q(Q));

endmodule

module dff_cell(
    input wire CLK,
    input wire D,
    output reg Q
);

always @(posedge CLK) begin
    Q <= D;
end

endmodule
"""
    if design_name == "tff":
        return """module tff(
    input wire CLK,
    input wire T,
    output wire Q
);

wire d_next;

xor g1(d_next, T, Q);
dff_cell ff1(.CLK(CLK), .D(d_next), .Q(Q));

endmodule

module dff_cell(
    input wire CLK,
    input wire D,
    output reg Q
);

always @(posedge CLK) begin
    Q <= D;
end

endmodule
"""
    if design_name == "jkff":
        return """module jkff(
    input wire CLK,
    input wire J,
    input wire K,
    output wire Q
);

wire nQ, nK, set_term, reset_term, d_next;

not g1(nQ, Q);
not g2(nK, K);
and g3(set_term, J, nQ);
and g4(reset_term, nK, Q);
or g5(d_next, set_term, reset_term);
dff_cell ff1(.CLK(CLK), .D(d_next), .Q(Q));

endmodule

module dff_cell(
    input wire CLK,
    input wire D,
    output reg Q
);

always @(posedge CLK) begin
    Q <= D;
end

endmodule
"""
    if design_name == "srff":
        return """module srff(
    input wire CLK,
    input wire S,
    input wire R,
    output wire Q
);

wire nR, hold_term, d_next;

not g1(nR, R);
and g2(hold_term, nR, Q);
or g3(d_next, S, hold_term);
dff_cell ff1(.CLK(CLK), .D(d_next), .Q(Q));

endmodule

module dff_cell(
    input wire CLK,
    input wire D,
    output reg Q
);

always @(posedge CLK) begin
    Q <= D;
end

endmodule
"""
    if design_name.startswith("fifo_"):
        return _fifo_family_verilog(design_name, "structural")
    if design_name in {"counter_4bit", "shift_register_4bit", "fsm_traffic_light", "fifo_4x8"}:
        return _sequential_family_verilog(design_name, "structural")
    if design_name.startswith("counter_"):
        return _counter_family_verilog(design_name, "structural")
    if design_name in {"mux_4to1_tree", "mux_8to1_tree"}:
        return _mux_tree_verilog(design_name, "structural")
    return verilog_for_dataflow_legacy(design_name)


def _protocol_family_verilog(design_name: str, style: str = "dataflow") -> str:
    style = (style or "dataflow").strip().lower()
    if design_name == "uart_rx_8n1":
        return """module uart_rx_8n1(
    input wire CLK, input wire RST, input wire RX, input wire ENABLE,
    output reg [7:0] DATA_OUT, output reg DATA_READY, output reg BUSY, output reg FRAME_ERR
);
    localparam IDLE = 3'd0, START_BIT = 3'd1, DATA_BITS = 3'd2, STOP_BIT = 3'd3;
    reg [2:0] STATE; reg [2:0] BIT_IDX; reg [3:0] BAUD_CNT; reg [7:0] SHIFT;
    always @(posedge CLK) begin
        if (RST) begin STATE <= IDLE; BIT_IDX <= 0; BAUD_CNT <= 0; SHIFT <= 0; DATA_OUT <= 0; DATA_READY <= 0; BUSY <= 0; FRAME_ERR <= 0; end
        else begin DATA_READY <= 0; FRAME_ERR <= 0;
            case (STATE)
                IDLE: if (ENABLE && !RX) begin STATE <= START_BIT; BUSY <= 1; BAUD_CNT <= 0; end else BUSY <= 0;
                START_BIT: if (BAUD_CNT == 4'd3) begin STATE <= DATA_BITS; BAUD_CNT <= 0; BIT_IDX <= 0; end else BAUD_CNT <= BAUD_CNT + 1;
                DATA_BITS: if (BAUD_CNT == 4'd3) begin SHIFT <= {RX, SHIFT[7:1]}; BAUD_CNT <= 0; if (BIT_IDX == 3'd7) STATE <= STOP_BIT; else BIT_IDX <= BIT_IDX + 1; end else BAUD_CNT <= BAUD_CNT + 1;
                STOP_BIT: if (BAUD_CNT == 4'd3) begin STATE <= IDLE; DATA_OUT <= SHIFT; DATA_READY <= 1; BUSY <= 0; FRAME_ERR <= ~RX; end else BAUD_CNT <= BAUD_CNT + 1;
            endcase
        end
    end
endmodule
"""
    if design_name == "spi_slave_8bit":
        return """module spi_slave_8bit(
    input wire CLK, input wire RST, input wire SS_N, input wire SCLK, input wire MOSI, input wire MISO_IN,
    output reg MISO, output reg [7:0] DATA_OUT, output reg DATA_READY, output reg BUSY
);
    reg [7:0] SHIFT; reg [2:0] BIT_IDX; reg SCLK_D;
    always @(posedge CLK) begin
        if (RST) begin SHIFT <= 0; BIT_IDX <= 0; SCLK_D <= 0; MISO <= 0; DATA_OUT <= 0; DATA_READY <= 0; BUSY <= 0; end
        else begin DATA_READY <= 0; BUSY <= ~SS_N; if (SS_N) BIT_IDX <= 0; else if (!SCLK_D && SCLK) begin SHIFT <= {SHIFT[6:0], MOSI}; MISO <= SHIFT[7]; if (BIT_IDX == 3'd7) begin DATA_OUT <= {SHIFT[6:0], MOSI}; DATA_READY <= 1; end else BIT_IDX <= BIT_IDX + 1; end SCLK_D <= SCLK; end
    end
endmodule
"""
    if design_name == "i2c_slave_simple":
        return """module i2c_slave_simple(
    input wire CLK, input wire RST, input wire SCL, input wire SDA_IN, input wire [6:0] ADDR, input wire [7:0] DATA_IN,
    output reg SDA_OUT, output reg SDA_OE, output reg BUSY, output reg DONE, output reg ACK, output reg DATA_READY
);
    reg [1:0] STATE; reg [3:0] BIT_IDX; reg [7:0] SHIFT; reg SCL_D;
    always @(posedge CLK) begin
        if (RST) begin STATE <= 0; BIT_IDX <= 0; SHIFT <= 0; SCL_D <= 1; SDA_OUT <= 1; SDA_OE <= 0; BUSY <= 0; DONE <= 0; ACK <= 0; DATA_READY <= 0; end
        else begin DATA_READY <= 0; DONE <= 0;
            if (STATE == 2'd0 && SCL && SCL_D && !SDA_IN) begin STATE <= 2'd1; BUSY <= 1; end
            else if (STATE == 2'd1) begin STATE <= 2'd2; BIT_IDX <= 0; end
            else if (STATE == 2'd2 && !SCL_D && SCL) begin SHIFT <= {SHIFT[6:0], SDA_IN}; if (BIT_IDX == 4'd7) begin ACK <= 1; STATE <= 2'd3; end else BIT_IDX <= BIT_IDX + 1; end
            else if (STATE == 2'd3) begin SDA_OE <= 1; SDA_OUT <= 0; DATA_READY <= 1; DONE <= 1; BUSY <= 0; STATE <= 0; end
            SCL_D <= SCL;
        end
    end
endmodule
"""
    if design_name == "axi_lite_slave_simple":
        return """module axi_lite_slave_simple(
    input wire ACLK, input wire ARESETN, input wire [31:0] AWADDR, input wire AWVALID, input wire [31:0] WDATA, input wire WVALID,
    input wire [31:0] ARADDR, input wire ARVALID, input wire RREADY, input wire [3:0] WSTRB,
    output reg AWREADY, output reg WREADY, output reg BVALID, output reg [1:0] BRESP, output reg ARREADY, output reg [31:0] RDATA, output reg RVALID, output reg [1:0] RRESP
);
    reg [31:0] regs[0:3];
    always @(posedge ACLK) begin
        if (!ARESETN) begin AWREADY <= 0; WREADY <= 0; BVALID <= 0; BRESP <= 2'b00; ARREADY <= 0; RDATA <= 0; RVALID <= 0; RRESP <= 2'b00; regs[0] <= 0; regs[1] <= 0; regs[2] <= 0; regs[3] <= 0; end
        else begin AWREADY <= AWVALID & WVALID; WREADY <= AWVALID & WVALID; if (AWVALID && WVALID) begin regs[AWADDR[3:2]] <= WDATA; BVALID <= 1; end else if (BVALID && RREADY) BVALID <= 0; if (ARVALID) begin ARREADY <= 1; RDATA <= regs[ARADDR[3:2]]; RVALID <= 1; end else if (RVALID && RREADY) RVALID <= 0; end
    end
endmodule
"""
    if design_name == "uart_tx_8n1":
        if style == "behavioral":
            return """module uart_tx_8n1(
    input wire CLK,
    input wire RST,
    input wire START,
    input wire [7:0] DATA_IN,
    output reg TX,
    output reg BUSY,
    output reg DONE
);
    localparam IDLE = 3'd0, START_BIT = 3'd1, DATA_BITS = 3'd2, STOP_BIT = 3'd3;
    reg [2:0] STATE;
    reg [3:0] BIT_IDX;
    reg [3:0] BAUD_CNT;
    reg [7:0] SHIFTER;

    always @(posedge CLK) begin
        if (RST) begin
            STATE <= IDLE;
            BIT_IDX <= 4'd0;
            BAUD_CNT <= 4'd0;
            SHIFTER <= 8'd0;
            TX <= 1'b1;
            BUSY <= 1'b0;
            DONE <= 1'b0;
        end else begin
            DONE <= 1'b0;
            case (STATE)
                IDLE: begin
                    TX <= 1'b1;
                    BUSY <= 1'b0;
                    if (START) begin
                        STATE <= START_BIT;
                        SHIFTER <= DATA_IN;
                        BIT_IDX <= 4'd0;
                        BAUD_CNT <= 4'd0;
                        BUSY <= 1'b1;
                    end
                end
                START_BIT: begin
                    TX <= 1'b0;
                    BUSY <= 1'b1;
                    if (BAUD_CNT == 4'd3) begin
                        STATE <= DATA_BITS;
                        BAUD_CNT <= 4'd0;
                    end else begin
                        BAUD_CNT <= BAUD_CNT + 4'd1;
                    end
                end
                DATA_BITS: begin
                    TX <= SHIFTER[0];
                    BUSY <= 1'b1;
                    if (BAUD_CNT == 4'd3) begin
                        BAUD_CNT <= 4'd0;
                        SHIFTER <= {1'b0, SHIFTER[7:1]};
                        if (BIT_IDX == 4'd7)
                            STATE <= STOP_BIT;
                        else
                            BIT_IDX <= BIT_IDX + 4'd1;
                    end else begin
                        BAUD_CNT <= BAUD_CNT + 4'd1;
                    end
                end
                STOP_BIT: begin
                    TX <= 1'b1;
                    BUSY <= 1'b1;
                    if (BAUD_CNT == 4'd3) begin
                        STATE <= IDLE;
                        BAUD_CNT <= 4'd0;
                        BUSY <= 1'b0;
                        DONE <= 1'b1;
                    end else begin
                        BAUD_CNT <= BAUD_CNT + 4'd1;
                    end
                end
            endcase
        end
    end
endmodule
"""
        if style in {"gate_level", "structural"}:
            return """module uart_tx_8n1(
    input wire CLK,
    input wire RST,
    input wire START,
    input wire [7:0] DATA_IN,
    output wire TX,
    output wire BUSY,
    output wire DONE
);
    wire [2:0] STATE_NEXT;
    wire [3:0] BIT_IDX_NEXT;
    wire [3:0] BAUD_CNT_NEXT;
    wire [7:0] SHIFTER_NEXT;
    wire TX_NEXT;
    wire BUSY_NEXT;
    wire DONE_NEXT;

    uart_tx_8n1_next u_next(
        .STATE(STATE),
        .BIT_IDX(BIT_IDX),
        .BAUD_CNT(BAUD_CNT),
        .SHIFTER(SHIFTER),
        .START(START),
        .DATA_IN(DATA_IN),
        .TX_NEXT(TX_NEXT),
        .BUSY_NEXT(BUSY_NEXT),
        .DONE_NEXT(DONE_NEXT),
        .STATE_NEXT(STATE_NEXT),
        .BIT_IDX_NEXT(BIT_IDX_NEXT),
        .BAUD_CNT_NEXT(BAUD_CNT_NEXT),
        .SHIFTER_NEXT(SHIFTER_NEXT)
    );
    uart_tx_8n1_reg u_reg(
        .CLK(CLK),
        .RST(RST),
        .STATE_NEXT(STATE_NEXT),
        .BIT_IDX_NEXT(BIT_IDX_NEXT),
        .BAUD_CNT_NEXT(BAUD_CNT_NEXT),
        .SHIFTER_NEXT(SHIFTER_NEXT),
        .TX_NEXT(TX_NEXT),
        .BUSY_NEXT(BUSY_NEXT),
        .DONE_NEXT(DONE_NEXT),
        .TX(TX),
        .BUSY(BUSY),
        .DONE(DONE)
    );
endmodule

module uart_tx_8n1_next(
    input wire [2:0] STATE,
    input wire [3:0] BIT_IDX,
    input wire [3:0] BAUD_CNT,
    input wire [7:0] SHIFTER,
    input wire START,
    input wire [7:0] DATA_IN,
    output wire TX_NEXT,
    output wire BUSY_NEXT,
    output wire DONE_NEXT,
    output wire [2:0] STATE_NEXT,
    output wire [3:0] BIT_IDX_NEXT,
    output wire [3:0] BAUD_CNT_NEXT,
    output wire [7:0] SHIFTER_NEXT
);
    localparam IDLE = 3'd0, START_BIT = 3'd1, DATA_BITS = 3'd2, STOP_BIT = 3'd3;
    assign TX_NEXT = (STATE == IDLE) ? 1'b1 :
                     (STATE == START_BIT) ? 1'b0 :
                     (STATE == DATA_BITS) ? SHIFTER[0] : 1'b1;
    assign BUSY_NEXT = (STATE != IDLE) || START;
    assign DONE_NEXT = (STATE == STOP_BIT) && (BAUD_CNT == 4'd3);
    assign SHIFTER_NEXT = (STATE == IDLE && START) ? DATA_IN :
                          (STATE == DATA_BITS && BAUD_CNT == 4'd3) ? {1'b0, SHIFTER[7:1]} : SHIFTER;
    assign BIT_IDX_NEXT = (STATE == DATA_BITS && BAUD_CNT == 4'd3 && BIT_IDX != 4'd7) ? (BIT_IDX + 4'd1) : BIT_IDX;
    assign BAUD_CNT_NEXT = (STATE == IDLE && !START) ? 4'd0 :
                           (BAUD_CNT == 4'd3) ? 4'd0 : (BAUD_CNT + 4'd1);
    assign STATE_NEXT = (STATE == IDLE && START) ? START_BIT :
                        (STATE == START_BIT && BAUD_CNT == 4'd3) ? DATA_BITS :
                        (STATE == DATA_BITS && BAUD_CNT == 4'd3 && BIT_IDX == 4'd7) ? STOP_BIT :
                        (STATE == DATA_BITS && BAUD_CNT == 4'd3) ? DATA_BITS :
                        (STATE == STOP_BIT && BAUD_CNT == 4'd3) ? IDLE : STATE;
endmodule

module uart_tx_8n1_reg(
    input wire CLK,
    input wire RST,
    input wire [2:0] STATE_NEXT,
    input wire [3:0] BIT_IDX_NEXT,
    input wire [3:0] BAUD_CNT_NEXT,
    input wire [7:0] SHIFTER_NEXT,
    input wire TX_NEXT,
    input wire BUSY_NEXT,
    input wire DONE_NEXT,
    output reg TX,
    output reg BUSY,
    output reg DONE
);
    reg [2:0] STATE;
    reg [3:0] BIT_IDX;
    reg [3:0] BAUD_CNT;
    reg [7:0] SHIFTER;
    always @(posedge CLK) begin
        if (RST) begin
            STATE <= 3'd0;
            BIT_IDX <= 4'd0;
            BAUD_CNT <= 4'd0;
            SHIFTER <= 8'd0;
            TX <= 1'b1;
            BUSY <= 1'b0;
            DONE <= 1'b0;
        end else begin
            STATE <= STATE_NEXT;
            BIT_IDX <= BIT_IDX_NEXT;
            BAUD_CNT <= BAUD_CNT_NEXT;
            SHIFTER <= SHIFTER_NEXT;
            TX <= TX_NEXT;
            BUSY <= BUSY_NEXT;
            DONE <= DONE_NEXT;
        end
    end
endmodule
"""
        if style == "dataflow":
            return """module uart_tx_8n1(
    input wire CLK,
    input wire RST,
    input wire START,
    input wire [7:0] DATA_IN,
    output reg TX,
    output reg BUSY,
    output reg DONE
);
    localparam IDLE = 3'd0, START_BIT = 3'd1, DATA_BITS = 3'd2, STOP_BIT = 3'd3;
    reg [2:0] STATE;
    reg [3:0] BIT_IDX;
    reg [3:0] BAUD_CNT;
    reg [7:0] SHIFTER;
    wire [2:0] STATE_NEXT;
    wire [3:0] BIT_IDX_NEXT;
    wire [3:0] BAUD_CNT_NEXT;
    wire [7:0] SHIFTER_NEXT;

    assign STATE_NEXT = (STATE == IDLE && START) ? START_BIT :
                        (STATE == START_BIT && BAUD_CNT == 4'd3) ? DATA_BITS :
                        (STATE == DATA_BITS && BAUD_CNT == 4'd3 && BIT_IDX == 4'd7) ? STOP_BIT :
                        (STATE == DATA_BITS && BAUD_CNT == 4'd3) ? DATA_BITS :
                        (STATE == STOP_BIT && BAUD_CNT == 4'd3) ? IDLE : STATE;
    assign BIT_IDX_NEXT = (STATE == DATA_BITS && BAUD_CNT == 4'd3 && BIT_IDX != 4'd7) ? (BIT_IDX + 4'd1) : BIT_IDX;
    assign BAUD_CNT_NEXT = (STATE == IDLE && !START) ? 4'd0 : (BAUD_CNT == 4'd3 ? 4'd0 : BAUD_CNT + 4'd1);
    assign SHIFTER_NEXT = (STATE == IDLE && START) ? DATA_IN :
                          (STATE == DATA_BITS && BAUD_CNT == 4'd3) ? {1'b0, SHIFTER[7:1]} : SHIFTER;

    always @(posedge CLK) begin
        if (RST) begin
            STATE <= IDLE;
            BIT_IDX <= 4'd0;
            BAUD_CNT <= 4'd0;
            SHIFTER <= 8'd0;
            TX <= 1'b1;
            BUSY <= 1'b0;
            DONE <= 1'b0;
        end else begin
            STATE <= STATE_NEXT;
            BIT_IDX <= BIT_IDX_NEXT;
            BAUD_CNT <= BAUD_CNT_NEXT;
            SHIFTER <= SHIFTER_NEXT;
            TX <= (STATE == IDLE) ? 1'b1 :
                  (STATE == START_BIT) ? 1'b0 :
                  (STATE == DATA_BITS) ? SHIFTER[0] : 1'b1;
            BUSY <= (STATE != IDLE) || START;
            DONE <= (STATE == STOP_BIT) && (BAUD_CNT == 4'd3);
        end
    end
endmodule
"""
    if design_name == "spi_master_8bit":
        if style == "behavioral":
            return """module spi_master_8bit(
    input wire CLK,
    input wire RST,
    input wire START,
    input wire MISO,
    input wire [7:0] DATA_IN,
    output reg SCLK,
    output reg MOSI,
    output reg CS,
    output reg BUSY,
    output reg DONE,
    output reg [7:0] DATA_OUT
);
    reg [2:0] BIT_IDX;
    reg [7:0] SHIFT;
    reg [3:0] DIV;

    always @(posedge CLK) begin
        if (RST) begin
            BIT_IDX <= 3'd0;
            SHIFT <= 8'd0;
            DIV <= 4'd0;
            SCLK <= 1'b0;
            MOSI <= 1'b0;
            CS <= 1'b1;
            BUSY <= 1'b0;
            DONE <= 1'b0;
            DATA_OUT <= 8'd0;
        end else begin
            DONE <= 1'b0;
            if (START && !BUSY) begin
                BUSY <= 1'b1;
                CS <= 1'b0;
                SHIFT <= DATA_IN;
                BIT_IDX <= 3'd0;
                DIV <= 4'd0;
            end else if (BUSY) begin
                DIV <= DIV + 4'd1;
                if (DIV == 4'd3) begin
                    DIV <= 4'd0;
                    SCLK <= ~SCLK;
                    if (SCLK == 1'b0) begin
                        MOSI <= SHIFT[7];
                        SHIFT <= {SHIFT[6:0], MISO};
                        BIT_IDX <= BIT_IDX + 3'd1;
                        if (BIT_IDX == 3'd7) begin
                            BUSY <= 1'b0;
                            CS <= 1'b1;
                            DONE <= 1'b1;
                            DATA_OUT <= {SHIFT[6:0], MISO};
                        end
                    end
                end
            end else begin
                SCLK <= 1'b0;
                CS <= 1'b1;
            end
        end
    end
endmodule
"""
        if style in {"gate_level", "structural"}:
            return """module spi_master_8bit(
    input wire CLK,
    input wire RST,
    input wire START,
    input wire MISO,
    input wire [7:0] DATA_IN,
    output wire SCLK,
    output wire MOSI,
    output wire CS,
    output wire BUSY,
    output wire DONE,
    output wire [7:0] DATA_OUT
);
    wire SCLK_NEXT, MOSI_NEXT, CS_NEXT, BUSY_NEXT, DONE_NEXT;
    wire [7:0] DATA_OUT_NEXT;
    wire [2:0] BIT_IDX_NEXT;
    wire [7:0] SHIFT_NEXT;
    wire [3:0] DIV_NEXT;

    spi_master_8bit_next u_next(
        .BIT_IDX(BIT_IDX),
        .SHIFT(SHIFT),
        .DIV(DIV),
        .START(START),
        .MISO(MISO),
        .DATA_IN(DATA_IN),
        .SCLK(SCLK),
        .SCLK_NEXT(SCLK_NEXT),
        .MOSI_NEXT(MOSI_NEXT),
        .CS_NEXT(CS_NEXT),
        .BUSY_NEXT(BUSY_NEXT),
        .DONE_NEXT(DONE_NEXT),
        .DATA_OUT_NEXT(DATA_OUT_NEXT),
        .BIT_IDX_NEXT(BIT_IDX_NEXT),
        .SHIFT_NEXT(SHIFT_NEXT),
        .DIV_NEXT(DIV_NEXT)
    );
    spi_master_8bit_reg u_reg(
        .CLK(CLK),
        .RST(RST),
        .SCLK_NEXT(SCLK_NEXT),
        .MOSI_NEXT(MOSI_NEXT),
        .CS_NEXT(CS_NEXT),
        .BUSY_NEXT(BUSY_NEXT),
        .DONE_NEXT(DONE_NEXT),
        .DATA_OUT_NEXT(DATA_OUT_NEXT),
        .BIT_IDX_NEXT(BIT_IDX_NEXT),
        .SHIFT_NEXT(SHIFT_NEXT),
        .DIV_NEXT(DIV_NEXT),
        .SCLK(SCLK),
        .MOSI(MOSI),
        .CS(CS),
        .BUSY(BUSY),
        .DONE(DONE),
        .DATA_OUT(DATA_OUT)
    );
endmodule

module spi_master_8bit_next(
    input wire [2:0] BIT_IDX,
    input wire [7:0] SHIFT,
    input wire [3:0] DIV,
    input wire START,
    input wire MISO,
    input wire [7:0] DATA_IN,
    input wire SCLK,
    output wire SCLK_NEXT,
    output wire MOSI_NEXT,
    output wire CS_NEXT,
    output wire BUSY_NEXT,
    output wire DONE_NEXT,
    output wire [7:0] DATA_OUT_NEXT,
    output wire [2:0] BIT_IDX_NEXT,
    output wire [7:0] SHIFT_NEXT,
    output wire [3:0] DIV_NEXT
);
    assign SCLK_NEXT = (DIV == 4'd3) ? ~SCLK : SCLK;
    assign MOSI_NEXT = SHIFT[7];
    assign CS_NEXT = (START && !BUSY_NEXT) ? 1'b0 : 1'b1;
    assign BUSY_NEXT = START | (BIT_IDX != 3'd7);
    assign DONE_NEXT = (BIT_IDX == 3'd7) && (DIV == 4'd3);
    assign DATA_OUT_NEXT = {SHIFT[6:0], MISO};
    assign BIT_IDX_NEXT = (DIV == 4'd3 && BIT_IDX != 3'd7) ? (BIT_IDX + 3'd1) : BIT_IDX;
    assign SHIFT_NEXT = START ? DATA_IN : {SHIFT[6:0], MISO};
    assign DIV_NEXT = (DIV == 4'd3) ? 4'd0 : (DIV + 4'd1);
endmodule

module spi_master_8bit_reg(
    input wire CLK,
    input wire RST,
    input wire SCLK_NEXT,
    input wire MOSI_NEXT,
    input wire CS_NEXT,
    input wire BUSY_NEXT,
    input wire DONE_NEXT,
    input wire [7:0] DATA_OUT_NEXT,
    input wire [2:0] BIT_IDX_NEXT,
    input wire [7:0] SHIFT_NEXT,
    input wire [3:0] DIV_NEXT,
    output reg SCLK,
    output reg MOSI,
    output reg CS,
    output reg BUSY,
    output reg DONE,
    output reg [7:0] DATA_OUT
);
    reg [2:0] BIT_IDX;
    reg [7:0] SHIFT;
    reg [3:0] DIV;
    always @(posedge CLK) begin
        if (RST) begin
            BIT_IDX <= 3'd0;
            SHIFT <= 8'd0;
            DIV <= 4'd0;
            SCLK <= 1'b0;
            MOSI <= 1'b0;
            CS <= 1'b1;
            BUSY <= 1'b0;
            DONE <= 1'b0;
            DATA_OUT <= 8'd0;
        end else begin
            BIT_IDX <= BIT_IDX_NEXT;
            SHIFT <= SHIFT_NEXT;
            DIV <= DIV_NEXT;
            SCLK <= SCLK_NEXT;
            MOSI <= MOSI_NEXT;
            CS <= CS_NEXT;
            BUSY <= BUSY_NEXT;
            DONE <= DONE_NEXT;
            DATA_OUT <= DATA_OUT_NEXT;
        end
    end
endmodule
"""
        return """module spi_master_8bit(
    input wire CLK,
    input wire RST,
    input wire START,
    input wire MISO,
    input wire [7:0] DATA_IN,
    output reg SCLK,
    output reg MOSI,
    output reg CS,
    output reg BUSY,
    output reg DONE,
    output reg [7:0] DATA_OUT
);
    reg [2:0] BIT_IDX;
    reg [7:0] SHIFT;
    reg [3:0] DIV;

    always @(posedge CLK) begin
        if (RST) begin
            BIT_IDX <= 3'd0;
            SHIFT <= 8'd0;
            DIV <= 4'd0;
            SCLK <= 1'b0;
            MOSI <= 1'b0;
            CS <= 1'b1;
            BUSY <= 1'b0;
            DONE <= 1'b0;
            DATA_OUT <= 8'd0;
        end else begin
            DONE <= 1'b0;
            if (START && !BUSY) begin
                BUSY <= 1'b1;
                CS <= 1'b0;
                SHIFT <= DATA_IN;
                BIT_IDX <= 3'd0;
                DIV <= 4'd0;
            end else if (BUSY) begin
                DIV <= DIV + 4'd1;
                if (DIV == 4'd3) begin
                    DIV <= 4'd0;
                    SCLK <= ~SCLK;
                    if (SCLK == 1'b0) begin
                        MOSI <= SHIFT[7];
                        SHIFT <= {SHIFT[6:0], MISO};
                        BIT_IDX <= BIT_IDX + 3'd1;
                        if (BIT_IDX == 3'd7) begin
                            BUSY <= 1'b0;
                            CS <= 1'b1;
                            DONE <= 1'b1;
                            DATA_OUT <= {SHIFT[6:0], MISO};
                        end
                    end
                end
            end else begin
                SCLK <= 1'b0;
                CS <= 1'b1;
            end
        end
    end
endmodule
"""
    if design_name == "i2c_master_simple":
        if style in {"gate_level", "structural"}:
            return """module i2c_master_simple(
    input wire CLK,
    input wire RST,
    input wire START,
    input wire SDA_IN,
    input wire [6:0] ADDR,
    input wire [7:0] DATA_IN,
    output wire SCL,
    output wire SDA_OUT,
    output wire SDA_OE,
    output wire BUSY,
    output wire DONE,
    output wire ACK
);
    wire [1:0] STATE_NEXT;
    wire [3:0] BIT_IDX_NEXT;
    wire [3:0] DIV_NEXT;
    wire [7:0] SHIFT_NEXT;
    wire SCL_NEXT;
    wire SDA_OUT_NEXT;
    wire SDA_OE_NEXT;
    wire BUSY_NEXT;
    wire DONE_NEXT;
    wire ACK_NEXT;

    i2c_master_simple_next u_next(
        .STATE(STATE),
        .BIT_IDX(BIT_IDX),
        .DIV(DIV),
        .SHIFT(SHIFT),
        .START(START),
        .SDA_IN(SDA_IN),
        .ADDR(ADDR),
        .DATA_IN(DATA_IN),
        .SCL(SCL),
        .STATE_NEXT(STATE_NEXT),
        .BIT_IDX_NEXT(BIT_IDX_NEXT),
        .DIV_NEXT(DIV_NEXT),
        .SHIFT_NEXT(SHIFT_NEXT),
        .SCL_NEXT(SCL_NEXT),
        .SDA_OUT_NEXT(SDA_OUT_NEXT),
        .SDA_OE_NEXT(SDA_OE_NEXT),
        .BUSY_NEXT(BUSY_NEXT),
        .DONE_NEXT(DONE_NEXT),
        .ACK_NEXT(ACK_NEXT)
    );
    i2c_master_simple_reg u_reg(
        .CLK(CLK),
        .RST(RST),
        .STATE_NEXT(STATE_NEXT),
        .BIT_IDX_NEXT(BIT_IDX_NEXT),
        .DIV_NEXT(DIV_NEXT),
        .SHIFT_NEXT(SHIFT_NEXT),
        .SCL_NEXT(SCL_NEXT),
        .SDA_OUT_NEXT(SDA_OUT_NEXT),
        .SDA_OE_NEXT(SDA_OE_NEXT),
        .BUSY_NEXT(BUSY_NEXT),
        .DONE_NEXT(DONE_NEXT),
        .ACK_NEXT(ACK_NEXT),
        .SCL(SCL),
        .SDA_OUT(SDA_OUT),
        .SDA_OE(SDA_OE),
        .BUSY(BUSY),
        .DONE(DONE),
        .ACK(ACK)
    );
endmodule

module i2c_master_simple_next(
    input wire [1:0] STATE,
    input wire [3:0] BIT_IDX,
    input wire [3:0] DIV,
    input wire [7:0] SHIFT,
    input wire START,
    input wire SDA_IN,
    input wire [6:0] ADDR,
    input wire [7:0] DATA_IN,
    input wire SCL,
    output wire [1:0] STATE_NEXT,
    output wire [3:0] BIT_IDX_NEXT,
    output wire [3:0] DIV_NEXT,
    output wire [7:0] SHIFT_NEXT,
    output wire SCL_NEXT,
    output wire SDA_OUT_NEXT,
    output wire SDA_OE_NEXT,
    output wire BUSY_NEXT,
    output wire DONE_NEXT,
    output wire ACK_NEXT
);
    localparam IDLE = 2'd0, START_S = 2'd1, TRANSFER = 2'd2, STOP_S = 2'd3;
    assign STATE_NEXT = (STATE == IDLE && START) ? START_S :
                        (STATE == START_S) ? TRANSFER :
                        (STATE == TRANSFER && BIT_IDX == 4'd7 && DIV == 4'd3) ? STOP_S :
                        (STATE == STOP_S) ? IDLE : STATE;
    assign BIT_IDX_NEXT = (STATE == TRANSFER && DIV == 4'd3) ? (BIT_IDX + 4'd1) : BIT_IDX;
    assign DIV_NEXT = (STATE == IDLE) ? 4'd0 : (DIV == 4'd3 ? 4'd0 : DIV + 4'd1);
    assign SHIFT_NEXT = (STATE == START_S) ? DATA_IN : {SHIFT[6:0], SDA_IN};
    assign SCL_NEXT = (STATE == IDLE || STATE == START_S || STATE == STOP_S) ? 1'b1 : ~SCL;
    assign SDA_OUT_NEXT = (STATE == START_S) ? 1'b0 : SHIFT[7];
    assign SDA_OE_NEXT = (STATE == IDLE) ? 1'b0 : 1'b1;
    assign BUSY_NEXT = (STATE != IDLE) || START;
    assign DONE_NEXT = (STATE == STOP_S);
    assign ACK_NEXT = ~SDA_IN;
endmodule

module i2c_master_simple_reg(
    input wire CLK,
    input wire RST,
    input wire [1:0] STATE_NEXT,
    input wire [3:0] BIT_IDX_NEXT,
    input wire [3:0] DIV_NEXT,
    input wire [7:0] SHIFT_NEXT,
    input wire SCL_NEXT,
    input wire SDA_OUT_NEXT,
    input wire SDA_OE_NEXT,
    input wire BUSY_NEXT,
    input wire DONE_NEXT,
    input wire ACK_NEXT,
    output reg SCL,
    output reg SDA_OUT,
    output reg SDA_OE,
    output reg BUSY,
    output reg DONE,
    output reg ACK
);
    reg [1:0] STATE;
    reg [3:0] BIT_IDX;
    reg [3:0] DIV;
    reg [7:0] SHIFT;
    always @(posedge CLK) begin
        if (RST) begin
            STATE <= 2'd0;
            BIT_IDX <= 4'd0;
            DIV <= 4'd0;
            SHIFT <= 8'd0;
            SCL <= 1'b1;
            SDA_OUT <= 1'b1;
            SDA_OE <= 1'b0;
            BUSY <= 1'b0;
            DONE <= 1'b0;
            ACK <= 1'b0;
        end else begin
            STATE <= STATE_NEXT;
            BIT_IDX <= BIT_IDX_NEXT;
            DIV <= DIV_NEXT;
            SHIFT <= SHIFT_NEXT;
            SCL <= SCL_NEXT;
            SDA_OUT <= SDA_OUT_NEXT;
            SDA_OE <= SDA_OE_NEXT;
            BUSY <= BUSY_NEXT;
            DONE <= DONE_NEXT;
            ACK <= ACK_NEXT;
        end
    end
endmodule
"""
        if style == "dataflow":
            return """module i2c_master_simple(
    input wire CLK,
    input wire RST,
    input wire START,
    input wire SDA_IN,
    input wire [6:0] ADDR,
    input wire [7:0] DATA_IN,
    output reg SCL,
    output reg SDA_OUT,
    output reg SDA_OE,
    output reg BUSY,
    output reg DONE,
    output reg ACK
);
    reg [1:0] STATE;
    reg [3:0] BIT_IDX;
    reg [3:0] DIV;
    reg [7:0] SHIFT;
    wire [1:0] STATE_NEXT;
    wire [3:0] BIT_IDX_NEXT;
    wire [3:0] DIV_NEXT;
    wire [7:0] SHIFT_NEXT;

    assign STATE_NEXT = (STATE == 2'd0 && START) ? 2'd1 :
                        (STATE == 2'd1) ? 2'd2 :
                        (STATE == 2'd2 && BIT_IDX == 4'd7 && DIV == 4'd3) ? 2'd3 :
                        (STATE == 2'd3) ? 2'd0 : STATE;
    assign BIT_IDX_NEXT = (STATE == 2'd2 && DIV == 4'd3) ? (BIT_IDX + 4'd1) : BIT_IDX;
    assign DIV_NEXT = (STATE == 2'd0) ? 4'd0 : (DIV == 4'd3 ? 4'd0 : DIV + 4'd1);
    assign SHIFT_NEXT = (STATE == 2'd1) ? DATA_IN : {SHIFT[6:0], SDA_IN};

    always @(posedge CLK) begin
        if (RST) begin
            STATE <= 2'd0;
            BIT_IDX <= 4'd0;
            DIV <= 4'd0;
            SHIFT <= 8'd0;
            SCL <= 1'b1;
            SDA_OUT <= 1'b1;
            SDA_OE <= 1'b0;
            BUSY <= 1'b0;
            DONE <= 1'b0;
            ACK <= 1'b0;
        end else begin
            STATE <= STATE_NEXT;
            BIT_IDX <= BIT_IDX_NEXT;
            DIV <= DIV_NEXT;
            SHIFT <= SHIFT_NEXT;
            SCL <= (STATE == 2'd0 || STATE == 2'd1 || STATE == 2'd3) ? 1'b1 : ~SCL;
            SDA_OUT <= (STATE == 2'd1) ? 1'b0 : SHIFT[7];
            SDA_OE <= (STATE == 2'd0) ? 1'b0 : 1'b1;
            BUSY <= (STATE != 2'd0) || START;
            DONE <= (STATE == 2'd3);
            ACK <= ~SDA_IN;
        end
    end
endmodule
"""
        return """module i2c_master_simple(
    input wire CLK,
    input wire RST,
    input wire START,
    input wire SDA_IN,
    input wire [6:0] ADDR,
    input wire [7:0] DATA_IN,
    output reg SCL,
    output reg SDA_OUT,
    output reg SDA_OE,
    output reg BUSY,
    output reg DONE,
    output reg ACK
);
    reg [1:0] STATE;
    reg [3:0] BIT_IDX;
    reg [3:0] DIV;
    reg [7:0] SHIFT;

    always @(posedge CLK) begin
        if (RST) begin
            STATE <= 2'd0;
            BIT_IDX <= 4'd0;
            DIV <= 4'd0;
            SHIFT <= 8'd0;
            SCL <= 1'b1;
            SDA_OUT <= 1'b1;
            SDA_OE <= 1'b0;
            BUSY <= 1'b0;
            DONE <= 1'b0;
            ACK <= 1'b0;
        end else begin
            DONE <= 1'b0;
            case (STATE)
                2'd0: begin
                    SCL <= 1'b1;
                    SDA_OE <= 1'b0;
                    BUSY <= 1'b0;
                    if (START) begin
                        STATE <= 2'd1;
                        SHIFT <= DATA_IN;
                        BUSY <= 1'b1;
                    end
                end
                2'd1: begin
                    SDA_OE <= 1'b1;
                    SDA_OUT <= 1'b0;
                    STATE <= 2'd2;
                    BIT_IDX <= 4'd0;
                    DIV <= 4'd0;
                end
                2'd2: begin
                    DIV <= DIV + 4'd1;
                    if (DIV == 4'd3) begin
                        DIV <= 4'd0;
                        SCL <= ~SCL;
                        if (SCL == 1'b0) begin
                            SDA_OUT <= SHIFT[7];
                            SHIFT <= {SHIFT[6:0], SDA_IN};
                            BIT_IDX <= BIT_IDX + 4'd1;
                            if (BIT_IDX == 4'd7) begin
                                ACK <= ~SDA_IN;
                                STATE <= 2'd3;
                            end
                        end
                    end
                end
                default: begin
                    SDA_OUT <= 1'b0;
                    SDA_OE <= 1'b0;
                    SCL <= 1'b1;
                    STATE <= 2'd0;
                    BUSY <= 1'b0;
                    DONE <= 1'b1;
                end
            endcase
        end
    end
endmodule
"""
    return ""


def verilog_for(design_name: str) -> str:
    style = "dataflow"
    mux_spec = _mux_spec(design_name)
    if mux_spec:
        return _mux_tree_verilog(design_name, style) if mux_spec[1] else _mux_direct_verilog(design_name, style)
    if design_name.startswith("shift_register_") and "bit" in design_name:
        return _shift_register_family_verilog(design_name, style)
    if design_name in {"uart_baud_rate_generator", "uart_rx_8n1", "spi_slave_8bit", "i2c_slave_simple", "axi_lite_slave_simple"}:
        return _protocol_family_verilog(design_name, style)
    if style == "behavioral":
        return _behavioral_verilog(design_name)
    if style == "gate_level":
        return _gate_level_verilog(design_name)
    if style == "structural":
        return _structural_verilog(design_name)
    return verilog_for_dataflow_legacy(design_name)
def verilog_for(design_name: str, modeling_style: str = "dataflow") -> str:
    design_key = design_name.lower().strip()
    style = (modeling_style or "dataflow").lower().strip()
    if design_key in {"uart_baud_rate_generator", "uart_tx_8n1", "spi_master_8bit", "i2c_master_simple", "uart_rx_8n1", "spi_slave_8bit", "i2c_slave_simple", "axi_lite_slave_simple"}:
        return _protocol_family_verilog(design_key, style)

    mux_spec = _mux_spec(design_key)
    if mux_spec:
        return _mux_tree_verilog(design_key, style) if mux_spec[1] else _mux_direct_verilog(design_key, style)
    if design_key.startswith("shift_register_") and "bit" in design_key:
        return _shift_register_family_verilog(design_key, style)
    if _is_mux_tree(design_key):
        return _mux_tree_verilog(design_key, style)
    if design_key.startswith("counter_") or design_key in {"counter_4bit", "counter_3bit_tff", "counter_3bit_jkff", "counter_3bit_srff"}:
        return _counter_family_verilog(design_key, style)

    if style == "behavioral":
        return _behavioral_verilog(design_name)
    if style == "gate_level":
        return _gate_level_verilog(design_name)
    if style == "structural":
        return _structural_verilog(design_name)
    return verilog_for_dataflow_legacy(design_name)
def render_verilog_for_request(design_name: str, modeling_style: str = "dataflow") -> str:
    design_key = design_name.lower().strip()
    style = (modeling_style or "dataflow").lower().strip()
    if design_key in {"uart_baud_rate_generator", "uart_tx_8n1", "spi_master_8bit", "i2c_master_simple", "uart_rx_8n1", "spi_slave_8bit", "i2c_slave_simple", "axi_lite_slave_simple"}:
        return _protocol_family_verilog(design_key, style)

    mux_spec = _mux_spec(design_key)
    if mux_spec:
        return _mux_tree_verilog(design_key, style) if mux_spec[1] else _mux_direct_verilog(design_key, style)
    if design_key.startswith("shift_register_") and "bit" in design_key:
        return _shift_register_family_verilog(design_key, style)
    if _is_mux_tree(design_key):
        return _mux_tree_verilog(design_key, style)
    if design_key.startswith("counter_") or design_key in {"counter_4bit", "counter_3bit_tff", "counter_3bit_jkff", "counter_3bit_srff"}:
        return _counter_family_verilog(design_key, style)

    if style == "behavioral":
        return _behavioral_verilog(design_name)
    if style == "gate_level":
        return _gate_level_verilog(design_name)
    if style == "structural":
        return _structural_verilog(design_name)
    return verilog_for_dataflow_legacy(design_name)
