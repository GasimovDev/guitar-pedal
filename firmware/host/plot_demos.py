"""Plot the demo renders in out/ so you can SEE what each effect does -> out/demos.png"""
import wave, numpy as np, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

os.chdir(os.path.dirname(os.path.abspath(__file__)))
def load(name):
    w = wave.open("out/%s.wav" % name)
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16) / 32768.0
    return x, w.getframerate()

names = [("00_dry", "Dry guitar (synthetic riff)"), ("01_overdrive", "Overdrive: clipped, louder, more sustain"),
         ("02_tremolo", "Tremolo: volume pulses at RATE"), ("03_delay", "Delay: echoes every TIME ms"),
         ("04_all_three", "All three")]
fig, ax = plt.subplots(len(names) + 1, 1, figsize=(10, 13))
for a, (n, title) in zip(ax, names):
    x, fs = load(n)
    t = np.arange(len(x)) / fs
    a.plot(t, x, lw=0.3); a.set_title(title, fontsize=10); a.set_ylim(-1, 1); a.set_xlim(0, t[-1])
    a.set_ylabel("level")
x, fs = load("00_dry"); y, _ = load("01_overdrive")
i0, i1 = int(0.30 * fs), int(0.33 * fs)
t = np.arange(i1 - i0) / fs * 1000
ax[-1].plot(t, x[i0:i1], label="dry"); ax[-1].plot(t, y[i0:i1], label="overdrive")
ax[-1].set_title("Zoom (30 ms): overdrive squashes the peaks = new harmonics", fontsize=10)
ax[-1].set_xlabel("ms"); ax[-1].legend()
ax[-2].set_xlabel("seconds")
plt.tight_layout(); plt.savefig("out/demos.png", dpi=100)
print("wrote out/demos.png")
