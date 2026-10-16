"""
Generate the KiCad 7 schematic from design.py.

Layout: one A3 sheet per circuit section. Every pin gets a short wire and a
global label with its net name, so two pins with the same label are connected
(that is how KiCad works: same label = same wire). Each sheet ends with a
notes block that says what every part is for.
"""
import os, uuid, math
from sexp import Sym, dump, load_symbol, symbol_pins, unit_count, find, findall
import design

HW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
EXTRA = {"pedal": os.path.join(HW, "pedal.kicad_sym")}
PROJECT = "pedal"
NS = uuid.UUID("6f1d3c55-0a63-4c5e-9d2e-2b7a0f6c9e11")

def uid(*key):
    return str(uuid.uuid5(NS, "/".join(key)))

def eff(size=1.27, hide=False, justify=None):
    e = [Sym("effects"), [Sym("font"), [Sym("size"), size, size]]]
    if justify: e.append([Sym("justify")] + [Sym(j) for j in justify])
    if hide: e.append(Sym("hide"))
    return e

def snap(v, g=1.27):
    return round(v / g) * g

ROOT_UUID = uid("root")
symcache = {}

def libsym(lib_id):
    if lib_id not in symcache:
        symcache[lib_id] = load_symbol(lib_id, EXTRA)
    return symcache[lib_id]

def out_dir(ang):
    # pin angle = direction from the connection point into the body
    return {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[ang]

def label_angle(dx, dy):
    return {(-1, 0): 180, (1, 0): 0, (0, 1): 270, (0, -1): 90}[(dx, dy)]

def text_len(s):
    return 1.0 * len(s) + 2.5

def place_cell(p, unit):
    """Return (pins_of_unit, bbox relative to symbol origin in sheet coords)."""
    sym = libsym(p["lib"])
    pins = [x for x in symbol_pins(sym) if x[0] in (0, unit)]
    xs, ys = [-2.54, 2.54], [-2.54, 2.54]
    for (_, num, nm, px, py, ang, et) in pins:
        sx, sy = px, -py
        dx, dy = out_dir(ang)
        net = p["pins"].get(num)
        L = 2.54 + (text_len(net) if net else 1)
        ex, ey = sx + dx * L, sy + dy * L
        xs += [sx, ex]; ys += [sy, ey]
    # body extent (rough): use pins and a minimum box
    return pins, (min(xs) - 2, min(ys) - 2, max(xs) + 7, max(ys) + 3)

def sym_instance(p, unit, X, Y, sheet_path):
    sym = libsym(p["lib"])
    is_power = p["lib"].startswith("power:")
    su = uid("sym", p["ref"], str(unit))
    e = [Sym("symbol"), [Sym("lib_id"), p["lib"]], [Sym("at"), X, Y, 0], [Sym("unit"), unit],
         [Sym("in_bom"), Sym("no") if is_power or p["ref"].startswith("TP") or p["ref"].startswith("H") else Sym("yes")],
         [Sym("on_board"), Sym("no") if is_power else Sym("yes")],
         [Sym("dnp"), Sym("no")], [Sym("uuid"), su]]
    ref = ("#FLG" + p["ref"][2:]) if is_power else p["ref"]
    # put Reference/Value where the library symbol's author put them
    lp = {pr[1]: pr for pr in findall(sym, "property")}
    def field(name, val, hide=False):
        at = find(lp[name], "at") if name in lp else [Sym("at"), 0, 0, 0]
        ang = at[3] if len(at) > 3 else 0
        le = find(lp[name], "effects") if name in lp else None
        just = None
        if le is not None and find(le, "justify"):
            just = [str(j) for j in find(le, "justify")[1:]]
        return [Sym("property"), name, val, [Sym("at"), X + float(at[1]), Y - float(at[2]), ang],
                eff(hide=hide, justify=just)]
    e.append(field("Reference", ref, hide=is_power))
    e.append(field("Value", p["value"]))
    e.append([Sym("property"), "Footprint", p["fp"] or "", [Sym("at"), X, Y, 0], eff(hide=True)])
    ds = find(sym, "property")
    dsv = ""
    for pr in findall(sym, "property"):
        if pr[1] == "Datasheet": dsv = pr[2]
    e.append([Sym("property"), "Datasheet", dsv, [Sym("at"), X, Y, 0], eff(hide=True)])
    if not is_power:
        e.append([Sym("property"), "MPN", p["mpn"], [Sym("at"), X, Y, 0], eff(hide=True)])
        e.append([Sym("property"), "Description", p["desc"], [Sym("at"), X, Y, 0], eff(hide=True)])
        e.append([Sym("property"), "Assembly", "HAND" if p["ref"] in design.HAND_SOLDER else
                  ("NONE" if p["ref"].startswith(("TP", "H")) else "FACTORY"), [Sym("at"), X, Y, 0], eff(hide=True)])
    for (u, num, nm, px, py, ang, et) in symbol_pins(sym):
        if u in (0, unit):
            e.append([Sym("pin"), num, [Sym("uuid"), uid("pin", p["ref"], num)]])
    e.append([Sym("instances"), [Sym("project"), PROJECT,
              [Sym("path"), sheet_path, [Sym("reference"), ref], [Sym("unit"), unit]]]])
    return e

def wire(x1, y1, x2, y2, key):
    return [Sym("wire"), [Sym("pts"), [Sym("xy"), x1, y1], [Sym("xy"), x2, y2]],
            [Sym("stroke"), [Sym("width"), 0], [Sym("type"), Sym("default")]], [Sym("uuid"), uid("w", key)]]

def glabel(net, x, y, ang, key):
    just = {0: ["left"], 180: ["right"], 90: ["left"], 270: ["right"]}[ang]
    return [Sym("global_label"), net, [Sym("shape"), Sym("passive")], [Sym("at"), x, y, ang],
            [Sym("fields_autoplaced")], eff(justify=just), [Sym("uuid"), uid("gl", key)],
            [Sym("property"), "Intersheetrefs", "${INTERSHEET_REFS}", [Sym("at"), x, y, 0], eff(size=1.0, hide=True)]]

def noconn(x, y, key):
    return [Sym("no_connect"), [Sym("at"), x, y], [Sym("uuid"), uid("nc", key)]]

def text(s, x, y, size=1.27, key=""):
    return [Sym("text"), s, [Sym("at"), x, y, 0], eff(size=size, justify=["left", "top"]),
            [Sym("uuid"), uid("t", key or s[:40], str(x), str(y))]]

def make_sheet(sec, title, sheet_uuid, page):
    sheet_path = "/" + ROOT_UUID + "/" + sheet_uuid
    items = []
    used_libs = []
    items.append(text(title, 12, 10, 2.5, key="title" + sec))
    ps = [p for p in design.parts if p["section"] == sec]
    # order: big parts (many pins) first
    cells = []
    for p in ps:
        sym = libsym(p["lib"])
        if p["lib"] not in used_libs: used_libs.append(p["lib"])
        nu = unit_count(sym)
        for u in range(1, nu + 1):
            pins, bb = place_cell(p, u)
            cells.append((p, u, pins, bb))
    # keep the order of design.py = roughly signal-flow order; ICs first
    big = [c for c in cells if len(c[2]) > 3 or c[0]["lib"].startswith("Amplifier")]
    small = [c for c in cells if c not in big]
    x0, y0, xmax = 15.0, 25.0, 282.0
    x, y, rowh = x0, y0, 0
    for (p, u, pins, bb) in big + small:
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        if x + w > xmax:
            x = x0; y += rowh + 10; rowh = 0
        X, Y = snap(x - bb[0]), snap(y - bb[1])
        items.append(sym_instance(p, u, X, Y, sheet_path))
        for (_, num, nm, px, py, ang, et) in pins:
            sx, sy = X + px, Y - py
            net = p["pins"].get(num)
            key = p["ref"] + "." + num
            dx, dy = out_dir(ang)
            if net is None:
                items.append(noconn(sx, sy, key))
                continue
            ex, ey = sx + dx * 2.54, sy + dy * 2.54
            items.append(wire(sx, sy, ex, ey, key))
            items.append(glabel(net, ex, ey, label_angle(dx, dy), key))
        x += w + 2
        rowh = max(rowh, h)
    # notes
    ny = y + rowh + 8
    groups = {}
    for p in ps:
        if p["desc"] and not p["lib"].startswith("power:"):
            groups.setdefault((p["desc"], p["value"]), []).append(p["ref"])
    lines = ["%s (%s): %s" % (", ".join(refs), v, d) for (d, v), refs in groups.items()]
    col = 0
    per_col = 30
    for i in range(0, len(lines), per_col):
        items.append(text("\n".join(lines[i:i + per_col]), 12 + col * 140, ny, 1.27, key="notes%s%d" % (sec, i)))
        col += 1
    lib_symbols = [Sym("lib_symbols")] + [libsym(l) for l in used_libs]
    sch = [Sym("kicad_sch"), [Sym("version"), 20230121], [Sym("generator"), Sym("eeschema")],
           [Sym("uuid"), sheet_uuid], [Sym("paper"), "A4"],
           [Sym("title_block"), [Sym("title"), "Guitar pedal - " + sec],
            [Sym("company"), "Embedded audio learning project"], [Sym("rev"), "A"]],
           lib_symbols] + items + [[Sym("sheet_instances"), [Sym("path"), "/", [Sym("page"), str(page)]]]]
    return sch

def main():
    sheets = []
    root_items = []
    root_items.append(text("GUITAR EFFECTS PEDAL  -  STM32F411 + PCM1808 ADC + PCM5102A DAC", 20, 20, 4.0, key="roottitle"))
    root_items.append(text(
        "Signal path:  guitar -> INPUT buffer -> ADC (PCM1808) -> I2S -> MCU (overdrive, tremolo, delay)"
        " -> I2S -> DAC (PCM5102A) -> OUTPUT buffer -> amp\n"
        "Every wire is drawn as a label: two labels with the same name are the same wire.\n"
        "Power: 9 V centre-negative adapter. Net names: +9V (after the protection diode), +5V, +5VA (ADC analog),"
        " +3V3A (converters), +3V3_MCU (from the Black Pill), VBIAS (half of 9 V, the op-amps' 'zero').",
        20, 30, 1.8, key="rootdesc"))
    for i, (sec, title) in enumerate(design.sections):
        su = uid("sheet", sec)
        fname = "%s.kicad_sch" % sec
        sheets.append((sec, title, su, fname))
        col, row = i % 4, i // 4
        sx, sy = 20 + col * 97, 60 + row * 55
        root_items.append([Sym("sheet"), [Sym("at"), sx, sy], [Sym("size"), 85, 40],
                           [Sym("fields_autoplaced")],
                           [Sym("stroke"), [Sym("width"), 0.1524], [Sym("type"), Sym("solid")]],
                           [Sym("fill"), [Sym("color"), 0, 0, 0, 0.0]],
                           [Sym("uuid"), su],
                           [Sym("property"), "Sheetname", sec.upper(), [Sym("at"), sx, sy - 0.7, 0],
                            eff(justify=["left", "bottom"])],
                           [Sym("property"), "Sheetfile", fname, [Sym("at"), sx, sy + 40.6, 0],
                            eff(justify=["left", "top"])],
                           [Sym("instances"), [Sym("project"), PROJECT,
                                                [Sym("path"), "/" + ROOT_UUID, [Sym("page"), str(i + 2)]]]]])
        root_items.append(text(title.split(":", 1)[-1].strip(), sx + 2, sy + 4, 1.5, key="desc" + sec))
    root = [Sym("kicad_sch"), [Sym("version"), 20230121], [Sym("generator"), Sym("eeschema")],
            [Sym("uuid"), ROOT_UUID], [Sym("paper"), "A3"],
            [Sym("title_block"), [Sym("title"), "Guitar effects pedal"], [Sym("date"), "2026-10-14"],
             [Sym("rev"), "A"], [Sym("company"), "Embedded audio learning project"]],
            [Sym("lib_symbols")]] + root_items + \
           [[Sym("sheet_instances"), [Sym("path"), "/", [Sym("page"), "1"]]]]
    open(os.path.join(HW, "pedal.kicad_sch"), "w").write(dump(root) + "\n")
    for i, (sec, title, su, fname) in enumerate(sheets):
        open(os.path.join(HW, fname), "w").write(dump(make_sheet(sec, title, su, i + 2)) + "\n")
    # map ref -> path for the PCB
    import json
    paths = {}
    for p in design.parts:
        if p["lib"].startswith("power:"): continue
        su = uid("sheet", p["section"])
        paths[p["ref"]] = "/%s/%s" % (su, uid("sym", p["ref"], "1"))
    json.dump(paths, open(os.path.join(os.path.dirname(__file__), "sym_paths.json"), "w"), indent=1)

if __name__ == "__main__":
    main()
