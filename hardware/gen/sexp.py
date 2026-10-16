"""Tiny S-expression reader/writer for KiCad files, plus a symbol-library helper."""
import re, copy

class Sym(str):
    """An unquoted atom (KiCad keyword or number)."""

_tok = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)

def parse(text):
    stack, cur = [], []
    pos = 0
    n = len(text)
    while pos < n:
        m = _tok.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise ValueError("parse error at %d" % pos)
        pos = m.end()
        if m.group(1):
            stack.append(cur); cur = []
        elif m.group(2):
            done = cur; cur = stack.pop(); cur.append(done)
        elif m.group(3) is not None:
            cur.append(m.group(3).replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\'))
        else:
            cur.append(Sym(m.group(4)))
    return cur[0] if len(cur) == 1 else cur

def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'

def dump(e, ind=0):
    if isinstance(e, list):
        if not e:
            return "()"
        simple = all(not isinstance(x, list) for x in e)
        if simple:
            return "(" + " ".join(dump(x) for x in e) + ")"
        out = "(" + dump(e[0])
        for x in e[1:]:
            if isinstance(x, list):
                out += "\n" + "  " * (ind + 1) + dump(x, ind + 1)
            else:
                out += " " + dump(x)
        return out + ")"
    if isinstance(e, Sym):
        return str(e)
    if isinstance(e, (int,)):
        return str(e)
    if isinstance(e, float):
        s = ("%.4f" % e).rstrip("0").rstrip(".")
        return s if s not in ("-0", "") else "0"
    return q(e)

def find(e, key):
    for x in e:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None

def findall(e, key):
    return [x for x in e if isinstance(x, list) and x and x[0] == key]


LIBDIR = "/usr/share/kicad/symbols"
_libcache = {}

def _lib(name, extra=None):
    if name not in _libcache:
        path = extra.get(name) if extra and name in extra else "%s/%s.kicad_sym" % (LIBDIR, name)
        _libcache[name] = parse(open(path).read())
    return _libcache[name]

def load_symbol(lib_id, extra_libs=None):
    """Return a flattened symbol S-expr named 'Lib:Name' ready for lib_symbols."""
    lib, name = lib_id.split(":")
    L = _lib(lib, extra_libs)
    sym = None
    for s in findall(L, "symbol"):
        if s[1] == name:
            sym = copy.deepcopy(s); break
    if sym is None:
        raise KeyError(lib_id)
    ext = find(sym, "extends")
    if ext:
        base = load_symbol(lib + ":" + ext[1], extra_libs)
        bname = base[1].split(":")[1]
        # derived = base graphics/pins + derived properties
        props = {p[1]: p for p in findall(sym, "property")}
        new = [Sym("symbol"), name]
        for x in base[2:]:
            if isinstance(x, list) and x[0] == "property" and x[1] in props:
                new.append(props.pop(x[1]))
            elif isinstance(x, list) and x[0] == "symbol":
                y = copy.deepcopy(x)
                y[1] = y[1].replace(bname + "_", name + "_", 1)
                new.append(y)
            else:
                new.append(x)
        for p in props.values():
            new.append(p)
        sym = new
    sym[1] = lib + ":" + name if ":" not in sym[1] else sym[1]
    return sym

def symbol_pins(sym):
    """[(unit, number, name, x, y, angle, etype)] in symbol coords (Y up)."""
    name = sym[1].split(":")[-1]
    pins = []
    for sub in findall(sym, "symbol"):
        m = re.match(r"(.*)_(\d+)_(\d+)$", sub[1])
        unit = int(m.group(2))
        for p in findall(sub, "pin"):
            at = find(p, "at")
            num = find(p, "number")[1]
            nm = find(p, "name")[1]
            pins.append((unit, num, nm, float(at[1]), float(at[2]), int(float(at[3])) if len(at) > 3 else 0, str(p[1])))
    return pins

def unit_count(sym):
    units = set()
    for sub in findall(sym, "symbol"):
        m = re.match(r"(.*)_(\d+)_(\d+)$", sub[1])
        u = int(m.group(2))
        if u > 0: units.add(u)
    return max(units) if units else 1
