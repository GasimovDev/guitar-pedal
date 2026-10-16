"""
The whole pedal circuit as data. Both the schematic and the PCB are generated
from this one file, so they can never disagree.

Each part: ref, lib symbol, value, footprint, {pin number: net}, extra fields,
schematic section, and PCB placement (x, y in mm from the board's top-left
corner as seen from the TOP, rotation in degrees, side 'T' or 'B').
"""

R0805 = "Resistor_SMD:R_0805_2012Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"

parts = []

def part(ref, lib, value, fp, pins, section, pos=None, mpn="", desc="", **kw):
    parts.append(dict(ref=ref, lib=lib, value=value, fp=fp, pins=pins,
                      section=section, pos=pos, mpn=mpn, desc=desc, **kw))

def R(ref, value, a, b, section, pos=None, desc=""):
    part(ref, "Device:R", value, R0805, {"1": a, "2": b}, section, pos,
         mpn="0805 %s 1%%" % value, desc=desc or "Resistor 0805 1%")

def C(ref, value, a, b, section, pos=None, fp=C0805, desc="", mpn=None):
    v = value.replace("u", "µ") if False else value
    part(ref, "Device:C", v, fp, {"1": a, "2": b}, section, pos,
         mpn=mpn or ("0805 %s X7R" % value if fp == C0805 else "1206 %s X7R" % value),
         desc=desc or "Ceramic capacitor")

# ---------------------------------------------------------------- POWER
S = "power"
part("J1", "Connector_Generic:Conn_01x02", "9V_DC_IN", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
     {"1": "+9V_IN", "2": "GND"}, S, mpn="2.54mm header 1x2",
     desc="Wire to a 2.1 mm DC jack: sleeve -> pin 1 (+9V), centre pin -> pin 2 (GND). Pedal standard = centre negative.")
part("D1", "Device:D_Schottky", "SS34", "Diode_SMD:D_SMA", {"1": "+9V", "2": "+9V_IN"}, S,
     mpn="SS34", desc="Reverse polarity protection: blocks current if the adapter is wrong")
part("C1", "Device:C_Polarized", "100uF 25V", "Capacitor_SMD:CP_Elec_6.3x7.7", {"1": "+9V", "2": "GND"}, S,
     mpn="100uF 25V SMD electrolytic 6.3x7.7", desc="Bulk supply reservoir")
C("C2", "100nF", "+9V", "GND", S)
part("U1", "Regulator_Linear:LM78M05_TO252", "L78M05", "Package_TO_SOT_SMD:TO-252-2",
     {"1": "+9V", "2": "GND", "3": "+5V"}, S, mpn="L78M05CDT-TR", desc="9 V -> 5 V regulator, 500 mA")
C("C3", "1uF", "+9V", "GND", S, desc="Regulator input cap")
C("C4", "10uF", "+5V", "GND", S, desc="Regulator output cap")
C("C5", "100nF", "+5V", "GND", S)
part("D2", "Device:D_Schottky", "SS14", "Diode_SMD:D_SMA", {"1": "+5V_MCU", "2": "+5V"}, S,
     mpn="SS14", desc="Feeds the Black Pill 5V pin. Stops USB power flowing back into our 5 V rail")
part("U2", "Regulator_Linear:AP2112K-3.3", "AP2112K-3.3", "Package_TO_SOT_SMD:SOT-23-5",
     {"1": "+5V", "2": "GND", "3": "+5V", "4": None, "5": "+3V3A"}, S,
     mpn="AP2112K-3.3TRG1", desc="5 V -> 3.3 V clean supply for the audio converters")
C("C6", "1uF", "+5V", "GND", S)
C("C7", "10uF", "+3V3A", "GND", S)
part("FB1", "Device:FerriteBead", "600R@100MHz", "Inductor_SMD:L_0805_2012Metric", {"1": "+5V", "2": "+5VA"}, S,
     mpn="BLM21PG601SN1D", desc="Ferrite bead: keeps digital noise off the ADC's analog 5 V")
R("R1", "10k", "+9V", "VBIAS", S, desc="Bias divider top")
R("R2", "10k", "VBIAS", "GND", S, desc="Bias divider bottom")
part("C8", "Device:C_Polarized", "47uF 25V", "Capacitor_SMD:CP_Elec_6.3x5.4", {"1": "VBIAS", "2": "GND"}, S,
     mpn="47uF 25V SMD electrolytic 6.3x5.4", desc="Makes VBIAS a quiet 'AC ground' at half supply")
part("PF1", "power:PWR_FLAG", "PWR_FLAG", None, {"1": "+9V"}, S)
part("PF2", "power:PWR_FLAG", "PWR_FLAG", None, {"1": "GND"}, S)
part("PF3", "power:PWR_FLAG", "PWR_FLAG", None, {"1": "+5VA"}, S)
part("PF4", "power:PWR_FLAG", "PWR_FLAG", None, {"1": "+9V_IN"}, S)
part("PF5", "power:PWR_FLAG", "PWR_FLAG", None, {"1": "+5V_MCU"}, S)
part("PF6", "power:PWR_FLAG", "PWR_FLAG", None, {"1": "+3V3_MCU"}, S)

# ---------------------------------------------------------------- INPUT STAGE
S = "input"
part("J2", "Connector_Generic:Conn_01x02", "GUITAR_IN", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
     {"1": "IN_TIP", "2": "GND"}, S, mpn="2.54mm header 1x2", desc="Wire to the input jack: tip -> 1, sleeve -> 2")
R("R3", "1M", "IN_TIP", "GND", S, desc="Pull-down: stops a 'pop' when you plug in")
C("C9", "100nF", "IN_TIP", "IN_AC", S, desc="Blocks DC from the guitar side")
R("R4", "1k", "IN_AC", "IN_P", S, desc="With C10: filters radio interference")
C("C10", "100pF", "IN_P", "GND", S, mpn="0805 100pF C0G")
R("R5", "1M", "VBIAS", "IN_P", S, desc="Biases the op-amp input to VBIAS; 1 MOhm = what a guitar wants to see")
part("U3", "Amplifier_Operational:OPA1678", "OPA1678", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
     {"1": "IN_BUF", "2": "IN_FB", "3": "IN_P", "5": "OUT_P", "6": "OUT_BUF", "7": "OUT_BUF", "4": "GND", "8": "+9V"},
     "input", mpn="OPA1678IDR", desc="Dual audio op-amp, rail-to-rail output. NE5532 fits too (same pins, works on 9 V)")
R("R6", "5.1k", "IN_BUF", "IN_FB", S, desc="Gain = 1 + R6/R7 = 1.51 (+3.6 dB)")
C("C11", "100pF", "IN_BUF", "IN_FB", S, mpn="0805 100pF C0G", desc="Rolls off gain above 300 kHz (stability)")
R("R7", "10k", "IN_FB", "IN_G", S)
C("C12", "10uF", "IN_G", "GND", S, desc="Gain only for AC: at DC the stage is a follower and stays at VBIAS")
R("R8", "1k", "IN_BUF", "ADC_AA", S, desc="Anti-alias filter R (72 kHz with C13)")
C("C13", "2.2nF", "ADC_AA", "GND", S, mpn="0805 2.2nF C0G")
C("C14", "10uF", "ADC_AA", "ADC_VINL", S, desc="Blocks VBIAS (4.3 V) from the ADC, which centres itself at 2.5 V")
C("C15", "1uF", "ADC_VINR", "GND", S, desc="Unused right ADC input: AC-grounded so it stays quiet")

# ---------------------------------------------------------------- ADC
S = "adc"
part("U4", "pedal:PCM1808PW", "PCM1808", "Package_SO:TSSOP-14_4.4x5mm_P0.65mm",
     {"1": "ADC_VREF", "2": "GND", "3": "+5VA", "4": "+3V3A", "5": "GND", "6": "MCLK", "7": "LRCK",
      "8": "BCK", "9": "ADC_DOUT", "10": "GND", "11": "GND", "12": "GND", "13": "ADC_VINL", "14": "ADC_VINR"},
     S, mpn="PCM1808PWR", desc="24-bit stereo ADC. MD0=MD1=0: slave mode. FMT=0: I2S")
C("C16", "10uF", "ADC_VREF", "GND", S, desc="ADC reference decoupling (datasheet: 10uF + 0.1uF)")
C("C17", "100nF", "ADC_VREF", "GND", S)
C("C18", "10uF", "+5VA", "GND", S)
C("C19", "100nF", "+5VA", "GND", S)
C("C20", "100nF", "+3V3A", "GND", S)

# ---------------------------------------------------------------- DAC
S = "dac"
part("U5", "Audio:PCM5102A", "PCM5102A", "Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm",
     {"1": "+3V3A", "2": "DAC_CAPP", "3": "GND", "4": "DAC_CAPM", "5": "DAC_VNEG", "6": "DAC_OUTL",
      "7": None, "8": "+3V3A", "9": "GND", "10": "GND", "11": "GND", "12": "MCLK", "13": "BCK",
      "14": "DAC_DIN", "15": "LRCK", "16": "GND", "17": "DAC_XSMT", "18": "DAC_LDOO", "19": "GND", "20": "+3V3A"},
     S, mpn="PCM5102APWR", desc="32-bit stereo DAC with built-in negative charge pump: output centred on 0 V")
C("C21", "2.2uF", "DAC_CAPP", "DAC_CAPM", S, desc="Charge-pump flying cap")
C("C22", "2.2uF", "DAC_VNEG", "GND", S, desc="Charge-pump output (-3.3 V)")
C("C23", "1uF", "DAC_LDOO", "GND", S, desc="Internal 1.8 V regulator decoupling")
C("C24", "10uF", "+3V3A", "GND", S)
C("C25", "100nF", "+3V3A", "GND", S, desc="AVDD decoupling")
C("C26", "100nF", "+3V3A", "GND", S, desc="CPVDD decoupling")
C("C27", "100nF", "+3V3A", "GND", S, desc="DVDD decoupling")
R("R9", "10k", "DAC_XSMT", "GND", S, desc="Keeps the DAC muted until the MCU says go (no power-on pop)")

# ---------------------------------------------------------------- OUTPUT STAGE
S = "output"
R("R10", "470", "DAC_OUTL", "DAC_F", S, desc="DAC output filter (datasheet: 470 Ohm + 2.2 nF)")
C("C28", "2.2nF", "DAC_F", "GND", S, mpn="0805 2.2nF C0G")
C("C29", "10uF", "DAC_F", "OUT_AC", S, desc="Blocks DC between the 0 V DAC and the 4.3 V op-amp")
R("R11", "22k", "OUT_AC", "OUT_P", S, desc="Attenuator: 10k/(22k+10k) = 0.31, full scale 3 V peak -> 0.93 V peak")
R("R12", "10k", "OUT_P", "VBIAS", S, desc="Bottom of attenuator, also biases the op-amp to VBIAS")
C("C30", "10uF", "OUT_BUF", "OUT_AC2", S, desc="Blocks VBIAS from the output jack")
R("R13", "100k", "OUT_AC2", "GND", S, desc="Pull-down: keeps the jack at 0 V DC (no pop)")
R("R14", "1k", "OUT_AC2", "OUT_TIP", S, desc="Protects the op-amp from shorts and long cables")
part("J3", "Connector_Generic:Conn_01x02", "OUT", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
     {"1": "OUT_TIP", "2": "GND"}, S, mpn="2.54mm header 1x2", desc="Wire to the output jack: tip -> 1, sleeve -> 2")
C("C31", "100nF", "+9V", "GND", S, desc="Op-amp supply decoupling")
C("C32", "10uF", "+9V", "GND", S)

# ---------------------------------------------------------------- MCU
S = "mcu"
BP_A = ["5V", "GND", "3V3", "PB10", "PB2", "PB1", "PB0", "PA7", "PA6", "PA5", "PA4", "PA3", "PA2", "PA1",
        "PA0", "NRST", "PC15", "PC14", "PC13", "VBAT"]
BP_B = ["PB12", "PB13", "PB14", "PB15", "PA8", "PA9", "PA10", "PA11", "PA12", "PA15", "PB3", "PB4", "PB5",
        "PB6", "PB7", "PB8", "PB9", "5V", "GND", "3V3"]
bp_net = {"5V": "+5V_MCU", "GND": "GND", "3V3": "+3V3_MCU",
          "PB10": "LED3", "PB1": "LED2", "PB0": "LED1",
          "PA7": "K6", "PA6": "K5", "PA5": "K4", "PA4": "K3", "PA2": "K2", "PA1": "K1",
          "PA3": "MCU_MCLK", "PB12": "MCU_LRCK", "PB13": "MCU_BCK", "PB14": "ADC_DOUT", "PB15": "MCU_DIN",
          "PA9": "UART_TX", "PA10": "UART_RX", "PB6": "FSW1", "PB7": "FSW2", "PB8": "FSW3", "PB9": "DAC_XSMT"}
bp_pins = {}
for i, n in enumerate(BP_A):
    bp_pins[str(i + 1)] = bp_net.get(n)
for i, n in enumerate(BP_B):
    bp_pins[str(i + 21)] = bp_net.get(n)
part("U6", "pedal:BlackPill_F411", "WeAct BlackPill STM32F411CEU6", "pedal:BlackPill_Sockets",
     bp_pins, S, mpn="WeAct BlackPill V3.0 STM32F411CEU6 (25 MHz HSE)",
     desc="Plugs into two 1x20 female headers. Not assembled by the factory - you buy and plug it")
R("R15", "33", "MCU_MCLK", "MCLK", S, desc="Series resistors on fast clock lines: soften edges, less ringing/noise")
R("R16", "33", "MCU_BCK", "BCK", S)
R("R17", "33", "MCU_LRCK", "LRCK", S)
R("R18", "33", "MCU_DIN", "DAC_DIN", S)
part("J5", "Connector_Generic:Conn_01x03", "UART", "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
     {"1": "UART_TX", "2": "UART_RX", "3": "GND"}, S, mpn="2.54mm header 1x3",
     desc="Debug serial port: connect a USB-serial adapter (its RX to pin 1)")

# ---------------------------------------------------------------- CONTROLS
S = "controls"
knob_names = ["DRIVE", "TONE", "RATE", "DEPTH", "TIME", "REPEATS"]
for i in range(6):
    n = i + 1
    part("RV%d" % n, "Device:R_Potentiometer", "B10k " + knob_names[i],
         "Potentiometer_THT:Potentiometer_Alpha_RD901F-40-00D_Single_Vertical",
         {"1": "GND", "2": "POT%d" % n, "3": "+3V3_MCU"}, S, mpn="Alpha RD901F-40 9mm B10K linear",
         desc="Knob %s. CCW end to GND, CW end to 3.3 V" % knob_names[i])
    R("R%d" % (18 + n), "1k", "POT%d" % n, "K%d" % n, S, desc="Knob filter R")
    C("C%d" % (32 + n), "100nF", "K%d" % n, "GND", S, desc="Knob filter C: steadies the ADC reading")
part("J6", "Connector_Generic:Conn_01x04", "FOOTSWITCHES", "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
     {"1": "FSW1_EXT", "2": "FSW2_EXT", "3": "FSW3_EXT", "4": "GND"}, S, mpn="2.54mm header 1x4",
     desc="Three momentary (soft-touch) SPST footswitches: each one between pin 1/2/3 and pin 4 (GND)")
for i in range(3):
    n = i + 1
    R("R%d" % (24 + n), "1k", "FSW%d_EXT" % n, "FSW%d" % n, S, desc="Protects the MCU pin from static on the switch wire")
    C("C%d" % (38 + n), "100nF", "FSW%d" % n, "GND", S, desc="Hardware debounce + noise filter")
led_names = ["OD", "TREM", "DELAY"]
led_cols = ["red", "yellow", "green"]
for i in range(3):
    n = i + 1
    R("R%d" % (27 + n), "470", "LED%d" % n, "LED%d_A" % n, S, desc="LED current limit: (3.3-2.0)/470 = 2.8 mA")
    part("D%d" % (2 + n), "Device:LED", "LED %s %s" % (led_names[i], led_cols[i]), "LED_THT:LED_D3.0mm",
         {"1": "GND", "2": "LED%d_A" % n}, S, mpn="3mm %s LED, diffused" % led_cols[i],
         desc="Status LED for %s" % led_names[i])

# ---------------------------------------------------------------- TEST POINTS
S = "test"
tps = [("TP1", "+9V"), ("TP2", "+5V"), ("TP3", "+3V3A"), ("TP4", "VBIAS"), ("TP5", "GND"), ("TP6", "GND"),
       ("TP7", "MCLK"), ("TP8", "BCK"), ("TP9", "LRCK"), ("TP10", "IN_BUF"), ("TP11", "DAC_OUTL"), ("TP12", "OUT_BUF")]
for ref, net in tps:
    part(ref, "Connector:TestPoint", net, "TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm", {"1": net}, S,
         mpn="(no part - bare pad, probe here)", desc="Measure here with the multimeter or scope")

# Factory assembles every SMD part. You solder only these by hand:
HAND_SOLDER = {"J1", "J2", "J3", "J5", "J6", "U6", "D3", "D4", "D5", "RV1", "RV2", "RV3", "RV4", "RV5", "RV6"}

sections = [
    ("power", "POWER: 9 V in -> protection -> 5 V, 3.3 V and VBIAS (4.3 V)"),
    ("input", "INPUT: guitar -> 1 MOhm buffer (x1.5) -> anti-alias filter -> ADC"),
    ("adc", "ADC: PCM1808 turns the analog signal into numbers (I2S)"),
    ("dac", "DAC: PCM5102A turns numbers back into an analog signal"),
    ("output", "OUTPUT: DAC -> filter -> attenuator -> buffer -> output jack"),
    ("mcu", "MCU: STM32F411 Black Pill runs the effects"),
    ("controls", "CONTROLS: 6 knobs, 3 footswitches, 3 LEDs"),
    ("test", "TEST POINTS and mounting holes"),
]


def nets():
    s = set()
    for p in parts:
        for n in p["pins"].values():
            if n: s.add(n)
    return sorted(s)
