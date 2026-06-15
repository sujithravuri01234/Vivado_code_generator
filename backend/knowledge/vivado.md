# Vivado Validation

Vivado validation flow:

1. Write generated Verilog to a temporary file
2. Run `synth_design`
3. Generate timing, utilization, and power reports
4. Export synthesized netlist
5. Use the verified netlist for downstream diagram generation

When Vivado is unavailable, return a structured failure report instead of crashing.

