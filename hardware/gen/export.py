"""
Make everything the factory needs, plus pictures for the docs.

  python3 export.py

  ../fab/pedal-gerbers.zip      upload this to JLCPCB (or PCBWay)
  ../fab/bom_jlc.csv            parts the factory solders (bottom side)
  ../fab/cpl_jlc.csv            where each of those parts goes (pick and place)
  ../fab/hand_parts.csv         parts YOU buy and solder / wire
  ../fab/pcb_top.png, pcb_bottom.png, ../fab/schematic.pdf
"""
import csv, os, re, shutil, subprocess, sys, zipfile, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.normpath(os.path.join(HERE, ".."))
FAB = os.path.join(HW, "fab")
PCB = os.path.join(HW, "pedal.kicad_pcb")
SCH = os.path.join(HW, "pedal.kicad_sch")

def run(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout, r.stderr); sys.exit(1)
    return r.stdout

def gerbers():
    out = os.path.join(FAB, "gerbers")
    shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
    layers = "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"
    run("kicad-cli", "pcb", "export", "gerbers", "--layers", layers, "--subtract-soldermask",
        "-o", out + "/", PCB)
    run("kicad-cli", "pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm",
        "--excellon-separate-th", "-o", out + "/", PCB)
    z = os.path.join(FAB, "pedal-gerbers.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as f:
        for n in sorted(os.listdir(out)):
            f.write(os.path.join(out, n), n)
    print("gerbers:", ", ".join(sorted(os.listdir(out))))
    return z

# --------------------------------------------------------------------- BOM
def short_fp(fp):
    n = fp.split(":")[-1]
    for k, v in (("R_0805", "0805"), ("C_0805", "0805"), ("L_0805", "0805"), ("C_1206", "1206"),
                 ("CP_Elec_6.3x7.7", "SMD electrolytic 6.3x7.7mm"), ("CP_Elec_6.3x5.4", "SMD electrolytic 6.3x5.4mm"),
                 ("D_SMA", "SMA (DO-214AC)"), ("TO-252-2", "TO-252 (DPAK)"), ("SOT-23-5", "SOT-23-5"),
                 ("SOIC-8", "SOIC-8"), ("TSSOP-14", "TSSOP-14"), ("TSSOP-20", "TSSOP-20")):
        if n.startswith(k):
            return v
    return n

def cap_comment(p):
    v = p["value"]
    nets = set(p["pins"].values())
    if v.endswith("pF") or v == "2.2nF":         # audio filter caps: C0G keeps them exact
        return "%s 50V C0G/NP0" % v
    if "25V" in v:
        return v + " electrolytic"
    volts = "25V" if nets & {"+9V", "+9V_IN", "IN_TIP"} else "16V"
    if v in ("100nF",):
        volts = "50V"
    return "%s %s X7R/X5R" % (v, volts)

def comment(p):
    r = p["ref"]
    if r.startswith("C"):
        return cap_comment(p)
    if r.startswith("R"):
        return "%s 1%% 1/8W" % p["value"]
    if r.startswith("FB"):
        return "Ferrite bead 600R@100MHz"
    return p["value"]

def assembled(p):
    return p["fp"] and p["ref"] not in design.HAND_SOLDER and not p["ref"].startswith(("TP", "PF"))

def bom():
    groups = collections.OrderedDict()
    for p in design.parts:
        if not assembled(p):
            continue
        key = (comment(p), short_fp(p["fp"]), p["mpn"] if not p["ref"][0] in "RC" else "")
        groups.setdefault(key, []).append(p["ref"])
    path = os.path.join(FAB, "bom_jlc.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #", "Manufacturer Part", "Qty"])
        def k(item):
            refs = item[1]
            m = re.match(r"([A-Z]+)(\d+)", refs[0])
            return (m.group(1), int(m.group(2)))
        for (c, fp, mpn), refs in sorted(groups.items(), key=k):
            w.writerow([c, ",".join(refs), fp, "", mpn, len(refs)])
    print("bom: %d lines, %d parts" % (len(groups), sum(len(v) for v in groups.values())))
    return path

def cpl():
    tmp = os.path.join(FAB, "pos_kicad.csv")
    run("kicad-cli", "pcb", "export", "pos", "--side", "back", "--format", "csv", "--units", "mm",
        "--smd-only", "-o", tmp, PCB)
    keep = {p["ref"] for p in design.parts if assembled(p)}
    rows = list(csv.DictReader(open(tmp)))
    path = os.path.join(FAB, "cpl_jlc.csv")
    n = 0
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for r in rows:
            if r["Ref"] in keep:
                w.writerow([r["Ref"], "%smm" % r["PosX"], "%smm" % r["PosY"], "Bottom", r["Rot"]])
                n += 1
    os.remove(tmp)
    missing = keep - {r["Ref"] for r in rows}
    if missing:
        print("WARNING: no position for", sorted(missing))
    print("cpl: %d parts on the bottom side" % n)
    return path

HAND = [
    # what, qty, details, where it goes
    ("WeAct Black Pill V3.0, STM32F411CEU6", 1, "Must say F411 (not F401) and have the 25 MHz crystal. Comes with 2x 20-pin male headers.", "U6 (plugs into the sockets)"),
    ("Female pin header 1x20, 2.54 mm", 2, "Straight, through-hole. These are the Black Pill's sockets.", "U6 footprint, bottom side"),
    ("Potentiometer 9 mm, B10K (linear), PCB mount, M7 bushing, ~15 mm shaft", 6, "Alpha 9 mm vertical (RD901F-40 family) or equivalent. Snap off the small anti-rotation tab.", "RV1-RV6, top side"),
    ("Knobs for 6 mm shafts", 6, "Match your pots' shaft type (knurled or D).", "on the pots"),
    ("LED 3 mm diffused: red, yellow, green", 3, "One of each colour (any colour works).", "D3 red, D4 yellow, D5 green, top side"),
    ("Momentary footswitch, SPST, normally open ('soft-touch')", 3, "NOT the latching/clicky 3PDT kind. 12 mm thread.", "wired to J6"),
    ("6.35 mm (1/4\") mono jack, panel mount", 2, "Cliff/Lumberg or Switchcraft style.", "input -> J2, output -> J3"),
    ("2.1 mm DC jack, panel mount, centre-negative pedal type", 1, "", "wired to J1"),
    ("Male pin header 1x3, 2.54 mm", 1, "", "J5 (debug serial)"),
    ("Hook-up wire, 24 AWG stranded, 2-3 colours", 1, "About 2 m in total. Solder it straight into J1, J2, J3 and J6 (no pin headers there).", "jacks and switches"),
    ("Enclosure Hammond 1590XX (145 x 121 x 39 mm) or similar", 1, "Aluminium. The drill template is drawn for this size.", "the box"),
    ("9 V DC pedal power supply, centre-negative, >= 300 mA", 1, "The normal guitar-pedal adapter.", "power"),
    ("USB-C cable", 1, "For flashing the firmware.", "Black Pill"),
    ("USB-serial adapter, 3.3 V (CP2102 or CH340)", 1, "Optional: only to read the debug messages.", "J5"),
]

def hand_parts():
    path = os.path.join(FAB, "hand_parts.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Part", "Qty", "Notes", "Goes to"])
        for row in HAND:
            w.writerow(row)
    return path

# --------------------------------------------------------------------- pictures
def pictures():
    tmp = os.path.join(FAB, "tmp.svg")
    for name, layers, extra in (("pcb_top", "F.Cu,F.SilkS,F.Mask,Edge.Cuts", []),
                                ("pcb_bottom", "B.Cu,B.SilkS,B.Mask,Edge.Cuts", ["--mirror"])):
        run("kicad-cli", "pcb", "export", "svg", "--layers", layers, "--page-size-mode", "2",
            "--exclude-drawing-sheet", *extra, "-o", tmp, PCB)
        run("rsvg-convert", "-w", "1600", "-b", "white", tmp, "-o", os.path.join(FAB, name + ".png"))
    os.remove(tmp)
    run("kicad-cli", "sch", "export", "pdf", "-o", os.path.join(FAB, "schematic.pdf"), SCH)
    print("pictures: pcb_top.png, pcb_bottom.png, schematic.pdf")

if __name__ == "__main__":
    os.makedirs(FAB, exist_ok=True)
    gerbers(); bom(); cpl(); hand_parts(); pictures()
