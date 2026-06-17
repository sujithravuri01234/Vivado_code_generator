import json
import urllib.request
import re
from typing import Tuple

from app.core.settings import settings

class LLMGenerator:
    def __init__(self):
        self.api_key = settings.grok_api_key
        self.url = "https://api.groq.com/openai/v1/chat/completions"

    def generate_verilog_with_llm(self, prompt: str, design_name: str, previous_error: str) -> Tuple[str, str]:
        if not self.api_key:
            print("Warning: GROK_API_KEY not set. Cannot use LLM fallback.")
            return "", ""

        system_prompt = (
            "You are an expert Senior FPGA Engineer. Your task is to generate highly accurate, synthesizable Verilog code and a self-checking Testbench.\n\n"
            "Strict Guidelines for State Machines:\n"
            "1. For sequence detectors, verify if it is a Moore or Mealy machine:\n"
            "   - Moore: The output must depend ONLY on the current state (e.g., assign out = (state == STATE_DETECTED)). For an N-bit sequence, a Moore machine requires exactly N+1 states.\n"
            "   - Mealy: The output depends on both the current state and the inputs.\n"
            "2. EVERY state MUST have a unique encoding value. Do NOT reuse, overlap, or duplicate state codes. If a design has K states, you must use at least ceil(log2(K)) bits for the state registers (e.g., 5 states require a 3-bit register: `reg [2:0] state, next_state;` with 5 distinct parameters from 3'b000 to 3'b100). Double-check that all state parameters have different binary values.\n"
            "3. For sequence detectors (especially overlapping ones), trace the transitions carefully: if a partial match fails, the next state must go to the longest matching prefix of the sequence. If NO prefix of the sequence matches (e.g., sequence is '100' or '0'), the next state MUST transition to IDLE (do NOT stay in a non-matching state).\n"
            "   - Example: In a '1011' overlapping detector, if you are in the state representing '101' and receive a '0' (making the sequence '1010'), the last two bits '10' match the prefix, so the transition MUST go to the state representing '10'. However, if you are in the state representing '10' and receive a '0' (making '100'), none of the prefix matches, so you MUST transition to IDLE.\n"
            "   - Example: From the match state ('1011'), receiving a '0' (making '10110') must transition to the '10' state, and receiving a '1' (making '10111') must transition to the '1' state.\n"
            "4. Use standard two-always-block or three-always-block coding styles for FSMs (one sequential block for state transitions, one combinational block for next-state logic using blocking assignments `=`, and combinational assignment or block for output).\n"
            "5. Ensure active-low or active-high resets are implemented exactly as requested (e.g., asynchronous active-low reset should be `always @(posedge clk or negedge reset_n)` and check `if (!reset_n)`).\n\n"
            "Strict Guidelines for Processors / CPUs (e.g., RISC-V or custom cores):\n"
            "1. Must implement a real Register File (e.g., array of registers `reg [31:0] rf [0:31]`). Read/write values from/to the register file using decoded instruction register indices (e.g., `rf[rs1]`), do NOT perform operations on the raw register index variables directly.\n"
            "2. Ensure instruction opcodes match standard specifications. For RISC-V (RV32I):\n"
            "   - R-type opcode is 7'b0110011\n"
            "   - I-type ALU opcode is 7'b0010011\n"
            "   - Load opcode is 7'b0000011\n"
            "   - Store opcode is 7'b0100011\n"
            "   - Branch opcode is 7'b1100011\n"
            "3. Implement Program Counter (PC) logic and instruction fetch logic correctly. The PC must increment appropriately (e.g., by 4 on each clock cycle unless branching) and index an actual instruction memory array.\n"
            "   - **STRICT RULE ON MULTI-DRIVEN REGISTERS**: Do NOT assign to the same register (e.g., `pc`) from multiple different `always` blocks. Instead, compute a combinational `next_pc` value and update the PC register in a single sequential `always` block. Follow this structural template:\n"
            "     ```verilog\n"
            "     reg [31:0] pc_reg;\n"
            "     reg [31:0] next_pc;\n"
            "     always @(*) begin\n"
            "         if (branch_taken)\n"
            "             next_pc = pc_reg + branch_offset;\n"
            "         else\n"
            "             next_pc = pc_reg + 32'd4;\n"
            "     end\n"
            "     always @(posedge clk or negedge reset_n) begin\n"
            "         if (!reset_n)\n"
            "             pc_reg <= 32'd0;\n"
            "         else\n"
            "             pc_reg <= next_pc;\n"
            "     end\n"
            "     ```\n"
            "4. For pipelined processors, correctly declare pipeline register stages (e.g., IF/ID, ID/EX, EX/MEM, MEM/WB registers) and transfer signals sequentially on clock edges to avoid combinational loops.\n"
            "5. If any output port or internal signal is assigned inside an `always` block, it MUST be declared as a `reg` (e.g., `output reg [31:0] pc`).\n"
            "6. In CPU designs (like RISC-V), register 0 (`x0`) must be hardwired to 0. Reads must return 0, and writes to `x0` must be ignored (e.g., `if (rd != 5'd0) rf[rd] <= data;`).\n\n"
            "Formatting:\n"
            "- Output the synthesizable Verilog design code inside the first ```verilog ... ``` block.\n"
            "  - BEFORE the module definition, write a detailed Verilog comment block containing:\n"
            "    1. The list of states and what sequence they represent.\n"
            "    2. A transition table trace: for each state, show the sequence represented, the next bit, the resulting sequence, the longest matching prefix, and the resulting next state.\n"
            "- Output the Testbench code inside the second ```verilog ... ``` block.\n"
            "- Do not write any conversational text outside the code blocks."
        )

        user_prompt = f"Design a circuit for the following prompt: {prompt}\nDesign Name: {design_name}\n"
        if previous_error:
            user_prompt += f"\nThe previous attempt failed with this Vivado error:\n{previous_error}\nPlease fix the syntax or logic errors."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2
        }

        try:
            req = urllib.request.Request(self.url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=60.0) as response:
                data = json.loads(response.read().decode('utf-8'))
                content = data["choices"][0]["message"]["content"]

                # Extract verilog and testbench
                code_blocks = re.findall(r"```(?:verilog)?\n(.*?)\n```", content, re.DOTALL)
                
                verilog = ""
                testbench = ""
                if len(code_blocks) >= 2:
                    verilog = code_blocks[0].strip()
                    testbench = code_blocks[1].strip()
                elif len(code_blocks) == 1:
                    # Heuristic: if it contains $monitor or $dumpfile it's probably testbench
                    if "$monitor" in code_blocks[0] or "$dumpfile" in code_blocks[0]:
                        testbench = code_blocks[0].strip()
                    else:
                        verilog = code_blocks[0].strip()
                
                return verilog, testbench
        except Exception as e:
            print(f"LLM Generation failed: {e}")
            return "", ""
