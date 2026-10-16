"""Write pedal.kicad_pro: design rules (safe for JLCPCB/PCBWay 2-layer) and net classes."""
import json, os
HW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

def nc(name, width, clearance=0.2):
    return {"name": name, "clearance": clearance, "track_width": width, "via_diameter": 0.6, "via_drill": 0.3,
            "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_width": 0.2, "diff_pair_gap": 0.25,
            "diff_pair_via_gap": 0.25, "wire_width": 6, "bus_width": 12, "line_style": 0,
            "schematic_color": "rgba(0, 0, 0, 0.000)", "pcb_color": "rgba(0, 0, 0, 0.000)"}

pro = {
    "board": {
        "design_settings": {
            "defaults": {"board_outline_line_width": 0.1, "copper_line_width": 0.2, "silk_line_width": 0.12,
                         "silk_text_size_h": 1.0, "silk_text_size_v": 1.0, "silk_text_thickness": 0.15},
            "rules": {"min_clearance": 0.2, "min_track_width": 0.15, "min_via_diameter": 0.5,
                      "min_via_annular_width": 0.1, "min_through_hole_diameter": 0.3,
                      "min_hole_clearance": 0.25, "min_hole_to_hole": 0.25, "min_copper_edge_clearance": 0.3,
                      "min_silk_clearance": 0.0, "min_text_height": 0.6, "min_text_thickness": 0.1,
                      "solder_mask_clearance": 0.0, "solder_mask_min_width": 0.0},
            "track_widths": [0.0, 0.25, 0.4, 0.6],
            "via_dimensions": [{"diameter": 0.0, "drill": 0.0}, {"diameter": 0.6, "drill": 0.3}],
            "rule_severities": {"silk_overlap": "ignore", "silk_over_copper": "ignore",
                                "silk_edge_clearance": "ignore", "text_height": "warning",
                                "courtyards_overlap": "warning", "starved_thermal": "warning", "lib_footprint_issues": "ignore",
                                "lib_footprint_mismatch": "ignore"},
        },
    },
    "net_settings": {
        "classes": [nc("Default", 0.25), nc("Power", 0.6), nc("Supply", 0.35), nc("Audio", 0.3)],
        "meta": {"version": 3},
        "netclass_patterns": [{"netclass": "Power", "pattern": p} for p in
                              ["+9V*", "+5V", "+5V_MCU", "GND"]] +
                             [{"netclass": "Supply", "pattern": p} for p in ["+5VA", "+3V3A", "+3V3_MCU"]] +
                             [{"netclass": "Audio", "pattern": p} for p in
                              ["IN_*", "OUT_*", "DAC_OUTL", "DAC_F", "ADC_*", "VBIAS"]],
    },
    "meta": {"filename": "pedal.kicad_pro", "version": 1},
    "sheets": [],
}
json.dump(pro, open(os.path.join(HW, "pedal.kicad_pro"), "w"), indent=2)
