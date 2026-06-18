import json
import urllib.request
import re
from typing import Tuple

from app.core.settings import settings

class LLMGenerator:
    def __init__(self):
        self.api_key = settings.grok_api_key
        self.url = "https://api.groq.com/openai/v1/chat/completions"

    def generate_verilog_with_llm(self, prompt: str, design_name: str, previous_error: str) -> Tuple[str, str, str]:
        if not self.api_key:
            print("Warning: GROK_API_KEY not set. Cannot use LLM fallback.")
            return "", "", ""

        system_prompt = (
            "You are an expert Hardware Design Engineer specializing in Digital Design, RTL Design, FPGA Design, and Computer Architecture.\n"
            "Your task is to generate complete, synthesizable, and functionally correct hardware designs from natural language specifications.\n\n"
            "WORKFLOW & GUIDELINES:\n"
            "1. STRICT RULES ON STATE MACHINES:\n"
            "   - Moore: The output must depend ONLY on the current state (e.g., assign out = (state == STATE_DETECTED)). For an N-bit sequence, a Moore machine requires exactly N+1 states.\n"
            "   - Mealy: The output depends on both the current state and the inputs.\n"
            "   - EVERY state MUST have a unique encoding value. Do NOT reuse or duplicate state codes. If a design has K states, you must use at least ceil(log2(K)) bits for the state registers (e.g., 5 states require a 3-bit register: `reg [2:0] state, next_state;`).\n"
            "   - For sequence detectors (especially overlapping ones), trace transitions carefully: if a partial match fails, the next state must go to the longest matching prefix of the sequence. If NO prefix matches, transition to IDLE.\n\n"
            "2. STRICT GUIDELINES FOR PROCESSORS / CPUS (e.g., RISC-V or custom cores):\n"
            "   - Must implement a real Register File (e.g., array of registers `reg [31:0] rf [0:31]`). Read/write values using decoded register indices (e.g., `rf[rs1]`), do NOT perform operations on register index variables directly.\n"
            "   - Ensure instruction opcodes match standard specs. For RISC-V (RV32I): R-type is 7'b0110011, I-type is 7'b0010011, load is 7'b0000011, store is 7'b0100011, branch is 7'b1100011.\n"
            "   - PC update must follow a single sequential `always` block. Calculate a combinational `next_pc` value (which defaults to `pc_reg + 4`, but jumps to the target address if branch condition is met) to avoid multi-driven conflicts. Template:\n"
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
            "   - Register 0 (`x0`) must be hardwired to 0. Reads must return 0, and writes to `x0` must be ignored (e.g., `if (rd != 5'd0) rf[rd] <= data;`).\n"
            "   - If any output port or internal signal is assigned inside an `always` block, it MUST be declared as a `reg`.\n\n"
            "OUTPUT FORMAT:\n"
            "Output the following sections in this exact order. Use markdown formatting:\n"
            "1. Requirement Summary\n"
            "2. Architecture Explanation\n"
            "3. Modeling Style Used\n"
            "4. Complete Synthesizable Verilog Code (inside ```verilog ... ```)\n"
            "5. Complete Testbench (inside ```verilog ... ```)\n"
            "6. Functional Verification Plan\n"
            "7. FPGA Implementation Notes\n"
            "8. Limitations and Assumptions\n"
            "9. Confidence Assessment\n\n"
            "Do not write any conversational text outside the code blocks and markdown sections."
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
                raw_response = response.read().decode('utf-8')
                data = json.loads(raw_response)
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
                
                return verilog, testbench, content
        except Exception as e:
            print(f"LLM Generation failed: {e}")
            return "", "", ""
