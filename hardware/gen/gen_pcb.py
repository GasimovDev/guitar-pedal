"""
Generate the PCB (KiCad 7) from design.py: place footprints, assign nets,
board outline, ground pours, silkscreen. Routing is done afterwards by
route.py (Freerouting).

Board: 85 x 76 mm, 2 layers, for a Hammond 1590XX enclosure.
TOP side  (faces the box face, under the knobs): the 6 pots and 3 LEDs only.
BOTTOM side: everything else, all SMD parts assembled by the factory, plus
the Black Pill sockets and wire headers which you solder by hand.
Coordinates: mm, origin = top-left corner of the board seen from the TOP.
"""
import os, sys, json, math
import pcbnew
sys.path.insert(0, os.path.dirname(__file__))
import design

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.join(HERE, "..")
FPDIR = "/usr/share/kicad/footprints"
mm = pcbnew.FromMM
BW, BH = 85.0, 76.0

# ---------------------------------------------------------------- fixed placements
# (x, y, rotation, side). Pots/LEDs: x,y = SHAFT / LED centre.
POT_SHAFT = {"RV1": (14.0, 13.0), "RV2": (14.0, 36.0),      # overdrive column
             "RV3": (42.5, 13.0), "RV4": (42.5, 36.0),      # tremolo column
             "RV5": (71.0, 13.0), "RV6": (71.0, 36.0)}      # delay column
LED_POS = {"D3": (14.0, 50.0), "D4": (42.5, 50.0), "D5": (71.0, 50.0)}

FIXED = {
    "U6": (82.0, 56.0, 0, "B"),       # Black Pill: pad 21 (PB12) here, USB-C points right
    "J1": (41.23, 2.2, 90, "B"),      # 9 V header at the top edge (DC jack on the top wall)
    "J2": (82.6, 21.5, 0, "B"),       # input header at the right edge (input jack on the right wall)
    "J3": (2.4, 21.5, 0, "B"),        # output header at the left edge
    "J6": (2.4, 57.0, 0, "B"),        # footswitch header, bottom-left
    "J5": (27.6, 63.0, 0, "B"),       # UART header, next to the Black Pill
    "U1": (58.0, 4.2, 0, "B"),        # 5 V regulator
    "C1": (25.0, 4.2, 0, "B"),        # 100 uF bulk
    "U3": (48.5, 24.5, 0, "B"),       # op-amp, between input and output stages
    "U4": (63.0, 46.0, 90, "B"),      # ADC
    "U5": (32.0, 46.0, 90, "B"),      # DAC
    "U2": (48.0, 45.0, 0, "B"),       # 3.3 V regulator between the converters
    "C8": (37.0, 24.5, 0, "B"),       # VBIAS reservoir
}
# test points: next to what they measure
TP_POS = {"TP1": (31.0, 2.0), "TP2": (66.0, 2.5), "TP3": (52.0, 41.5), "TP4": (31.0, 20.0),
          "TP5": (79.5, 2.5), "TP6": (5.0, 44.0), "TP7": (54.5, 51.42), "TP8": (58.5, 51.42),
          "TP9": (62.5, 51.42), "TP10": (66.0, 20.0), "TP11": (22.0, 41.5), "TP12": (24.0, 30.0)}

# small parts: placed as close as possible to an anchor ("REF.PAD" or (x, y))
ANCHOR = {
    "D1": "J1.1", "C2": "C1.1", "C3": "U1.1", "C4": "U1.3", "C5": "U1.3",
    "D2": "U6.38", "C6": "U2.1", "C7": "U2.5", "FB1": "U4.3",
    "R1": "C8.1", "R2": "C8.1",
    "R3": "J2.1", "C9": "J2.1", "R4": "U3.3", "C10": "U3.3", "R5": "U3.3",
    "R6": "U3.2", "C11": "U3.2", "R7": "U3.2", "C12": "U3.2", "R8": "U3.1", "C13": "U4.13",
    "C14": "U4.13", "C15": "U4.14",
    "C16": "U4.1", "C17": "U4.1", "C18": "U4.3", "C19": "U4.3", "C20": "U4.4",
    "C21": "U5.2", "C22": "U5.5", "C23": "U5.18", "C24": "U5.8", "C25": "U5.8", "C26": "U5.1",
    "C27": "U5.20", "R9": "U5.17",
    "R10": "U5.6", "C28": "U5.6", "C29": "U5.6", "R11": "U3.5", "R12": "U3.5", "C30": "U3.7",
    "R13": "J3.1", "R14": "J3.1", "C31": "U3.8", "C32": "U3.8",
    "R15": "U6.12", "R16": "U6.22", "R17": "U6.21", "R18": "U6.24",
    "R19": "U6.14", "R20": "U6.13", "R21": "U6.11", "R22": "U6.10", "R23": "U6.9", "R24": "U6.8",
    "C33": "U6.14", "C34": "U6.13", "C35": "U6.11", "C36": "U6.10", "C37": "U6.9", "C38": "U6.8",
    "R25": "J6.1", "R26": "J6.2", "R27": "J6.3", "C39": "U6.34", "C40": "U6.35", "C41": "U6.36",
    "R28": "U6.7", "R29": "U6.6", "R30": "U6.4",
}

def fp_load(fpid):
    lib, name = fpid.split(":")
    path = os.path.join(HW, "pedal.pretty") if lib == "pedal" else os.path.join(FPDIR, lib + ".pretty")
    f = pcbnew.FootprintLoad(path, name)
    if f is None:
        raise RuntimeError("footprint not found: " + fpid)
    f.SetFPID(pcbnew.LIB_ID(lib, name))
    return f

def pad_pos(f, num):
    for p in f.Pads():
        if p.GetNumber() == num:
            v = p.GetPosition()
            return pcbnew.ToMM(v.x), pcbnew.ToMM(v.y)
    raise KeyError(num)

def bbox(f, margin=0.25):
    # courtyard of the footprint's own side if present, else pads+graphics
    lay = pcbnew.F_CrtYd if f.GetLayer() == pcbnew.F_Cu else pcbnew.B_CrtYd
    xs, ys = [], []
    for g in f.GraphicalItems():
        if g.GetLayer() == lay:
            b = g.GetBoundingBox()
            xs += [b.GetLeft(), b.GetRight()]; ys += [b.GetTop(), b.GetBottom()]
    for p in f.Pads():
        b = p.GetBoundingBox()
        xs += [b.GetLeft(), b.GetRight()]; ys += [b.GetTop(), b.GetBottom()]
    T = pcbnew.ToMM
    return (T(min(xs)) - margin, T(min(ys)) - margin, T(max(xs)) + margin, T(max(ys)) + margin)

def overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])

def make_board():
    path = os.path.join(HW, "pedal.kicad_pcb")
    board = pcbnew.NewBoard(path)
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)

    netmap = {}
    for n in design.nets():
        ni = pcbnew.NETINFO_ITEM(board, n)
        board.Add(ni)
        netmap[n] = ni

    paths = json.load(open(os.path.join(HERE, "sym_paths.json")))
    placed_boxes = {"T": [], "B": []}
    fps = {}

    def add(p, x, y, rot, side):
        f = fp_load(p["fp"])
        f.SetReference(p["ref"])
        f.SetValue(p["value"])
        if p["ref"] in paths:
            f.SetPath(pcbnew.KIID_PATH(paths[p["ref"]]))
        for k in ("MPN", "Description"):
            v = p["mpn"] if k == "MPN" else p["desc"]
            if v:
                f.SetProperty(k, v)
        f.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        f.SetOrientationDegrees(rot)
        board.Add(f)
        if side == "B":
            f.Flip(f.GetPosition(), True)
        for pad in f.Pads():
            net = p["pins"].get(pad.GetNumber())
            if net:
                pad.SetNet(netmap[net])
        attrs = f.GetAttributes()
        if p["ref"].startswith("TP"):
            f.SetAttributes(attrs | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM)
        if p["ref"] in design.HAND_SOLDER:
            # factory does not place these; they stay in the BOM for you
            f.SetAttributes(f.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        fps[p["ref"]] = f
        bb = bbox(f)
        th = any(pd.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for pd in f.Pads())
        placed_boxes[side].append((bb, p["ref"]))
        if th:   # through-hole pads block both sides
            for pd in f.Pads():
                b = pd.GetBoundingBox(); T = pcbnew.ToMM
                pb = (T(b.GetLeft()) - 0.3, T(b.GetTop()) - 0.3, T(b.GetRight()) + 0.3, T(b.GetBottom()) + 0.3)
                placed_boxes["B" if side == "T" else "T"].append((pb, p["ref"]))
        return f

    byref = {p["ref"]: p for p in design.parts if p["fp"]}

    # 1. fixed parts
    for ref, (sx, sy) in POT_SHAFT.items():
        add(byref[ref], sx - 7.5, sy - 2.5, 0, "T")
    for ref, (lx, ly) in LED_POS.items():
        add(byref[ref], lx - 1.27, ly, 0, "T")
    for ref, (x, y, r, s) in FIXED.items():
        add(byref[ref], x, y, r, s)
    for ref, (x, y) in TP_POS.items():
        add(byref[ref], x, y, 0, "B")

    # 2. small parts by anchor, spiral search for the closest free spot
    keepout_edge = 0.6
    order = [p["ref"] for p in design.parts if p["fp"] and p["ref"] not in fps]
    for ref in order:
        p = byref[ref]
        a = ANCHOR.get(ref)
        if isinstance(a, str):
            r, n = a.split(".")
            ax, ay = pad_pos(fps[r], n)
        elif a:
            ax, ay = a
        else:
            ax, ay = BW / 2, BH / 2
        best = None
        for rot in (0, 90):
            f = fp_load(p["fp"]); f.SetOrientationDegrees(rot)
            f.SetPosition(pcbnew.VECTOR2I(0, 0))
            t = bbox(f)
            b0 = (-t[2] - 0.2, t[1] - 0.2, -t[0] + 0.2, t[3] + 0.2)    # mirrored = flipped to the bottom; +0.2 mm routing room
            step = 0.5
            for ring in range(0, 80):
                cands = []
                for i in range(-ring, ring + 1):
                    for j in (-ring, ring):
                        cands += [(i, j), (j, i)]
                found = None
                for (i, j) in sorted(set(cands), key=lambda c: c[0] ** 2 + c[1] ** 2):
                    x, y = ax + i * step, ay + j * step
                    bb = (b0[0] + x, b0[1] + y, b0[2] + x, b0[3] + y)
                    if bb[0] < keepout_edge or bb[1] < keepout_edge or bb[2] > BW - keepout_edge or bb[3] > BH - keepout_edge:
                        continue
                    if any(overlap(bb, o) for o, _ in placed_boxes["B"]):
                        continue
                    found = (math.hypot(x - ax, y - ay), x, y, rot)
                    break
                if found:
                    break
            if found and (best is None or found[0] < best[0] - 0.01):
                best = found
        if not best:
            raise RuntimeError("no room for " + ref)
        _, x, y, rot = best
        add(p, x, y, rot, "B")

    # 3. outline
    pts = [(0, 0), (BW, 0), (BW, BH), (0, BH)]
    for i in range(4):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(mm(pts[i][0]), mm(pts[i][1])))
        s.SetEnd(pcbnew.VECTOR2I(mm(pts[(i + 1) % 4][0]), mm(pts[(i + 1) % 4][1])))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1))
        board.Add(s)

    # 4. silkscreen labels
    def text(t, x, y, layer, size=1.2, rot=0, mirror=False):
        tx = pcbnew.PCB_TEXT(board)
        tx.SetText(t); tx.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        tx.SetLayer(layer); tx.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
        tx.SetTextThickness(mm(size * 0.15)); tx.SetTextAngleDegrees(rot)
        if mirror: tx.SetMirrored(True)
        board.Add(tx)
    names = {"RV1": "DRIVE", "RV2": "TONE", "RV3": "RATE", "RV4": "DEPTH", "RV5": "TIME", "RV6": "REPEATS"}
    for ref, (sx, sy) in POT_SHAFT.items():
        text(names[ref], sx, sy + 8.3, pcbnew.F_SilkS, 1.2)
    for (lx, ly), nm in zip(LED_POS.values(), ("OVERDRIVE", "TREMOLO", "DELAY")):
        text(nm, lx, ly + 3.0, pcbnew.F_SilkS, 1.2)
    text("GUITAR PEDAL rev A", 42.5, 72.5, pcbnew.F_SilkS, 1.5)
    text("STM32F411 + PCM1808 + PCM5102A", 42.5, 74.6, pcbnew.F_SilkS, 1.0)
    B = pcbnew.B_SilkS
    text("9V +  GND", 42.5, 5.6, B, 1.0, mirror=True)
    text("IN", 82.6, 19.0, B, 1.2, mirror=True)
    text("TIP GND", 79.6, 22.8, B, 0.8, rot=90, mirror=True)
    text("OUT", 2.4, 19.0, B, 1.2, mirror=True)
    text("FSW OD TREM DLY GND", 5.2, 60.8, B, 0.8, rot=90, mirror=True)
    text("TX RX GND", 25.2, 65.5, B, 0.8, rot=90, mirror=True)
    text("<- USB-C END     BLACK PILL HERE", 57.0, 63.6, B, 1.0, mirror=True)   # reads right from the bottom side
    return board, fps, netmap

def add_zones(board, netmap):
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(netmap["GND"])
        ol = z.Outline(); ol.NewOutline()
        for (x, y) in [(0.3, 0.3), (BW - 0.3, 0.3), (BW - 0.3, BH - 0.3), (0.3, BH - 0.3)]:
            ol.Append(mm(x), mm(y))
        z.SetLocalClearance(mm(0.2))
        z.SetMinThickness(mm(0.2))
        z.SetThermalReliefGap(mm(0.4))
        z.SetThermalReliefSpokeWidth(mm(0.45))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)   # SMD pads solid, through-hole pads with thermal spokes (easier to solder)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        board.Add(z)

if __name__ == "__main__":
    board, fps, netmap = make_board()
    add_zones(board, netmap)
    out = os.path.join(HW, "pedal.kicad_pcb")
    board.Save(out)
    print("placed", len(fps), "footprints ->", out)
