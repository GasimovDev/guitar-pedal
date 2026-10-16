"""
Drilling template for the enclosure, printed 1:1 -> ../fab/enclosure-drill-template.pdf

The hole positions come from the PCB itself (pot shafts and LEDs), so the
knobs line up with the board. Box: Hammond 1590XX (about 145 x 121 x 39 mm).
"""
import os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_pcb import POT_SHAFT, LED_POS, BW, BH

HW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(HW, "fab", "enclosure-drill-template.pdf")

BOX_W, BOX_L, BOX_D = 121.0, 145.0, 39.0    # face width, face length, depth (mm)
OFF_X = (BOX_W - BW) / 2                     # board centred left-right
OFF_Y = 12.0                                 # board's top edge 12 mm below the box's top end
FSW_Y = OFF_Y + BH + 30.0                    # footswitch row, below the board
WALL_DEPTH = 24.0                            # jack centres: 24 mm down from the face

KNOB = {"RV1": "DRIVE", "RV2": "TONE", "RV3": "RATE", "RV4": "DEPTH", "RV5": "TIME", "RV6": "REPEATS"}
LED = {"D3": "OD LED", "D4": "TREM LED", "D5": "DELAY LED"}
D_POT, D_LED, D_FSW, D_JACK, D_DC = 7.5, 3.5, 12.5, 9.5, 12.0

A4 = (210 / 25.4, 297 / 25.4)

def page():
    fig = plt.figure(figsize=A4)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 210); ax.set_ylim(297, 0); ax.axis("off")
    return fig, ax

def hole(ax, x, y, d, label, sub=""):
    ax.add_patch(plt.Circle((x, y), d / 2, fill=False, lw=0.6))
    ax.plot([x - d / 2 - 3, x + d / 2 + 3], [y, y], lw=0.3, c="k")
    ax.plot([x, x], [y - d / 2 - 3, y + d / 2 + 3], lw=0.3, c="k")
    ax.text(x, y + d / 2 + 4.5, "%s\n%s" % (label, sub or "drill %.1f mm" % d), ha="center", va="top", fontsize=6)

def scale_bar(ax, x, y):
    ax.plot([x, x + 50], [y, y], lw=1.2, c="k")
    for t in (x, x + 50):
        ax.plot([t, t], [y - 1.5, y + 1.5], lw=1.2, c="k")
    ax.text(x + 25, y - 2.5, "this bar must measure exactly 50 mm", ha="center", fontsize=7)

def face_page(pdf):
    fig, ax = page()
    X0, Y0 = (210 - BOX_W) / 2, 40.0           # where the face sits on the paper
    ax.text(105, 10, "PEDAL FACE (top of the box) - drilling template, seen from OUTSIDE", ha="center", fontsize=11, weight="bold")
    ax.text(105, 16, "Print at 100 % ('actual size', no 'fit to page'). Check the 50 mm bar with a ruler.\n"
                     "Tape it on the box, centre-punch every cross, drill small (3 mm) first, then open up with a step drill.",
            ha="center", va="top", fontsize=7.5)
    scale_bar(ax, 80, 33)
    ax.add_patch(plt.Rectangle((X0, Y0), BOX_W, BOX_L, fill=False, lw=0.8))
    ax.text(X0 + BOX_W / 2, Y0 - 1.5, "top end (DC jack side)", ha="center", fontsize=7)
    ax.text(X0 - 2, Y0 + 33.5, "OUTPUT\nside", ha="right", va="center", fontsize=7)
    ax.text(X0 + BOX_W + 2, Y0 + 33.5, "INPUT\nside", ha="left", va="center", fontsize=7)
    ax.plot([X0 + BOX_W / 2] * 2, [Y0, Y0 + BOX_L], lw=0.2, c="0.6", ls="--")
    # the PCB's outline, so you can see where the board sits inside
    ax.add_patch(plt.Rectangle((X0 + OFF_X, Y0 + OFF_Y), BW, BH, fill=False, lw=0.4, ls=":", ec="0.5"))
    ax.text(X0 + OFF_X + 1, Y0 + OFF_Y + BH - 1, "PCB outline (inside)", fontsize=5.5, color="0.5")
    rows = []
    for ref, (sx, sy) in POT_SHAFT.items():
        x, y = X0 + OFF_X + sx, Y0 + OFF_Y + sy
        hole(ax, x, y, D_POT, KNOB[ref]); rows.append((KNOB[ref], OFF_X + sx, OFF_Y + sy, D_POT))
    for ref, (lx, ly) in LED_POS.items():
        x, y = X0 + OFF_X + lx, Y0 + OFF_Y + ly
        hole(ax, x, y, D_LED, LED[ref]); rows.append((LED[ref], OFF_X + lx, OFF_Y + ly, D_LED))
    for (lx, _), nm in zip(LED_POS.values(), ("OD switch", "TREM switch", "DELAY switch")):
        x, y = X0 + OFF_X + lx, Y0 + FSW_Y
        hole(ax, x, y, D_FSW, nm); rows.append((nm, OFF_X + lx, FSW_Y, D_FSW))
    # table of coordinates, in case you mark it out with a ruler instead
    ty = Y0 + BOX_L + 8
    ax.text(X0, ty, "Hole centres, mm from the face's top-left corner (seen from outside):", fontsize=7, weight="bold")
    for i, (nm, x, y, d) in enumerate(rows):
        col, r = divmod(i, 6)
        ax.text(X0 + col * 45, ty + 4 + r * 3.6, "%-12s x %5.1f  y %5.1f  (%.1f)" % (nm, x, y, d),
                fontsize=6.5, family="monospace")
    ax.text(X0, ty + 28, "Drawn for a Hammond 1590XX (145 x 121 x 39 mm). Different box? Keep the holes' positions\n"
                         "relative to each other (they match the PCB) and centre the group on your box.",
            fontsize=6.5, va="top")
    pdf.savefig(fig); plt.close(fig)

def wall(ax, x0, y0, length, title, holes, note):
    ax.add_patch(plt.Rectangle((x0, y0), length, BOX_D, fill=False, lw=0.8))
    ax.text(x0, y0 - 2, title, fontsize=8, weight="bold")
    ax.text(x0 + length + 2, y0 + 1, "face (top) edge", fontsize=6, va="center")
    ax.text(x0 + length + 2, y0 + BOX_D - 1, "open edge (lid)", fontsize=6, va="center")
    for (hx, d, lab) in holes:
        hole(ax, x0 + hx, y0 + WALL_DEPTH, d, lab)
    ax.text(x0, y0 + BOX_D + 13, note, fontsize=6.5, va="top")

def walls_page(pdf):
    fig, ax = page()
    ax.text(105, 10, "SIDE WALLS - seen from OUTSIDE, face edge at the top", ha="center", fontsize=11, weight="bold")
    ax.text(105, 16, "All three holes are %d mm down from the face. That keeps the jacks below the parts on the PCB.\n"
                     "Solder the jack and switch wires straight into J1/J2/J3/J6 (no pin headers there), so nothing sticks down."
            % WALL_DEPTH, ha="center", va="top", fontsize=7.5)
    scale_bar(ax, 80, 30)
    wall(ax, (210 - BOX_W) / 2, 45, BOX_W, "TOP END wall (121 mm)", [(BOX_W / 2, D_DC, "9 V DC jack")],
         "The DC jack sits in the middle of the top end.")
    # Seen from outside with the face up: on the right wall the box's top end is
    # on your right, on the left wall it is on your left.
    wall(ax, 20, 120, BOX_L, "RIGHT side wall = INPUT (145 mm). Top end of the box is at the RIGHT of this drawing.",
         [(BOX_L - (OFF_Y + 21.5), D_JACK, "INPUT jack")], "Input jack centre: %.1f mm from the top end." % (OFF_Y + 21.5))
    wall(ax, 20, 200, BOX_L, "LEFT side wall = OUTPUT (145 mm). Top end of the box is at the LEFT of this drawing.",
         [(OFF_Y + 21.5, D_JACK, "OUTPUT jack")], "Output jack centre: %.1f mm from the top end." % (OFF_Y + 21.5))
    pdf.savefig(fig); plt.close(fig)

if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with PdfPages(OUT) as pdf:
        face_page(pdf); walls_page(pdf)
    print("wrote", OUT)
