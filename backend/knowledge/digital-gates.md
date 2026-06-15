# Digital Gates

Supported simple gates in this project:

- NOT
- BUFFER
- NAND
- NOR
- AND
- OR
- XOR
- XNOR

For transistor-level CMOS generation:

- NAND uses parallel PMOS and series NMOS
- NOR uses series PMOS and parallel NMOS
- AND can be formed from NAND followed by inverter
- OR can be formed from NOR followed by inverter

For synthesizable Verilog:

- Prefer continuous assignments for simple combinational gates
- Keep module ports explicit and stable

