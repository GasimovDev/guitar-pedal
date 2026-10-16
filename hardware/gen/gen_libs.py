"""Write the project's own symbol library (pedal.kicad_sym) and footprint (pedal.pretty)."""
import os, uuid
from sexp import Sym, dump

HW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
F = lambda: [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]
FH = lambda: [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]], Sym("hide")]

def prop(name, val, x, y, hide=False, pid=0):
    return [Sym("property"), name, val, [Sym("at"), x, y, 0], FH() if hide else F()]

def pin(etype, x, y, ang, name, num, length=5.08):
    return [Sym("pin"), Sym(etype), Sym("line"), [Sym("at"), x, y, ang], [Sym("length"), length],
            [Sym("name"), name, F()], [Sym("number"), str(num), F()]]

def box_symbol(name, ref, fp, ds, left, right, top, bottom, w=10.16, desc=""):
    """left/right: [(num, name, type)] listed top->bottom; top/bottom: listed left->right."""
    n = max(len(left), len(right))
    h = (n + 1) * 2.54
    h = max(h, 10.16)
    top_y = round(h / 2 / 2.54) * 2.54 + 2.54
    bot_y = -top_y
    pins = []
    for i, (num, nm, t) in enumerate(left):
        pins.append(pin(t, -w - 5.08, top_y - 2.54 * (i + 1), 0, nm, num))
    for i, (num, nm, t) in enumerate(right):
        pins.append(pin(t, w + 5.08, top_y - 2.54 * (i + 1), 180, nm, num))
    for i, (num, nm, t) in enumerate(top):
        x = (i - (len(top) - 1) / 2) * 5.08
        pins.append(pin(t, x, top_y + 5.08, 270, nm, num))
    for i, (num, nm, t) in enumerate(bottom):
        x = (i - (len(bottom) - 1) / 2) * 5.08
        pins.append(pin(t, x, bot_y - 5.08, 90, nm, num))
    body = [Sym("symbol"), name + "_0_1",
            [Sym("rectangle"), [Sym("start"), -w, top_y], [Sym("end"), w, bot_y],
             [Sym("stroke"), [Sym("width"), 0.254], [Sym("type"), Sym("default")]],
             [Sym("fill"), [Sym("type"), Sym("background")]]]]
    return [Sym("symbol"), name, [Sym("pin_names"), [Sym("offset"), 1.016]],
            [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")],
            prop("Reference", ref, 0, top_y + 7.62),
            prop("Value", name, 0, bot_y - 7.62),
            prop("Footprint", fp, 0, bot_y - 10.16, True),
            prop("Datasheet", ds, 0, bot_y - 12.7, True),
            prop("ki_description", desc, 0, 0, True),
            body, [Sym("symbol"), name + "_1_1"] + pins]

def symbols():
    pcm1808 = box_symbol(
        "PCM1808PW", "U", "Package_SO:TSSOP-14_4.4x5mm_P0.65mm",
        "https://www.ti.com/lit/ds/symlink/pcm1808.pdf",
        left=[("6", "SCKI", "input"), ("8", "BCK", "bidirectional"), ("7", "LRCK", "bidirectional"),
              ("9", "DOUT", "output"), ("", "", ""), ("12", "FMT", "input"), ("10", "MD0", "input"),
              ("11", "MD1", "input")],
        right=[("13", "VINL", "input"), ("14", "VINR", "input"), ("", "", ""), ("1", "VREF", "passive")],
        top=[("3", "VCC", "power_in"), ("4", "VDD", "power_in")],
        bottom=[("2", "AGND", "power_in"), ("5", "DGND", "power_in")],
        desc="Single-ended 24-bit stereo ADC, 99 dB SNR, TSSOP-14")
    # drop the spacer pins
    for sub in pcm1808:
        if isinstance(sub, list) and sub and sub[0] == "symbol" and sub[1].endswith("_1_1"):
            sub[:] = [x for x in sub if not (isinstance(x, list) and x[0] == "pin" and x[6][1] == "")]

    # Black Pill: header A (pins 1-20) on the left, header B (21-40) on the right
    from design import BP_A, BP_B
    def t(n):
        if n in ("5V", "3V3", "VBAT"): return "passive"
        if n == "GND": return "passive"
        return "bidirectional"
    left = [(str(i + 1), "A%d_%s" % (i + 1, n), t(n)) for i, n in enumerate(BP_A)]
    right = [(str(i + 21), "B%d_%s" % (i + 1, n), t(n)) for i, n in enumerate(BP_B)]
    bp = box_symbol("BlackPill_F411", "U", "pedal:BlackPill_Sockets",
                    "https://stm32-base.org/boards/STM32F411CEU6-WeAct-Black-Pill-V2.0.html",
                    left, right, [], [], w=12.7,
                    desc="WeAct Black Pill STM32F411CEU6 module on two 1x20 sockets")
    return [Sym("kicad_symbol_lib"), [Sym("version"), 20220914], [Sym("generator"), Sym("pedal_gen")], pcm1808, bp]


def footprint_blackpill():
    """Two 1x20 female headers, 15.24 mm apart, as seen from the TOP of the
    Black Pill (its components up) with the USB-C end on the LEFT.
    Row B (PB12 ... 3V3) is the upper row, row A the lower one. Both rows start
    at the USB end with PB12 / VBAT; the power pins sit at the far end. (The
    stm32-base.org pin tables count row A from the far end: 5V ... VBAT.)
    The footprint is placed flipped on the bottom of the pedal PCB, which is
    exactly how the module hangs under the board (components facing away)."""
    from design import BP_A, BP_B
    items = [Sym("footprint"), "BlackPill_Sockets", [Sym("version"), 20221018], [Sym("generator"), Sym("pedal_gen")],
             [Sym("layer"), "F.Cu"],
             [Sym("descr"), "WeAct Black Pill (STM32F4x1) on two 1x20 2.54 mm sockets, rows 15.24 mm apart"],
             [Sym("attr"), Sym("through_hole")],
             [Sym("fp_text"), Sym("reference"), "REF**", [Sym("at"), 24.13, -4.5], [Sym("layer"), "F.SilkS"],
              [Sym("effects"), [Sym("font"), [Sym("size"), 1, 1], [Sym("thickness"), 0.15]]]],
             [Sym("fp_text"), Sym("value"), "BlackPill", [Sym("at"), 24.13, 7.62], [Sym("layer"), "F.Fab"],
              [Sym("effects"), [Sym("font"), [Sym("size"), 1, 1], [Sym("thickness"), 0.15]]]]]
    def line(x1, y1, x2, y2, layer, w=0.12):
        return [Sym("fp_line"), [Sym("start"), x1, y1], [Sym("end"), x2, y2],
                [Sym("stroke"), [Sym("width"), w], [Sym("type"), Sym("solid")]], [Sym("layer"), layer]]
    # module outline 52.8 x 20.8 mm; USB end ~2.3 mm beyond pin 1
    x0, x1, y0, y1 = -2.3, 50.5, -2.77, 18.01
    for L, w in (("F.Fab", 0.1), ("F.SilkS", 0.12)):
        items += [line(x0, y0, x1, y0, L, w), line(x1, y0, x1, y1, L, w),
                  line(x1, y1, x0, y1, L, w), line(x0, y1, x0, y0, L, w)]
    items += [line(x0 - 0.25, y0 - 0.25, x1 + 0.25, y0 - 0.25, "F.CrtYd", 0.05),
              line(x1 + 0.25, y0 - 0.25, x1 + 0.25, y1 + 0.25, "F.CrtYd", 0.05),
              line(x1 + 0.25, y1 + 0.25, x0 - 0.25, y1 + 0.25, "F.CrtYd", 0.05),
              line(x0 - 0.25, y1 + 0.25, x0 - 0.25, y0 - 0.25, "F.CrtYd", 0.05)]
    items.append([Sym("fp_text"), Sym("user"), "USB-C", [Sym("at"), 0.8, 7.62, 90], [Sym("layer"), "F.SilkS"],
                  [Sym("effects"), [Sym("font"), [Sym("size"), 1, 1], [Sym("thickness"), 0.15]]]])
    for row, names, base, y in (("B", BP_B, 21, 0.0), ("A", BP_A, 1, 15.24)):
        for i, nm in enumerate(names):
            x = i * 2.54 if row == "B" else (19 - i) * 2.54
            num = base + i
            shape = Sym("rect") if i == 0 else Sym("oval")
            items.append([Sym("pad"), str(num), Sym("thru_hole"), shape, [Sym("at"), x, y],
                          [Sym("size"), 1.7, 1.7], [Sym("drill"), 1.0], [Sym("layers"), "*.Cu", "*.Mask"]])
            ty = y + 2.2 if row == "B" else y - 2.2
            just = [Sym("justify"), Sym("left")] if row == "B" else [Sym("justify"), Sym("right")]
            items.append([Sym("fp_text"), Sym("user"), nm.replace("GND", "G"), [Sym("at"), x, ty, 90],
                          [Sym("layer"), "F.SilkS"],
                          [Sym("effects"), [Sym("font"), [Sym("size"), 0.7, 0.7], [Sym("thickness"), 0.12]], just]])
    return items


def footprint_jlc_fiducial():
    return None


def main():
    os.makedirs(os.path.join(HW, "pedal.pretty"), exist_ok=True)
    open(os.path.join(HW, "pedal.kicad_sym"), "w").write(dump(symbols()) + "\n")
    open(os.path.join(HW, "pedal.pretty", "BlackPill_Sockets.kicad_mod"), "w").write(dump(footprint_blackpill()) + "\n")
    # library tables so KiCad finds the project libraries
    open(os.path.join(HW, "sym-lib-table"), "w").write(
        '(sym_lib_table\n  (lib (name "pedal")(type "KiCad")(uri "${KIPRJMOD}/pedal.kicad_sym")(options "")(descr "Pedal project symbols"))\n)\n')
    open(os.path.join(HW, "fp-lib-table"), "w").write(
        '(fp_lib_table\n  (lib (name "pedal")(type "KiCad")(uri "${KIPRJMOD}/pedal.pretty")(options "")(descr "Pedal project footprints"))\n)\n')

if __name__ == "__main__":
    main()
