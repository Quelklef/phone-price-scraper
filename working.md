

- Repeatedly do the following until there is no more to do:

  - Find something that can be simplified, and make it simpler
  - Find something that should be factored out, and do so
  - Find something that should be made more readable/clear, and do so
  - Find something that deserves a comment, and give it one
  - Find something that can be optimized without architectural changes, and do it




### Notes on equality/hashing

Option A (current)

Two notions of equality: `==` (structural) and `is` (identity).

Hashable types are required to keep `hash()` coherent with `==` by ensuring that if `a == b` then `hash(a) == hash(b)`.

Consequence: mutable datatypes cannot be hashable:
  (a) If you hash by contents, then a value's hash could change over time, which breaks `dict`/`set` internals
  (b) If you hash by identity, then the hash law can be violated

~~~
Option B (alternative)

Add a new operator `~~` which checks Leibniz-style equality. Operationally, `~~` is implemented by acting like `==` on immutable types and `is` on mutable types. Conceptually, two values are `~~` if they are indistinguishable by normal value algebra operations (ie, not stuff like `id()`).

Make this the standard go-to equality check, with `==` and `is` reserved for when you specifically want to project down to structural/identity comparison.

The point of this is larger than adding a new operator; it's to shift the conceptualization of mutable values. One should think of a mutable value as a reference to data, and an immutable value as data proper. The data of a mutable value is the reference itself (eg, numeric memory location), rather than the data referenced. In this model, `~~` is simply the canonical correct equality operator,

Change the hash law to use `~~`: if `a ~~ b` then `hash(a) ~~ hash(b)`

Consequence: mutable datatypes become hashable (identity semantics)

~~~
Comparison table

Mutable values as container keys:
- Option A: disallowed unless converted to an immutable value first, which gives structural key semantics.
- Option B: allowed directly with identity semantics, or convertible to immutable first for structural key semantics.

Hashability of mutable values:
- Option A: mutable values cannot be hashed
- Option B: mutable values can be hashed (identity/reference semantics)

Hash coherence:
- Option A: hash coherence with `==` (structural equality)
- Option B: hash coherence with `~~` (Leibniz equality)

Conceptual surface area:
- Option A: two equality operators (`==`, `is`).
- Option B: three equality operators (`~~`, `==`, `is`)

