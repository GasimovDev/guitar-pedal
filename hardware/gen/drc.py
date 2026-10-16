"""Run KiCad's design-rule check on pedal.kicad_pcb and summarise it."""
import pcbnew, os, re, sys, collections
HW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
b = pcbnew.LoadBoard(os.path.join(HW, "pedal.kicad_pcb"))
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
rpt = os.path.join(HW, "drc_report.txt")
pcbnew.WriteDRCReport(b, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
txt = open(rpt).read()
kinds = collections.Counter(re.findall(r"^\[(\w+)\]", txt, re.M))
print(re.findall(r"\*\* Found \d+ [^*]*\*\*", txt))
for k, v in kinds.most_common(): print("  %-28s %d" % (k, v))
