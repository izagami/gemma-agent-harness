# buildorder

`python3 -m buildorder DEPSFILE [TARGET ...]` prints the build order, one name per line.

## Dependency file

* One rule per line: `target: dep dep ...` (deps separated by spaces; a rule may have no deps: `target:`).
* `#` starts a comment; blank lines are ignored.
* A target may appear on several lines: its deps are merged. A dep listed more than once counts once.
* Every name that appears (as a target or a dep) is a node.

## Order

Kahn's algorithm: a node can be built once all its deps are built. Whenever more than one node can be
built, the alphabetically smallest one (plain string order) is built first. So the order is unique.

    app: lib util        ->   base
    lib: base                 lib
    util: base                util
                              app

With TARGETs, only those targets and everything they need (directly or indirectly) are printed,
in the same order rule. An unknown target: `error: unknown target NAME` on stderr, exit 1.

## Cycles

If some nodes can never be built, nothing is printed to stdout; stderr gets one line and the exit code is 2:

    error: cycle: b -> c -> d -> b

The cycle shown is found like this: let R be the nodes that could not be built. Start at the smallest
node of R and repeatedly move to its smallest dep that is in R, until a node repeats. The printed cycle
starts at the first repeated node and ends with it again. Example: R = {a, b, c, d}, a needs b,
b needs c, c needs d, d needs b → walk a, b, c, d, b → `error: cycle: b -> c -> d -> b`.
A node that depends on itself: `error: cycle: x -> x`.
