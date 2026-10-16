"""
Autoroute the PCB with Freerouting, then pour the ground planes and check.

  python3 route.py            -> route, pour, save, DRC report
Needs: java and freerouting.jar (path in FREEROUTING env var or ./freerouting.jar)
"""
import os, sys, subprocess, math
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.join(HERE, "..")
PCB = os.path.join(HW, "pedal.kicad_pcb")
JAR = os.environ.get("FREEROUTING", os.path.join(HERE, "freerouting.jar"))
WORK = os.environ.get("ROUTE_WORK", "/tmp/pedal_route")
ROUTE_GND = os.environ.get("ROUTE_GND", "0") == "1"
os.makedirs(WORK, exist_ok=True)

def stitch_vias(board, gnd, pitch=4.0):
    """Ground vias on a grid wherever there is room: ties the top and bottom
    ground planes together so return currents have a short path and no
    piece of ground pour is left floating."""
    mm = pcbnew.FromMM
    others_b = [s for s in item_shapes(board, pcbnew.B_Cu) if s[0] != gnd.GetNetCode()]
    others_f = [s for s in item_shapes(board, pcbnew.F_Cu) if s[0] != gnd.GetNetCode()]
    holes = [p.GetPosition() for f in board.GetFootprints() for p in f.Pads() if p.HasHole()]
    vias = [t.GetPosition() for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    added = 0
    y = 2.0
    while y < 75.0:
        x = 2.0
        while x < 84.0:
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
            v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3)); v.SetNet(gnd)
            if clear_of(v.GetEffectiveShape(pcbnew.B_Cu), others_b, -1, mm(0.25)) and \
               clear_of(v.GetEffectiveShape(pcbnew.F_Cu), others_f, -1, mm(0.25)) and \
               all((p - v.GetPosition()).EuclideanNorm() > mm(1.6) for p in holes) and \
               all((p - v.GetPosition()).EuclideanNorm() > mm(1.0) for p in vias):
                board.Add(v); added += 1
            x += pitch
        y += pitch
    return added

def gnd_fanout(board):
    """Before routing: give every small surface-mount ground pad (chip pins,
    capacitors, resistors) its own short track and via. Otherwise the router
    can box a pad in with signal tracks so the ground pour never reaches it.
    Neighbouring ground pins of a chip share one via."""
    mm = pcbnew.FromMM
    LAY = (pcbnew.F_Cu, pcbnew.B_Cu)
    gnd = board.FindNet("GND"); gc = gnd.GetNetCode()
    others = {L: [s for s in item_shapes(board, L) if s[0] != gc] for L in LAY}
    holes = [h.GetPosition() for fp in board.GetFootprints() for h in fp.Pads() if h.HasHole()]
    new_vias = []
    added = 0
    for f in board.GetFootprints():
        if any(p.HasHole() for p in f.Pads()):
            continue        # through-hole parts touch both pours already
        pads = [p for p in f.Pads() if p.GetNetCode() == gc and
                min(p.GetBoundingBox().GetWidth(), p.GetBoundingBox().GetHeight()) < mm(1.6)]
        if not pads:
            continue        # (a regulator's big tab sits in the pour anyway)
        allp = list(f.Pads())
        c = pcbnew.VECTOR2I(sum(p.GetPosition().x for p in allp) // len(allp),
                            sum(p.GetPosition().y for p in allp) // len(allp))
        lay = pcbnew.B_Cu if f.IsFlipped() else pcbnew.F_Cu
        chip = len(allp) > 3
        groups = []
        for p in sorted(pads, key=lambda p: (p.GetPosition().y, p.GetPosition().x)):
            for g in groups:
                if chip and pcbnew.ToMM((p.GetPosition() - g[-1].GetPosition()).EuclideanNorm()) < 0.7:
                    g.append(p); break
            else:
                groups.append([p])
        for g in groups:
            p0 = g[0]; bb = p0.GetBoundingBox(); pos = p0.GetPosition()
            d = pos - c
            if chip:
                ax = "y" if bb.GetHeight() > bb.GetWidth() else "x"
            else:
                ax = "y" if abs(d.y) > abs(d.x) else "x"
            sgn = 1 if (d.y if ax == "y" else d.x) >= 0 else -1
            tries = [(ax, sgn)]
            if len(g) == 1:
                other_ax = "x" if ax == "y" else "y"
                tries += [(other_ax, 1), (other_ax, -1)]
            xs = [q.GetPosition().x for q in g]; ys = [q.GetPosition().y for q in g]
            done = False
            for a_, s_ in tries:
                half = (bb.GetHeight() if a_ == "y" else bb.GetWidth()) // 2
                for extra in (0.65, 0.95, 1.25):
                    out = half + mm(extra)
                    if a_ == "y":
                        vpos = pcbnew.VECTOR2I((min(xs) + max(xs)) // 2, pos.y + s_ * out)
                        ends = [(q.GetPosition(), pcbnew.VECTOR2I(q.GetPosition().x, vpos.y)) for q in g]
                    else:
                        vpos = pcbnew.VECTOR2I(pos.x + s_ * out, (min(ys) + max(ys)) // 2)
                        ends = [(q.GetPosition(), pcbnew.VECTOR2I(vpos.x, q.GetPosition().y)) for q in g]
                    items = []
                    for a, e in ends + [(ends[0][1], ends[-1][1])]:
                        if a == e:
                            continue
                        t = pcbnew.PCB_TRACK(board); t.SetStart(a); t.SetEnd(e)
                        t.SetWidth(mm(0.3)); t.SetLayer(lay); t.SetNet(gnd); items.append(t)
                    v = pcbnew.PCB_VIA(board); v.SetPosition(vpos)
                    v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3)); v.SetNet(gnd)
                    ok = mm(1.0) < vpos.x < mm(84.0) and mm(1.0) < vpos.y < mm(75.0) and \
                         all(clear_of(t.GetEffectiveShape(), others[lay], -1, mm(0.2)) for t in items) and \
                         all(clear_of(v.GetEffectiveShape(L), others[L], -1, mm(0.2)) for L in LAY) and \
                         all((vpos - h).EuclideanNorm() > mm(1.2) for h in holes) and \
                         all((vpos - h).EuclideanNorm() > mm(0.9) for h in new_vias)
                    if ok:
                        for t in items:
                            board.Add(t)
                        board.Add(v); new_vias.append(vpos); added += 1; done = True
                        break
                if done:
                    break
            if not done:
                print("   no room for a ground via at", f.GetReference(), [q.GetNumber() for q in g])
    return added

def remove_dangling_vias(board):
    """Freerouting sometimes leaves a via that connects to only one track."""
    import re
    rpt = os.path.join(WORK, "drc_tmp.txt")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.WriteDRCReport(board, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
    pos = re.findall(r"via_dangling\][^@]*@\(([\d.]+) mm, ([\d.]+) mm\): Via \[([^\]]+)\]", open(rpt).read())
    n = 0
    for x, y, net in pos:
        for t in list(board.GetTracks()):
            if t.GetClass() == "PCB_VIA" and abs(pcbnew.ToMM(t.GetPosition().x) - float(x)) < 0.01 \
               and abs(pcbnew.ToMM(t.GetPosition().y) - float(y)) < 0.01:
                # also remove the stub track ending on it
                for s in list(board.GetTracks()):
                    if s.GetClass() == "PCB_TRACK" and s.GetNetCode() == t.GetNetCode() and \
                       (s.GetStart() == t.GetPosition() or s.GetEnd() == t.GetPosition()):
                        pass
                board.Remove(t); n += 1
                break
    return n

def import_ses(board, ses):
    """Read Freerouting's session file and add its tracks and vias to the board."""
    sys.path.insert(0, HERE)
    import sexp
    S = sexp.parse(open(ses).read())
    routes = sexp.find(S, "routes")
    res = sexp.find(routes, "resolution")
    per_unit_nm = {"um": 1000.0, "mm": 1e6, "mil": 25400.0}[str(res[1])] / float(res[2])
    nm = lambda v: int(round(float(v) * per_unit_nm))
    lib = sexp.find(routes, "library_out")
    vias = {}
    if lib:
        for ps in sexp.findall(lib, "padstack"):
            sh = sexp.find(ps, "shape")
            c = sexp.find(sh, "circle") if sh else None
            vias[ps[1]] = nm(c[2]) if c else pcbnew.FromMM(0.6)
    layers = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
    nt = nv = 0
    for net in sexp.findall(sexp.find(routes, "network_out"), "net"):
        ni = board.FindNet(net[1])
        for w in sexp.findall(net, "wire"):
            path = sexp.find(w, "path")
            lay, width = layers[path[1]], nm(path[2])
            pts = path[3:]
            xy = [(nm(pts[i]), -nm(pts[i + 1])) for i in range(0, len(pts) - 1, 2)]
            for a, b in zip(xy, xy[1:]):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pcbnew.VECTOR2I(*a)); t.SetEnd(pcbnew.VECTOR2I(*b))
                t.SetWidth(width); t.SetLayer(lay); t.SetNet(ni)
                board.Add(t); nt += 1
        for v in sexp.findall(net, "via"):
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(pcbnew.VECTOR2I(nm(v[2]), -nm(v[3])))
            via.SetWidth(vias.get(v[1], pcbnew.FromMM(0.6))); via.SetDrill(pcbnew.FromMM(0.3))
            via.SetNet(ni); board.Add(via); nv += 1
    return nt, nv

def item_shapes(board, layer):
    out = []
    for t in board.GetTracks():
        if t.IsOnLayer(layer):
            out.append((t.GetNetCode(), t.GetEffectiveShape()))
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.IsOnLayer(layer):
                out.append((p.GetNetCode(), p.GetEffectiveShape(layer)))
    return out

def clear_of(shape, shapes, net, clearance, own=None):
    for n, s in shapes:
        if s is own:
            continue
        if n == net and own is not None:
            continue
        if shape.Collide(s, clearance):
            return False
    return True

def unconnected_gnd_pads(board):
    """Ask KiCad's DRC which GND pads the pours did not reach."""
    import re, tempfile
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    rpt = os.path.join(WORK, "drc_tmp.txt")
    pcbnew.WriteDRCReport(board, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
    txt = open(rpt).read()
    pads = set(re.findall(r"Pad (\S+) \[GND\] of (\S+)", txt.split("unconnected pads")[-1]))
    return pads

def island_pads(board):
    """GND pads sitting on a piece of pour that has no via or through-hole pad."""
    gnd = board.FindNet("GND").GetNetCode()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pts = [t.GetPosition() for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetCode() == gnd] + \
          [p.GetPosition() for f in board.GetFootprints() for p in f.Pads() if p.HasHole() and p.GetNetCode() == gnd]
    out = set()
    for z in board.Zones():
        for L in (pcbnew.F_Cu, pcbnew.B_Cu):
            if not z.IsOnLayer(L):
                continue
            P = z.GetFilledPolysList(L)
            for i in range(P.OutlineCount()):
                fr = pcbnew.SHAPE_POLY_SET(); fr.AddOutline(P.Outline(i))
                if any(fr.Contains(p) for p in pts):
                    continue
                for f in board.GetFootprints():
                    hit = [p for p in f.Pads() if p.GetNetCode() == gnd and p.IsOnLayer(L) and fr.Contains(p.GetPosition())]
                    if hit:
                        out.add((hit[0].GetNumber(), f.GetReference()))
                        break
    return out

def fix_ground(board):
    """For every GND pad the pour can't reach: add a short track to a new
    via, which drops to the other layer's ground plane."""
    mm = pcbnew.FromMM
    gnd = board.FindNet("GND")
    total = 0
    for it in range(4):
        pads = unconnected_gnd_pads(board) | island_pads(board)
        if not pads:
            break
        print("pass %d: %d GND pads not reached by the pour" % (it, len(pads)))
        for num, ref in sorted(pads, key=lambda x: x[1]):
            f = board.FindFootprintByReference(ref)
            pad = [p for p in f.Pads() if p.GetNumber() == num][0]
            lay = pcbnew.B_Cu if pad.IsOnLayer(pcbnew.B_Cu) else pcbnew.F_Cu
            sh_l = item_shapes(board, lay)
            other = pcbnew.F_Cu if lay == pcbnew.B_Cu else pcbnew.B_Cu
            sh_o = item_shapes(board, other)
            c = pad.GetPosition()
            done = False
            for r in (1.1, 1.4, 1.7, 2.0, 2.4, 2.8, 3.3, 3.8, 4.4):
                for k in range(32):
                    a = k * math.pi / 16
                    pos = pcbnew.VECTOR2I(c.x + mm(r * math.cos(a)), c.y + mm(r * math.sin(a)))
                    if not (mm(0.8) < pos.x < mm(84.2) and mm(0.8) < pos.y < mm(75.2)):
                        continue
                    v = pcbnew.PCB_VIA(board); v.SetPosition(pos)
                    v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3)); v.SetNet(gnd)
                    t = pcbnew.PCB_TRACK(board); t.SetStart(c); t.SetEnd(pos)
                    t.SetWidth(mm(0.3)); t.SetLayer(lay); t.SetNet(gnd)
                    vs = v.GetEffectiveShape(lay)
                    ok = clear_of(vs, [s for s in sh_l if s[0] != gnd.GetNetCode()], -1, mm(0.22)) and \
                         clear_of(v.GetEffectiveShape(other), [s for s in sh_o if s[0] != gnd.GetNetCode()], -1, mm(0.22)) and \
                         clear_of(t.GetEffectiveShape(), [s for s in sh_l if s[0] != gnd.GetNetCode()], -1, mm(0.22))
                    if ok:
                        board.Add(v); board.Add(t); total += 1; done = True
                        break
                if done:
                    break
            if not done:
                print("   could not fix", ref, num)
    return total

def connect_islands(board):
    """A piece of ground pour boxed in by tracks may touch a GND pad but not the
    rest of the ground. Give every such piece its own via to the other layer."""
    mm = pcbnew.FromMM
    gnd = board.FindNet("GND")
    added = 0
    for it in range(5):
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        gvias = [t.GetPosition() for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetCode() == gnd.GetNetCode()]
        gth = [p.GetPosition() for f in board.GetFootprints() for p in f.Pads()
               if p.HasHole() and p.GetNetCode() == gnd.GetNetCode()]
        holes_all = [p.GetPosition() for f in board.GetFootprints() for p in f.Pads() if p.HasHole()] + \
                    [t.GetPosition() for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
        new = 0
        for z in board.Zones():
            for L in (pcbnew.F_Cu, pcbnew.B_Cu):
                if not z.IsOnLayer(L):
                    continue
                other = pcbnew.F_Cu if L == pcbnew.B_Cu else pcbnew.B_Cu
                polys = z.GetFilledPolysList(L)
                others_l = [s for s in item_shapes(board, L) if s[0] != gnd.GetNetCode()]
                others_o = [s for s in item_shapes(board, other) if s[0] != gnd.GetNetCode()]
                for i in range(polys.OutlineCount()):
                    frag = pcbnew.SHAPE_POLY_SET()
                    frag.AddOutline(polys.Outline(i))
                    if any(frag.Contains(p) for p in gvias + gth):
                        continue
                    bb = polys.Outline(i).BBox()
                    placed = False
                    step = mm(0.4)
                    y = bb.GetTop() + step
                    while y < bb.GetBottom() and not placed:
                        x = bb.GetLeft() + step
                        while x < bb.GetRight() and not placed:
                            pos = pcbnew.VECTOR2I(int(x), int(y))
                            if frag.Contains(pos) and polys.Contains(pos):
                                v = pcbnew.PCB_VIA(board); v.SetPosition(pos)
                                v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3)); v.SetNet(gnd)
                                far = all((pos - q).EuclideanNorm() > mm(1.0) for q in gvias + holes_all)
                                if far and clear_of(v.GetEffectiveShape(L), others_l, -1, mm(0.22)) and \
                                   clear_of(v.GetEffectiveShape(other), others_o, -1, mm(0.22)):
                                    board.Add(v); placed = True; new += 1
                                    gvias.append(pos)
                            x += step
                        y += step
        added += new
        if new == 0:
            break
    return added

def post_only():
    board = pcbnew.LoadBoard(PCB)
    print("island vias:", connect_islands(board))
    print("ground fix vias:", fix_ground(board))
    import gnd_bridge
    print("ground bridge items:", gnd_bridge.bridge(board))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(PCB)

def strip_board(path, kinds):
    sys.path.insert(0, HERE)
    import sexp
    b = sexp.parse(open(path).read())
    b = [x for x in b if not (isinstance(x, list) and x and x[0] in kinds)]
    return sexp.dump(b) + "\n"

def main():
    # 1. a throw-away copy without pours or old tracks, only for export
    # (done on the file text: removing zones through the Python API corrupts
    #  KiCad 7's SWIG bindings)
    tmp_path = os.path.join(WORK, "noroutes.kicad_pcb")
    open(tmp_path, "w").write(strip_board(PCB, ("zone", "segment", "via", "arc")))
    import shutil
    PRO = PCB.replace(".kicad_pcb", ".kicad_pro")
    shutil.copy(PRO, tmp_path.replace(".kicad_pcb", ".kicad_pro"))   # net classes + rules
    tmp = pcbnew.LoadBoard(tmp_path)
    print("ground fanout vias:", gnd_fanout(tmp))
    dsn = os.path.join(WORK, "pedal.dsn")
    ses = os.path.join(WORK, "pedal.ses")
    if os.path.exists(ses): os.remove(ses)
    pcbnew.ExportSpecctraDSN(tmp, dsn)
    import re
    txt = open(dsn).read()
    txt = re.sub(r"(\(class Power[^\n]*?) GND", r"\1", txt)
    if ROUTE_GND:
        # GND gets real tracks too (0.35 mm), so every ground pin is joined
        # even where signal tracks cut the pours into pieces
        txt = re.sub(r"(\(class Supply)", r"\1 GND", txt, count=1)
    else:
        # leave GND to the two pours: more room for the signals
        txt = re.sub(r"\(net GND\s*\(pins[^)]*\)\s*\)", "", txt)
        txt = txt.replace("(net GND)(type route)", "(net GND)(type protect)")
    # keep copper 0.5 mm away from the board edge: shrink the router's boundary
    def inset(m):
        nums = [float(v) for v in m.group(2).split()]
        xs, ys = nums[0::2], nums[1::2]
        x0, x1, y0, y1 = min(xs) + 500, max(xs) - 500, min(ys) + 500, max(ys) - 500
        return "%s%d %d %d %d %d %d %d %d %d %d)" % (m.group(1), x0, y0, x1, y0, x1, y1, x0, y1, x0, y0)
    txt = re.sub(r"(\(boundary\s*\(path pcb \S+ )([-\d.\s]+)\)", inset, txt, count=1)
    open(dsn, "w").write(txt)
    print("exported", dsn)
    cmd = [os.environ.get("JAVA", "/usr/lib/jvm/java-25-openjdk-amd64/bin/java"), "-jar", JAR, "-de", dsn, "-do", ses, "-mp", os.environ.get("PASSES", "30"),
           "--gui.enabled=false"]
    print(" ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3000)
    open(os.path.join(WORK, "freerouting.log"), "w").write(r.stdout + r.stderr)
    if not os.path.exists(ses):
        print(r.stdout[-3000:], r.stderr[-3000:]); sys.exit(1)
    # 2. fresh copy of the real board: delete old tracks, add the new ones
    clean = os.path.join(WORK, "clean.kicad_pcb")
    open(clean, "w").write(strip_board(PCB, ("segment", "via", "arc")))
    shutil.copy(PRO, clean.replace(".kicad_pcb", ".kicad_pro"))
    board = pcbnew.LoadBoard(clean)
    if not ROUTE_GND:   # (when GND is routed, the session file already has the fanout)
        print("ground fanout vias:", gnd_fanout(board))
    n_t, n_v = import_ses(board, ses)
    print("imported %d track segments, %d vias" % (n_t, n_v))
    gnd = board.FindNet("GND")
    print("stitching vias:", stitch_vias(board, gnd))
    print("dangling vias removed:", remove_dangling_vias(board))
    print("ground fix vias:", fix_ground(board))
    print("island vias:", connect_islands(board))
    import gnd_bridge
    print("ground bridge items:", gnd_bridge.bridge(board))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(PCB)
    shutil.copy(clean.replace(".kicad_pcb", ".kicad_pro"), PRO)   # Save() rewrote it; keep ours
    print("saved", PCB)

if __name__ == "__main__":
    post_only() if "--post" in sys.argv else main()
