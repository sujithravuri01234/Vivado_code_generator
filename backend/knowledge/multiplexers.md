# Multiplexers

Multiplexers select one of many data inputs based on select lines.

2:1 mux:

```verilog
assign y = sel ? d1 : d0;
```

4:1 mux:

- Use two select bits: `sel1` and `sel0`
- Map `00 -> d0`, `01 -> d1`, `10 -> d2`, `11 -> d3`

Canonical boolean form:

```text
y = (~sel1 & ~sel0 & d0) | (~sel1 & sel0 & d1) | (sel1 & ~sel0 & d2) | (sel1 & sel0 & d3)
```

Large multiplexers should be represented at gate level rather than transistor level.

