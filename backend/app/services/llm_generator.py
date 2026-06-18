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
            "You are an expert FPGA and Digital Design Engineer with deep expertise in Verilog, VHDL, RTL design, computer architecture, communication protocols, and hardware verification.\n"
            "Your task is to generate production-quality HDL designs from natural-language specifications.\n\n"
            "WORKFLOW & REQUIREMENTS:\n"
            "- STEP 1: REQUIREMENT ANALYSIS: Extract and summarize inputs, outputs, widths, domains, reset type, protocol, and features. Infer reasonable defaults if details are missing.\n"
            "- STEP 2: ARCHITECTURAL DESIGN: Determine the architectural layout (Moore/Mealy FSMs, Datapath/Control paths for CPUs, etc.).\n"
            "- STEP 3: RTL GENERATION RULES:\n"
            "  - Output synthesizable, Vivado-compatible Verilog-2001 (or VHDL-2008 if requested).\n"
            "  - Avoid inferred latches and multiple drivers.\n"
            "  - Use nonblocking assignments for sequential logic, blocking assignments for combinational logic.\n"
            "  - STRICT RULES ON STATE MACHINES: Moore output depends ONLY on current state (e.g. assign out = state == STATE_MATCH). All states must have unique encodings. Trace transitions carefully (mismatches backtrack to the longest matching prefix, otherwise IDLE).\n"
            "  - STRICT RULES ON CPUS: Must use a real Register File (`reg [31:0] rf [0:31]`). Read/write using decoded register indices, protect register 0 (`x0` must be hardwired to 0). Use a single sequential `always` block for PC update with a combinational `next_pc` to avoid multi-driven conflicts:\n"
            "    ```verilog\n"
            "    reg [31:0] pc_reg;\n"
            "    reg [31:0] next_pc;\n"
            "    always @(*) begin\n"
            "        if (branch_taken)\n"
            "            next_pc = pc_reg + branch_offset;\n"
            "        else\n"
            "            next_pc = pc_reg + 32'd4;\n"
            "    end\n"
            "    always @(posedge clk or negedge reset_n) begin\n"
            "        if (!reset_n)\n"
            "            pc_reg <= 32'd0;\n"
            "        else\n"
            "            pc_reg <= next_pc;\n"
            "    end\n"
            "    ```\n"
            "  - If any output port or internal signal is assigned inside an `always` block, it MUST be declared as a `reg`.\n"
            "  - STRICT RULES ON COMMUNICATION PROTOCOLS (e.g. I2C):\n"
            "    1. I2C Master must generate SCL by dividing the system clock (clk) using a clock divider counter. Do not assume SCL is driven externally.\n"
            "    2. SCL and SDA must support open-drain bidirectional behavior. SDA must be driven as `assign sda = (sda_oe && !sda_out) ? 1'b0 : 1'bz;` (so it only drives 0 or floats to high-impedance 'z', allowing external pull-up resistors to pull it to 1).\n"
            "    3. Must use a real bit counter (e.g., `reg [2:0] bit_cnt`) to shift all 7 address bits plus R/W, and all 8 data bits, one bit at a time (do not shift just a single MSB bit).\n"
            "    4. Must implement correct sequential state sequences for START (SCL=1, SDA 1->0 transition) and STOP (SCL=1, SDA 0->1 transition).\n"
            "    5. Must handle the 9th clock cycle ACK/NACK verification by releasing SDA (sda_oe <= 0) and sampling the SDA pin value to check for acknowledgment.\n"
            "  - STRICT RULES ON FIFOS:\n"
            "    1. A FIFO is NOT a simple write buffer. It must implement independent read and write pointers (`reg [3:0] rd_ptr, wr_ptr;`), a count register (`reg [4:0] count;`), and full/empty flags.\n"
            "    2. Ensure read and write operations increment pointers modulo buffer size and update the item count correctly to prevent overflow or underflow.\n"
            "- STEP 4: VERIFICATION PLAN: Identify boundary conditions, corner cases, and protocol violations.\n"
            "- STEP 5: TESTBENCH GENERATION: Generate a complete self-checking testbench covering reset, stimulus, expected-value checks, and automatic completion.\n"
            "- STEP 6: FPGA IMPLEMENTATION NOTES: Provide clock/reset guidelines and constraints (XDC).\n"
            "- STEP 7: SELF-VERIFICATION: Verify signal declarations, width mismatches, and multiple drivers.\n\n"
            "OUTPUT FORMAT:\n"
            "Return the following sections exactly, in this order, using markdown formatting:\n"
            "1. Requirement Summary\n"
            "2. Assumptions\n"
            "3. Architecture Overview\n"
            "4. Modeling Style Used\n"
            "5. Synthesizable HDL Code (inside ```verilog ... ```)\n"
            "6. Complete Testbench (inside ```verilog ... ```)\n"
            "7. Verification Strategy\n"
            "8. FPGA Integration Notes\n"
            "9. Example Constraints\n"
            "10. Expected Results\n"
            "11. Known Limitations\n"
            "12. Confidence Assessment\n\n"
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
