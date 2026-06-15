# Adders

Half adder:

- Sum = `a ^ b`
- Carry = `a & b`

Full adder:

- Sum = `a ^ b ^ cin`
- Carry = `(a & b) | (cin & (a ^ b))`

Ripple carry adders chain full adders from LSB to MSB.

Truth tables should be reduced when the design has many inputs.

