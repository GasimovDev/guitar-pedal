"""Run analog.cir in ngspice and plot frequency response + waveforms -> analog_sim.png"""
import subprocess, numpy as np, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

os.chdir(os.path.dirname(os.path.abspath(__file__)))
log = subprocess.run(["ngspice", "-b", "analog.cir"], capture_output=True, text=True).stdout
open("analog_sim.log", "w").write(log)

ai = np.loadtxt("ac_in.txt"); ao = np.loadtxt("ac_out.txt"); tr = np.loadtxt("tran.txt")
f, gin, gout = ai[:, 0], ai[:, 1], ao[:, 1]

def corner(f, g, ref):
    lo = f[np.argmax(g > ref - 3)]
    hi = f[len(g) - 1 - np.argmax(g[::-1] > ref - 3)]
    return lo, hi

mid_in = gin[np.argmin(abs(f - 1000))]; mid_out = gout[np.argmin(abs(f - 1000))]
li, hi_ = corner(f, gin, mid_in); lo, ho = corner(f, gout, mid_out)
print("input stage : %.2f dB at 1 kHz (x%.2f), -3 dB at %.1f Hz and %.0f Hz" % (mid_in, 10 ** (mid_in / 20), li, hi_))
print("output stage: %.2f dB at 1 kHz (x%.3f), -3 dB at %.1f Hz and %.0f Hz" % (mid_out, 10 ** (mid_out / 20), lo, ho))

fig, ax = plt.subplots(2, 1, figsize=(9, 8))
ax[0].semilogx(f, gin, label="guitar -> ADC input (gain %.1f dB)" % mid_in)
ax[0].semilogx(f, gout, label="DAC -> output jack (gain %.1f dB)" % mid_out)
ax[0].axvspan(20, 20000, color="0.92", label="audio band 20 Hz - 20 kHz")
ax[0].set_xlabel("frequency (Hz)"); ax[0].set_ylabel("gain (dB)"); ax[0].set_ylim(-40, 10)
ax[0].grid(True, which="both", alpha=0.3); ax[0].legend(); ax[0].set_title("Frequency response (ngspice)")
t = (tr[:, 0] - tr[0, 0]) * 1000
ax[1].plot(t, tr[:, 1], label="guitar, 1 V peak (hard strum)")
ax[1].plot(t, tr[:, 3], label="buffer output, centred on VBIAS 4.3 V")
ax[1].plot(t, tr[:, 5], label="ADC pin, centred on 2.5 V")
ax[1].plot(t, tr[:, 11], label="output jack (DAC at full scale)")
ax[1].axhline(2.5 + 1.5, ls=":", c="k", lw=0.8); ax[1].axhline(2.5 - 1.5, ls=":", c="k", lw=0.8)
ax[1].text(0.2, 4.05, "ADC full scale (2.5 V +- 1.5 V)", fontsize=8)
ax[1].set_xlabel("time (ms)"); ax[1].set_ylabel("volts"); ax[1].set_xlim(0, 3); ax[1].set_ylim(-1.5, 6.5)
ax[1].grid(alpha=0.3); ax[1].legend(fontsize=8, loc="lower right")
plt.tight_layout(); plt.savefig("analog_sim.png", dpi=110)
for k in ("ac_in.txt", "ac_out.txt", "tran.txt"):
    os.remove(k)
