"""
Electrical check of the generated schematic (KiCad 7's command line has no
ERC, so we do the important part ourselves):

1. Export the netlist from the real .kicad_sch files with kicad-cli.
2. Every net in the netlist must contain exactly the pins design.py says.
3. No net may have only one pin (a wire to nowhere).
4. Every power-input pin must sit on a net that has a power source.
"""
import subprocess, sys, os, collections
sys.path.insert(0, os.path.dirname(__file__))
import sexp, design

HW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
out = "/tmp/pedal_check.net"
subprocess.run(["kicad-cli", "sch", "export", "netlist", "-o", out, os.path.join(HW, "pedal.kicad_sch")],
               check=True, capture_output=True)
nl = sexp.parse(open(out).read())
nets = sexp.find(nl, "nets")
got = {}
pintypes = {}
for n in sexp.findall(nets, "net"):
    name = sexp.find(n, "name")[1].lstrip("/")
    nodes = set()
    for nd in sexp.findall(n, "node"):
        ref = sexp.find(nd, "ref")[1]; pin = sexp.find(nd, "pin")[1]
        pt = sexp.find(nd, "pintype")
        nodes.add((ref, pin))
        pintypes[(ref, pin)] = pt[1] if pt else "?"
    got[name] = nodes

want = collections.defaultdict(set)
flagged = set()
for p in design.parts:
    ref = p["ref"]
    if p["lib"].startswith("power:"):
        flagged.update(n for n in p["pins"].values())   # PWR_FLAG = "a supply is connected here"
        continue
    for pin, net in p["pins"].items():
        if net: want[net].add((ref, pin))

errors = 0
for net, nodes in want.items():
    g = got.get(net)
    if g is None:
        print("MISSING net", net); errors += 1; continue
    if g != nodes:
        print("MISMATCH", net, "extra:", g - nodes, "missing:", nodes - g); errors += 1
for net, nodes in got.items():
    if net.startswith("unconnected"):
        continue
    if net not in want:
        print("UNEXPECTED net", net, nodes); errors += 1
    real = [n for n in nodes if not n[0].startswith("#FLG")]
    if len(real) < 2:
        print("SINGLE-PIN net", net, nodes); errors += 1
    types = [pintypes[n] for n in nodes]
    if any(t.startswith("power_in") for t in types) and not any(t.startswith("power_out") for t in types) and net not in flagged:
        print("UNDRIVEN power net", net, types); errors += 1

print("nets checked: %d, pins: %d, errors: %d" % (len(want), sum(len(v) for v in want.values()), errors))
sys.exit(1 if errors else 0)
