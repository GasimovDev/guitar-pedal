"""
Last ground check after routing.

The two ground pours are cut into pieces by the signal tracks. Most pieces are
tied together by vias, but now and then a piece (with a chip's ground pin on
it) ends up boxed in. This file finds every piece of ground copper that is not
joined to the main ground and draws a short GND track to it, using a tiny maze
router on a 0.1 mm grid (both layers, with a via where it has to change side).
"""
import heapq, math
import numpy as np
import pcbnew
from PIL import Image, ImageDraw

mm, ToMM = pcbnew.FromMM, pcbnew.ToMM
LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu)
STEP = 0.1          # grid, mm
TRACK_W = 0.3       # bridge track width, mm
CLEAR = 0.2         # copper clearance, mm
VIA_D, VIA_DRILL = 0.6, 0.3
MARGIN = 0.1        # extra room for the grid's rounding


def components(board):
    """All GND copper grouped into connected pieces, biggest first.
    Each piece is a list of (kind, {layer: shape}, board item or pour piece)."""
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    g = board.FindNet("GND").GetNetCode()
    items = []
    for z in board.Zones():
        for L in LAYERS:
            if not z.IsOnLayer(L):
                continue
            P = z.GetFilledPolysList(L)
            for i in range(P.OutlineCount()):
                fr = pcbnew.SHAPE_POLY_SET(); fr.AddOutline(P.Outline(i))
                items.append(("zone", {L: fr}, fr))
    for t in board.GetTracks():
        if t.GetNetCode() != g:
            continue
        if t.GetClass() == "PCB_VIA":
            items.append(("via", {L: t.GetEffectiveShape(L) for L in LAYERS}, t))
        else:
            items.append(("track", {t.GetLayer(): t.GetEffectiveShape()}, t))
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetCode() == g:
                items.append(("pad %s.%s" % (f.GetReference(), p.GetNumber()),
                              {L: p.GetEffectiveShape(L) for L in LAYERS if p.IsOnLayer(L)}, p))
    n = len(items); par = list(range(n))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]; a = par[a]
        return a
    for i in range(n):
        for j in range(i + 1, n):
            if items[i][0] == "zone" and items[j][0] == "zone":
                continue        # two pieces of the same pour never overlap
            for L, s in items[i][1].items():  # noqa
                o = items[j][1].get(L)
                if o is None:
                    continue
                a, b = (o, s) if items[i][0] == "zone" else (s, o)   # b may be a polygon
                if (b.Collide(a, 0) if isinstance(b, pcbnew.SHAPE_POLY_SET) else a.Collide(b, 0)):
                    par[find(i)] = find(j); break
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(items[i])
    return sorted(groups.values(), key=len, reverse=True)


class Grid:
    def __init__(self, board):
        bb = board.GetBoardEdgesBoundingBox()
        self.x0, self.y0 = bb.GetLeft(), bb.GetTop()
        self.nx = int(ToMM(bb.GetWidth()) / STEP) + 1
        self.ny = int(ToMM(bb.GetHeight()) / STEP) + 1

    def to_px(self, p):
        return ((p.x - self.x0) / mm(STEP), (p.y - self.y0) / mm(STEP))

    def to_board(self, ix, iy):
        return pcbnew.VECTOR2I(self.x0 + mm(ix * STEP), self.y0 + mm(iy * STEP))

    def raster(self, prims):
        """prims: ('poly', SHAPE_POLY_SET) | ('seg', a, b, width) | ('circle', centre, radius)"""
        img = Image.new("1", (self.nx, self.ny), 0)
        d = ImageDraw.Draw(img)
        px = mm(STEP)
        for pr in prims:
            if pr[0] == "poly":
                ps = pr[1]
                for i in range(ps.OutlineCount()):
                    o = ps.Outline(i)
                    pts = [self.to_px(o.CPoint(k)) for k in range(o.PointCount())]
                    if len(pts) >= 3:
                        d.polygon(pts, fill=1, outline=1)
            elif pr[0] == "seg":
                a, b, r = self.to_px(pr[1]), self.to_px(pr[2]), pr[3] / 2 / px
                d.line([a, b], fill=1, width=max(1, int(round(2 * r))))
                for c in (a, b):
                    d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=1)
            else:
                c, r = self.to_px(pr[1]), pr[2] / px
                d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=1)
        return np.array(img, dtype=bool)


def _prim(obj, L, inflate=0.0):
    """Copper of a pad, track, via or pour piece on layer L, grown by `inflate` mm."""
    if isinstance(obj, pcbnew.SHAPE_POLY_SET):
        return ("poly", obj)
    if isinstance(obj, pcbnew.PAD):
        ps = pcbnew.SHAPE_POLY_SET(obj.GetEffectivePolygon())
        if inflate:
            ps.Inflate(mm(inflate), 16)
        return ("poly", ps)
    if obj.GetClass() == "PCB_VIA":
        return ("circle", obj.GetPosition(), obj.GetWidth() / 2 + mm(inflate))
    return ("seg", obj.GetStart(), obj.GetEnd(), obj.GetWidth() + 2 * mm(inflate))


def bridge(board, verbose=True):
    g = board.FindNet("GND")
    G = Grid(board)
    hw = TRACK_W / 2
    # where a track centre may go, and where a via may go, on each layer
    track_ok, via_free = {}, None
    for L in LAYERS:
        obs_t, obs_v = [], []
        for t in board.GetTracks():
            if t.GetNetCode() != g.GetNetCode() and t.IsOnLayer(L):
                obs_t.append(_prim(t, L, CLEAR + hw + MARGIN))
                obs_v.append(_prim(t, L, CLEAR + VIA_D / 2 + MARGIN))
        for f in board.GetFootprints():
            for p in f.Pads():
                if p.GetNetCode() != g.GetNetCode() and p.IsOnLayer(L):
                    obs_t.append(_prim(p, L, CLEAR + hw + MARGIN))
                    obs_v.append(_prim(p, L, CLEAR + VIA_D / 2 + MARGIN))
        track_ok[L] = ~G.raster(obs_t)
        vf = ~G.raster(obs_v)
        via_free = vf if via_free is None else (via_free & vf)
    # keep away from the board edge, and keep vias away from every drilled hole
    edge = int(round(0.6 / STEP))
    for L in LAYERS:
        m = track_ok[L]
        m[:edge, :] = m[-edge:, :] = False; m[:, :edge] = m[:, -edge:] = False
    via_free[:edge + 1, :] = via_free[-edge - 1:, :] = False
    via_free[:, :edge + 1] = via_free[:, -edge - 1:] = False
    img = Image.new("1", (G.nx, G.ny), 0); d = ImageDraw.Draw(img)
    holes = [(p.GetPosition(), p.GetDrillSize().x) for f in board.GetFootprints() for p in f.Pads() if p.HasHole()] + \
            [(t.GetPosition(), t.GetDrillValue()) for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    for pos, dr in holes:
        r = (ToMM(dr) / 2 + 0.3 + VIA_DRILL / 2) / STEP
        cx, cy = G.to_px(pos)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=1)
    via_free &= ~np.array(img, dtype=bool)

    added = 0
    for attempt in range(20):
        comps = components(board)
        if len(comps) == 1:
            break
        main, minors = comps[0], comps[1:]
        target = {L: G.raster([_prim(o, L) for _, s, o in main if L in s]) & track_ok[L] for L in LAYERS}
        progress = False
        for comp in minors:
            src = {L: G.raster([_prim(o, L) for _, s, o in comp if L in s]) & track_ok[L] for L in LAYERS}
            path = _search(G, src, target, track_ok, via_free)
            names = [k[4:] for k, _, _ in comp if k.startswith("pad")]
            if path is None:
                if verbose:
                    print("   no ground bridge found for", names)
                continue
            items = _draw(board, G, path, g)
            bad = _check(board, items, g)
            if bad:
                for it in items:
                    board.Remove(it)
                for li, ix, iy in bad:     # forbid that spot and try again next round
                    r = 1
                    track_ok[LAYERS[li]][max(iy - r, 0):iy + r + 1, max(ix - r, 0):ix + r + 1] = False
                    via_free[max(iy - r, 0):iy + r + 1, max(ix - r, 0):ix + r + 1] = False
                progress = True
                break
            added += len(items)
            progress = True
            if verbose:
                nv = sum(1 for it in items if it.GetClass() == "PCB_VIA")
                print("   bridged", names, "with %d track(s) and %d via(s)" % (len(items) - nv, nv))
            break           # the pours changed: recompute pieces
        if not progress:
            break
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    return added


def _search(G, src, target, track_ok, via_free, via_cost=25, margin=12.0):
    """Dijkstra from any source cell to any target cell. Returns [(layer_index, ix, iy), ...]."""
    ys, xs = np.nonzero(src[LAYERS[0]] | src[LAYERS[1]])
    if len(xs) == 0:
        return None
    pad = int(margin / STEP)
    x_lo, x_hi = max(xs.min() - pad, 0), min(xs.max() + pad, G.nx - 1)
    y_lo, y_hi = max(ys.min() - pad, 0), min(ys.max() + pad, G.ny - 1)
    dist, prev, pq = {}, {}, []
    for li, L in enumerate(LAYERS):
        for iy, ix in zip(*np.nonzero(src[L])):
            st = (li, int(ix), int(iy)); dist[st] = 0.0; heapq.heappush(pq, (0.0, st))
    moves = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
             (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
    while pq:
        dcur, st = heapq.heappop(pq)
        if dcur > dist.get(st, 1e18):
            continue
        li, ix, iy = st
        L = LAYERS[li]
        if target[L][iy, ix] and dcur > 0:
            path = [st]
            while path[-1] in prev:
                path.append(prev[path[-1]])
            return path[::-1]
        nbrs = []
        for dx, dy, c in moves:
            jx, jy = ix + dx, iy + dy
            if x_lo <= jx <= x_hi and y_lo <= jy <= y_hi and track_ok[L][jy, jx]:
                if dx and dy and not (track_ok[L][iy, jx] and track_ok[L][jy, ix]):
                    continue        # no corner cutting past an obstacle
                nbrs.append(((li, jx, jy), c))
        if via_free[iy, ix] and track_ok[LAYERS[1 - li]][iy, ix]:
            nbrs.append(((1 - li, ix, iy), via_cost))
        for nst, c in nbrs:
            nd = dcur + c
            if nd < dist.get(nst, 1e18):
                dist[nst] = nd; prev[nst] = st; heapq.heappush(pq, (nd, nst))
    return None


def _check(board, items, net):
    """KiCad's exact geometry has the final word: grid cells of any new item
    that is too close to other copper or to a drilled hole."""
    bad = []
    for it in items:
        for li, L in enumerate(LAYERS):
            if not it.IsOnLayer(L):
                continue
            mine = it.GetEffectiveShape(L) if it.GetClass() == "PCB_VIA" else it.GetEffectiveShape()
            for t in board.GetTracks():
                if t.GetNetCode() != net.GetNetCode() and t.IsOnLayer(L):
                    if mine.Collide(t.GetEffectiveShape(L) if t.GetClass() == "PCB_VIA" else t.GetEffectiveShape(), mm(CLEAR)):
                        bad.append((li, it))
            for f in board.GetFootprints():
                for p in f.Pads():
                    if p.GetNetCode() != net.GetNetCode() and p.IsOnLayer(L) and mine.Collide(p.GetEffectiveShape(L), mm(CLEAR)):
                        bad.append((li, it))
        if it.GetClass() == "PCB_VIA":
            others = [h for f in board.GetFootprints() for h in f.Pads() if h.HasHole()] + \
                     [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t is not it and t.m_Uuid.AsString() != it.m_Uuid.AsString()]
            for h in others:
                dr = h.GetDrillSize().x if isinstance(h, pcbnew.PAD) else h.GetDrillValue()
                if (h.GetPosition() - it.GetPosition()).EuclideanNorm() < (dr + it.GetDrillValue()) / 2 + mm(0.3):
                    bad.append((0, it))
    out = []
    G = Grid(board)
    for li, it in bad:
        pos = it.GetPosition() if it.GetClass() == "PCB_VIA" else it.GetStart()
        ix, iy = [int(round(v)) for v in G.to_px(pos)]
        out.append((li, ix, iy))
        if it.GetClass() != "PCB_VIA":       # the whole run is suspect
            a, b = G.to_px(it.GetStart()), G.to_px(it.GetEnd())
            n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1]))) + 1
            for k in range(n + 1):
                out.append((li, int(round(a[0] + (b[0] - a[0]) * k / n)), int(round(a[1] + (b[1] - a[1]) * k / n))))
    return out


def _draw(board, G, path, net):
    """Turn the grid path into tracks (merging straight runs) and vias.
    Returns the new board items."""
    new = []
    runs, cur = [], [path[0]]
    for st in path[1:]:
        if st[0] != cur[-1][0]:
            runs.append(cur); cur = [st]
        else:
            cur.append(st)
    runs.append(cur)
    for k, run in enumerate(runs):
        L = LAYERS[run[0][0]]
        pts = [run[0]]
        for a, b, c in zip(run, run[1:], run[2:]):
            if (b[1] - a[1], b[2] - a[2]) != (c[1] - b[1], c[2] - b[2]):
                pts.append(b)
        pts.append(run[-1])
        for a, b in zip(pts, pts[1:]):
            if a == b:
                continue
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(G.to_board(a[1], a[2])); t.SetEnd(G.to_board(b[1], b[2]))
            t.SetWidth(mm(TRACK_W)); t.SetLayer(L); t.SetNet(net); board.Add(t); new.append(t)
        if k + 1 < len(runs):
            v = pcbnew.PCB_VIA(board); v.SetPosition(G.to_board(run[-1][1], run[-1][2]))
            v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL)); v.SetNet(net); board.Add(v); new.append(v)
    return new
