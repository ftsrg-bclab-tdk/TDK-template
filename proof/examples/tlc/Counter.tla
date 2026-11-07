---- MODULE Counter ----
EXTENDS Naturals
CONSTANT Limit
VARIABLE value

Init == value = 0
Next == \/ /\ value < Limit
           /\ value' = value + 1
        \/ /\ value = Limit
           /\ UNCHANGED value

WithinBounds == value \in 0..Limit
====
