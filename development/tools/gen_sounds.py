#!/usr/bin/env python3
"""Before the Thaw - procedural sound generator.

All sounds are synthesised here (no recordings, no third-party samples) and
written as GoldSrc-friendly WAV: PCM 16-bit mono 22050 Hz.  Looping ambiences
get a 'cue ' chunk, which is what GoldSrc / Xash3D use as the loop point
(without it an ambient_generic plays once and stops).

The file names under player/, doors/, buttons/, common/ are the names the
HLSDK-based game code asks for (e.g. func_door "movesnd 1" ->
doors/doormove1.wav); the content is ours.

Usage: python3 development/tools/gen_sounds.py
"""
import os
import struct
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "game", "sound")
SR = 22050
R = np.random.default_rng(1999)


def t(sec):
    return np.arange(int(sec * SR)) / SR


def lp_fast(x, cutoff):
    """FFT brick-ish lowpass (fast for long buffers, circular = loop friendly)."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (f / cutoff) ** 4)
    return np.fft.irfft(X, len(x))


def bp_fast(x, lo, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= (1 / (1 + (lo / np.maximum(f, 1)) ** 4)) * (1 / (1 + (f / hi) ** 4))
    return np.fft.irfft(X, len(x))


def env(n, attack, decay):
    a = int(attack * SR)
    e = np.exp(-np.arange(n) / (decay * SR))
    if a:
        e[:a] *= np.linspace(0, 1, a)
    return e


def norm(x, peak=0.8):
    m = np.max(np.abs(x)) or 1
    return x / m * peak


def loopify(x, fade=0.25):
    """Crossfade the tail into the head so the loop has no click."""
    n = int(fade * SR)
    head, tail = x[:n].copy(), x[-n:].copy()
    w = np.linspace(0, 1, n)
    x = x[:-n].copy()
    x[:n] = head * w + tail * (1 - w)
    return x


def write(name, x, loop=False, peak=0.8):
    x = norm(x, peak)
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()
    fmt = struct.pack("<HHIIHH", 1, 1, SR, SR * 2, 2, 16)
    chunks = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    chunks += b"data" + struct.pack("<I", len(pcm)) + pcm
    if len(pcm) % 2:
        chunks += b"\0"
    if loop:
        # one cue point at sample 0 -> loop the whole file
        cue = struct.pack("<I", 1) + struct.pack("<II4sIII", 1, 0, b"data", 0, 0, 0)
        chunks += b"cue " + struct.pack("<I", len(cue)) + cue
    data = b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WAVE" + chunks
    path = os.path.join(OUT, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fp:
        fp.write(data)
    return name


# ------------------------------------------------------------------ ambiences
def wind_house():
    # wind heard from inside a log house: muffled, low, slow gusts, a whistle
    d = 12.0
    n = R.standard_normal(int(d * SR))
    base = lp_fast(n, 260)
    gust = lp_fast(R.standard_normal(len(n)), 0.35)
    gust = 0.45 + 0.55 * (gust - gust.min()) / (np.ptp(gust) or 1)
    whistle = bp_fast(R.standard_normal(len(n)), 700, 900) * np.clip(gust - 0.7, 0, 1) * 2.5
    x = base * gust + whistle * 0.25
    return loopify(x, 1.0)


def clock_tick():
    # ходики: tick - tock, two per second
    x = np.zeros(int(1.0 * SR))
    for k, (pos, f) in enumerate(((0.0, 2600), (0.5, 2100))):
        i = int(pos * SR)
        n = int(0.03 * SR)
        click = R.standard_normal(n) * env(n, 0, 0.004)
        click += np.sin(2 * np.pi * f * np.arange(n) / SR) * env(n, 0, 0.006) * 0.6
        x[i:i + n] += click * (1.0 if k == 0 else 0.8)
    return x


def stove_fire():
    # burning birch behind a closed iron damper: low roar + crackles
    d = 8.0
    n = int(d * SR)
    roar = lp_fast(R.standard_normal(n), 180) * (0.8 + 0.2 * np.sin(2 * np.pi * 0.3 * t(d)))
    x = roar
    for _ in range(int(d * 9)):
        i = R.integers(0, n - 2000)
        ln = int(R.integers(80, 900))
        c = R.standard_normal(ln) * env(ln, 0, ln / SR / 4) * R.uniform(0.3, 1.2)
        x[i:i + ln] += bp_fast(c, 400, 3500)[:ln] * 0.6
    return loopify(x, 0.5)


def fridge_hum():
    d = 4.0
    tt = t(d)
    x = sum(np.sin(2 * np.pi * 50 * h * tt) / h ** 1.3 for h in (1, 2, 3, 4, 6))
    x += lp_fast(R.standard_normal(len(tt)), 400) * 0.3
    x *= 0.9 + 0.1 * np.sin(2 * np.pi * 0.5 * tt)
    return x  # 4 s is an integer number of 50 Hz periods -> seamless


def radio_static():
    # an old receiver between stations: hiss, crackle, a drifting carrier
    d = 6.0
    tt = t(d)
    hiss = bp_fast(R.standard_normal(len(tt)), 300, 3200)
    drift = 620 + 40 * np.sin(2 * np.pi * (1 / 6.0) * tt)
    phase = 2 * np.pi * np.cumsum(drift) / SR
    carrier = np.sin(phase) * (0.25 + 0.25 * np.sin(2 * np.pi * (1 / 3.0) * tt) ** 2)
    voice = bp_fast(R.standard_normal(len(tt)), 250, 900) * \
        (lp_fast(R.standard_normal(len(tt)), 4) > 0.02) * 0.6   # far-away speech-like bursts
    x = hiss * 0.7 + carrier * 0.25 + voice * 0.4
    return loopify(x, 0.4)


def phone_dial():
    # Russian PSTN dial tone: continuous 425 Hz, picked up from the cradle
    d = 3.0
    tt = t(d)
    tone = np.sin(2 * np.pi * 425 * tt)
    tone = np.tanh(tone * 1.6) * 0.6           # cheap handset distortion
    tone += bp_fast(R.standard_normal(len(tt)), 300, 3000) * 0.04
    e = np.ones(len(tt))
    e[:int(0.25 * SR)] = 0                     # handset lift delay
    e[-int(0.3 * SR):] *= np.linspace(1, 0, int(0.3 * SR))
    clack = np.zeros(len(tt))
    n = int(0.05 * SR)
    clack[:n] = R.standard_normal(n) * env(n, 0, 0.01) * 2
    return tone * e + clack


# ------------------------------------------------------------------ foley
def door_creak():
    # stick-slip creak of an old hinge: pulse train with wandering rate
    d = 1.1
    n = int(d * SR)
    rate = 40 + 70 * np.abs(np.sin(np.linspace(0, 3.2, n))) + lp_fast(R.standard_normal(n), 3) * 300
    phase = np.cumsum(rate / SR)
    pulses = (np.diff(np.floor(phase), prepend=0) > 0).astype(float)
    x = np.zeros(n)
    for f, g in ((520, 1.0), (1150, 0.6), (2300, 0.3)):
        x += bp_fast(pulses, f * 0.85, f * 1.15) * g
    x *= np.sin(np.linspace(0, np.pi, n)) ** 0.5
    return x


def door_stop():
    n = int(0.35 * SR)
    thump = np.sin(2 * np.pi * 90 * np.arange(n) / SR) * env(n, 0, 0.05)
    knock = bp_fast(R.standard_normal(n), 200, 1500) * env(n, 0, 0.03)
    return thump + knock * 0.7


def light_switch():
    n = int(0.08 * SR)
    x = bp_fast(R.standard_normal(n), 1500, 6000) * env(n, 0, 0.004)
    x[int(0.03 * SR):] += bp_fast(R.standard_normal(n - int(0.03 * SR)), 1000, 5000) * \
        env(n - int(0.03 * SR), 0, 0.003) * 0.6
    return x


def latch_locked():
    # someone pushes the locked door: the hook rattles twice
    n = int(0.5 * SR)
    x = np.zeros(n)
    for p in (0.0, 0.12, 0.2):
        i = int(p * SR)
        m = int(0.06 * SR)
        x[i:i + m] += bp_fast(R.standard_normal(m), 800, 4000) * env(m, 0, 0.01)
        x[i:i + m] += np.sin(2 * np.pi * 140 * np.arange(m) / SR) * env(m, 0, 0.02) * 0.6
    return x


def furniture_scrape(k):
    # func_pushable: a wooden leg dragged over floor boards (debris/pushbox*.wav)
    rr = np.random.default_rng(300 + k)
    d = 0.6 + 0.2 * k
    n = int(d * SR)
    rate = 25 + 20 * k + lp_fast(rr.standard_normal(n), 4) * 200
    phase = np.cumsum(np.abs(rate) / SR)
    pulses = (np.diff(np.floor(phase), prepend=0) > 0).astype(float)
    x = bp_fast(pulses, 180, 900) + bp_fast(rr.standard_normal(n), 300, 2500) * 0.15
    return x * np.sin(np.linspace(0, np.pi, n)) ** 0.4


def step(k):
    # footstep on old floor boards: soft thump + sometimes a board squeak
    rr = np.random.default_rng(100 + k)
    n = int(0.28 * SR)
    tt = np.arange(n) / SR
    x = np.sin(2 * np.pi * (70 + 15 * k) * tt) * env(n, 0.002, 0.03)
    x += bp_fast(rr.standard_normal(n), 150, 1200) * env(n, 0.001, 0.02) * 0.6
    if k in (1, 3):
        f = 800 + 300 * rr.random()
        sq = np.sin(2 * np.pi * (f + 200 * tt) * tt) * np.exp(-((tt - 0.09) / 0.03) ** 2)
        x += sq * 0.12
    return x


def main():
    made = []
    made.append(write("ambience/wind_house.wav", wind_house(), loop=True, peak=0.5))
    made.append(write("ambience/clock_tick.wav", clock_tick(), loop=True, peak=0.6))
    made.append(write("ambience/stove_fire.wav", stove_fire(), loop=True, peak=0.6))
    made.append(write("ambience/fridge_hum.wav", fridge_hum(), loop=True, peak=0.35))
    made.append(write("ambience/radio_static.wav", radio_static(), loop=True, peak=0.6))
    made.append(write("ambience/phone_dial.wav", phone_dial(), peak=0.5))
    made.append(write("doors/doormove1.wav", door_creak(), peak=0.6))
    made.append(write("doors/doorstop1.wav", door_stop(), peak=0.7))
    made.append(write("buttons/lightswitch2.wav", light_switch(), peak=0.6))
    made.append(write("buttons/latchlocked1.wav", latch_locked(), peak=0.7))
    for k in range(1, 5):
        made.append(write("player/pl_step%d.wav" % k, step(k), peak=0.5))
    for k in range(1, 4):
        made.append(write("debris/pushbox%d.wav" % k, furniture_scrape(k), peak=0.5))
    made.append(write("common/null.wav", np.zeros(64)))
    print("sounds: %d -> %s" % (len(made), OUT))


if __name__ == "__main__":
    main()
