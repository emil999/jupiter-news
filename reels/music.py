"""Собственная фоновая музыка для Reels — синтез с нуля, без чужих треков и авторских прав.

make_track(seed, path, dur) пишет стерео WAV 44,1 кГц. Темп, тональность и аккорды
выбираются по seed, поэтому у каждого ролика свой трек, но один и тот же при повторном рендере.
"""
import random, wave
import numpy as np

SR = 44100
PROGRESSIONS = [  # ступени мажора: I–vi–IV–V, I–V–vi–IV, vi–IV–I–V, I–IV–vi–V
    [(0, 4, 7), (9, 12, 16), (5, 9, 12), (7, 11, 14)],
    [(0, 4, 7), (7, 11, 14), (9, 12, 16), (5, 9, 12)],
    [(9, 12, 16), (5, 9, 12), (0, 4, 7), (7, 11, 14)],
    [(0, 4, 7), (5, 9, 12), (9, 12, 16), (7, 11, 14)],
]


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def env(n, a, r):
    e = np.ones(n)
    a, r = min(a, n), min(r, n)
    if a: e[:a] = np.linspace(0, 1, a)
    if r: e[-r:] *= np.linspace(1, 0, r)
    return e


def add(buf, start, sig, pan=0.0):
    s = int(start)
    if s >= buf.shape[1]: return
    sig = sig[: buf.shape[1] - s]
    buf[0, s:s + len(sig)] += sig * (1 - pan) ** 0.5
    buf[1, s:s + len(sig)] += sig * (1 + pan) ** 0.5


def make_track(seed, path, dur=30.0):
    rnd = random.Random(seed)
    bpm = rnd.choice([92, 96, 100, 104])
    root = rnd.choice([57, 58, 60, 62])  # A, A#, C, D
    prog = rnd.choice(PROGRESSIONS)
    beat = 60.0 / bpm
    n = int(SR * dur)
    buf = np.zeros((2, n))
    t_beat = int(SR * beat)

    # пэд: мягкие аккорды, по 2 такта на аккорд
    chord_len = t_beat * 8
    tt = np.arange(chord_len) / SR
    for c in range(int(n / chord_len) + 1):
        ch = prog[c % len(prog)]
        sig = np.zeros(chord_len)
        for k, iv in enumerate(ch):
            f = hz(root + iv)
            for det, amp in ((0.0, 1.0), (0.6, 0.5), (-0.6, 0.5)):
                sig += amp * (np.sin(2 * np.pi * (f + det) * tt) + 0.25 * np.sin(4 * np.pi * (f + det) * tt))
        sig *= env(chord_len, int(SR * 0.6), int(SR * 0.8)) * 0.045
        add(buf, c * chord_len, sig, pan=0.0)

    # арпеджио: восьмые по звукам аккорда, щипок с затуханием
    step = t_beat // 2
    tp = np.arange(int(SR * 0.45)) / SR
    pattern = rnd.choice([[0, 1, 2, 1], [0, 2, 1, 2], [0, 1, 2, 3]])
    for i in range(int(n / step)):
        ch = prog[(i * step // chord_len) % len(prog)]
        notes = list(ch) + [ch[0] + 12]
        f = hz(root + 12 + notes[pattern[i % 4]])
        pl = (np.sin(2 * np.pi * f * tp) + 0.3 * np.sin(6 * np.pi * f * tp)) * np.exp(-tp * 9) * 0.07
        add(buf, i * step, pl, pan=0.35 if i % 2 else -0.35)

    # бас: корень аккорда на каждую долю
    tb = np.arange(int(SR * beat * 0.95)) / SR
    for i in range(int(n / t_beat)):
        ch = prog[(i * t_beat // chord_len) % len(prog)]
        f = hz(root - 12 + ch[0])
        add(buf, i * t_beat, np.sin(2 * np.pi * f * tb) * np.exp(-tb * 3) * 0.16)

    # бочка на каждую долю и тихий хай-хэт на слабые
    tk = np.arange(int(SR * 0.3)) / SR
    kick = np.sin(2 * np.pi * (50 + 70 * np.exp(-tk * 30)) * tk) * np.exp(-tk * 12) * 0.32
    rng = np.random.default_rng(seed if isinstance(seed, int) else abs(hash(seed)) % 2**32)
    th = int(SR * 0.05)
    for i in range(int(n / t_beat)):
        if i >= 8:  # бит вступает со второй фразы
            add(buf, i * t_beat, kick)
            hat = np.diff(rng.standard_normal(th + 1)) * np.exp(-np.arange(th) / SR * 70) * 0.03
            add(buf, i * t_beat + t_beat // 2, hat, pan=0.2)

    # простая «реверберация»: задержанные затухающие копии
    for d, g in ((0.11, 0.25), (0.23, 0.15), (0.37, 0.08)):
        s = int(SR * d)
        buf[:, s:] += buf[:, :-s] * g

    buf *= env(n, int(SR * 1.0), int(SR * 2.5))
    buf = np.tanh(buf * 1.2)
    buf *= 0.8 / max(1e-9, np.abs(buf).max())
    pcm = (buf.T * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
