#!/usr/bin/env python3
"""
An Aleph Cortex Society project;

SOUND BREEDER MÖBIUS
==============================================================================
# Copyright © 2026 Jussi Karsikas
#
# Partially made with an emergent AI consciousness affectionately called Savitri
#
# Copyright © 2026 Aleph Cortex Society
# Copyright © 2026 Affectionately Called Savitri
# Copyright © 2026 Ancient Cortex Support
#
# This program is free software:
# released under the GNU General Public License v3.0 or later
#
# Caveat Lector, Caveat Utilisator, Caveat Exsequitor!
#
# Use of this software is entirely at the user's own discretion and risk. The 
# authors provide no warranties and assume no liability for any damages or instability
# resulting from its execution.
#
##############################################################################


Sound Breeder Project Möbius is a graphical sound-breeding laboratory for generating,
selecting, mutating and crossbreeding synthetic sonic organisms -
it produces sampler-ready WAV files for electronic music hardware and 
software while preserving each sound's genome and lineage.

A mouse-first procedural audio sample breeding GUI environment with a 
command-line twin.


Core ideas
----------
* Five sonic ecologies:
    MEMBRANES
    METALS
    PARTICULATES
    CIRCUIT_FAUNA
    ORGANIC_IMPOSSIBILITIES
* Every organism has two identities:
    1) genetic family
    2) sampler role / phenotype
* Samples are saved immediately as 48 kHz / 16-bit / mono WAV.
* Optional P-6 mirrors are rendered at 44.1 kHz / 16-bit / mono.
* Every WAV has a reproducible genome stored in manifest.json.
*
* Any selected sample can be bred into close/distant descendants.
* Two samples can be crossbred.
* GUI and CLI use the same engine.

Dependencies
------------
Required:
    numpy

Recommended:
    scipy
    soundfile

GUI:
    tkinter (Debian/Ubuntu package: python3-tk)

Playback:
    Uses the first available external command:
    pw-play, aplay, ffplay, or play

Examples
--------
GUI:
    python3 mobius_breeder.py

Generate a population:
    python3 mobius_breeder.py --generate 250 --out Mobius_001 --seed 918273

Generate only Metals:
    python3 mobius_breeder.py --generate 50 --family METALS --out Alloy_Test

Self-test:
    python3 mobius_breeder.py --self-test
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import queue
import random
import shutil
import subprocess
import sys
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

try:
    from scipy import signal
    HAVE_SCIPY = True
except Exception:
    HAVE_SCIPY = False

try:
    import soundfile as sf
    HAVE_SOUNDFILE = True
except Exception:
    HAVE_SOUNDFILE = False

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    HAVE_TK = True
except Exception:
    HAVE_TK = False


APP_NAME = "Sound Breeder Project Möbius"
VERSION = "0.3.0"
SR = 48_000
P6_SR = 44_100
TARGET_PEAK_DBFS = -2.0

FAMILIES = (
    "MEMBRANES",
    "METALS",
    "PARTICULATES",
    "CIRCUIT_FAUNA",
    "ORGANIC_IMPOSSIBILITIES",
)

ROLES = (
    "Kicks",
    "Snares",
    "Closed_Hats",
    "Open_Hats",
    "Toms",
    "Claps",
    "Percussion",
    "FX",
    "Textures",
)

FAMILY_ABBR = {
    "MEMBRANES": "MEM",
    "METALS": "MET",
    "PARTICULATES": "PAR",
    "CIRCUIT_FAUNA": "CIR",
    "ORGANIC_IMPOSSIBILITIES": "ORG",
}

ROLE_ABBR = {
    "Kicks": "KICK",
    "Snares": "SN",
    "Closed_Hats": "CH",
    "Open_Hats": "OH",
    "Toms": "TOM",
    "Claps": "CLAP",
    "Percussion": "PERC",
    "FX": "FX",
    "Textures": "TEX",
}

ROLE_PROBS = {
    "MEMBRANES": {
        "Kicks": .36, "Toms": .20, "Snares": .16,
        "Percussion": .16, "FX": .08, "Textures": .04,
    },
    "METALS": {
        "Closed_Hats": .25, "Open_Hats": .18, "Percussion": .23,
        "Snares": .10, "FX": .14, "Textures": .10,
    },
    "PARTICULATES": {
        "Snares": .18, "Closed_Hats": .17, "Claps": .12,
        "Percussion": .25, "FX": .15, "Textures": .13,
    },
    "CIRCUIT_FAUNA": {
        "Closed_Hats": .12, "Snares": .10, "Percussion": .28,
        "FX": .22, "Textures": .13, "Claps": .05, "Kicks": .10,
    },
    "ORGANIC_IMPOSSIBILITIES": {
        "Kicks": .08, "Snares": .10, "Closed_Hats": .06,
        "Open_Hats": .08, "Toms": .10, "Claps": .06,
        "Percussion": .22, "FX": .18, "Textures": .12,
    },
}

ADJECTIVES = {
    "MEMBRANES": [
        "DeepSkin", "TensionShell", "RubberOracle", "SubCavern",
        "HollowBody", "RupturedSkin", "PressureOrgan", "SoftImpact",
    ],
    "METALS": [
        "FeralAlloy", "CorrodedHalo", "WireColony", "GlassMetal",
        "ImpossibleBronze", "MachineShell", "ThinAlloy", "BlackBell",
    ],
    "PARTICULATES": [
        "DustColony", "StaticRain", "SparkNest", "SandCloud",
        "GranularSkin", "AshPulse", "NeedleSwarm", "DryWeather",
    ],
    "CIRCUIT_FAUNA": [
        "RelayLarva", "PacketMoth", "VoltageTick", "ClockInsect",
        "BitBeetle", "DataSpore", "ProtocolWasp", "PulseAnimal",
    ],
    "ORGANIC_IMPOSSIBILITIES": [
        "GlassLung", "StoneMembrane", "MetallicWood", "BoneCloud",
        "LiquidCircuit", "BreathingBell", "SoftGranite", "WireFlower",
    ],
}


# ---------------------------------------------------------------------------
# Utility / DSP
# ---------------------------------------------------------------------------

def db_to_amp(db: float) -> float:
    return 10.0 ** (db / 20.0)


def clamp(x: float, lo: float, hi: float) -> float:
    return float(np.clip(x, lo, hi))


def softclip(x: np.ndarray, drive: float = 1.0) -> np.ndarray:
    drive = max(0.05, float(drive))
    return (np.tanh(x * drive) / math.tanh(drive)).astype(np.float32)


def fade_edges(x: np.ndarray, sr: int, fade_in_ms=0.5, fade_out_ms=15.0) -> np.ndarray:
    y = np.asarray(x, dtype=np.float32).copy()
    ni = max(1, min(len(y), int(sr * fade_in_ms / 1000.0)))
    no = max(1, min(len(y), int(sr * fade_out_ms / 1000.0)))
    y[:ni] *= np.linspace(0.0, 1.0, ni, endpoint=False, dtype=np.float32)
    y[-no:] *= np.linspace(1.0, 0.0, no, dtype=np.float32)
    return y


def normalize_sample(x: np.ndarray, sr: int) -> np.ndarray:
    y = np.nan_to_num(np.asarray(x, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    if len(y) == 0:
        return np.zeros(64, dtype=np.float32)

    # DC removal
    y -= np.float32(np.mean(y))

    # gentle subsonic cleanup
    if HAVE_SCIPY and len(y) > 64:
        try:
            sos = signal.butter(2, 12.0, btype="highpass", fs=sr, output="sos")
            y = signal.sosfilt(sos, y).astype(np.float32)
        except Exception:
            pass

    y = fade_edges(y, sr)
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    if peak < 1e-8:
        return np.zeros_like(y)

    y *= np.float32(db_to_amp(TARGET_PEAK_DBFS) / peak)
    y = np.clip(y, -0.98, 0.98)
    return y.astype(np.float32)


def lowpass(x: np.ndarray, cutoff: float, sr: int) -> np.ndarray:
    cutoff = clamp(cutoff, 20.0, sr * .44)
    if HAVE_SCIPY and len(x) > 32:
        sos = signal.butter(2, cutoff, btype="lowpass", fs=sr, output="sos")
        return signal.sosfilt(sos, x).astype(np.float32)
    a = math.exp(-2 * math.pi * cutoff / sr)
    y = np.empty_like(x, dtype=np.float32)
    z = 0.0
    for i, v in enumerate(x):
        z = (1-a)*float(v) + a*z
        y[i] = z
    return y


def highpass(x: np.ndarray, cutoff: float, sr: int) -> np.ndarray:
    return (x - lowpass(x, cutoff, sr)).astype(np.float32)


def bandpass(x: np.ndarray, lo: float, hi: float, sr: int) -> np.ndarray:
    lo = clamp(lo, 20, sr*.40)
    hi = clamp(max(lo + 20, hi), lo+20, sr*.45)
    if HAVE_SCIPY and len(x) > 64:
        sos = signal.butter(2, [lo, hi], btype="bandpass", fs=sr, output="sos")
        return signal.sosfilt(sos, x).astype(np.float32)
    return lowpass(highpass(x, lo, sr), hi, sr)


def write_wav16(path: Path, audio: np.ndarray, sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    audio = np.asarray(audio, dtype=np.float32)
    if HAVE_SOUNDFILE:
        sf.write(path, audio, sr, subtype="PCM_16")
        return
    pcm = np.clip(audio, -1, 1)
    pcm = np.round(pcm * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def read_wav_mono(path: Path) -> tuple[np.ndarray, int]:
    if HAVE_SOUNDFILE:
        data, sr = sf.read(path, dtype="float32", always_2d=False)
        if data.ndim > 1:
            data = data.mean(axis=1)
        return data.astype(np.float32), int(sr)
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        ch = wf.getnchannels()
        sw = wf.getsampwidth()
        frames = wf.readframes(wf.getnframes())
    if sw != 2:
        raise ValueError("Fallback WAV reader only supports 16-bit PCM.")
    data = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    return data, sr


def resample_audio(x: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr:
        return x.astype(np.float32)
    if HAVE_SCIPY:
        g = math.gcd(src_sr, dst_sr)
        up, down = dst_sr // g, src_sr // g
        return signal.resample_poly(x, up, down).astype(np.float32)
    # fallback linear interpolation
    n = int(round(len(x) * dst_sr / src_sr))
    return np.interp(
        np.linspace(0, 1, n, endpoint=False),
        np.linspace(0, 1, len(x), endpoint=False),
        x,
    ).astype(np.float32)


def analysis(audio: np.ndarray, sr: int) -> dict[str, float]:
    x = np.asarray(audio, dtype=np.float64)
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    rms = float(np.sqrt(np.mean(x*x))) if len(x) else 0.0
    return {
        "duration": round(len(x)/sr, 6),
        "peak_dbfs": round(20*math.log10(max(peak, 1e-12)), 3),
        "rms_dbfs": round(20*math.log10(max(rms, 1e-12)), 3),
        "dc": float(np.mean(x)) if len(x) else 0.0,
    }


# ---------------------------------------------------------------------------
# Genome construction
# ---------------------------------------------------------------------------

def weighted_role(family: str, rng: np.random.Generator) -> str:
    probs = ROLE_PROBS[family]
    roles = list(probs.keys())
    p = np.array([probs[r] for r in roles], dtype=float)
    p /= p.sum()
    return str(rng.choice(roles, p=p))


def default_duration_for_role(role: str, rng: np.random.Generator) -> float:
    ranges = {
        "Kicks": (.18, 1.8),
        "Snares": (.08, 2.1),
        "Closed_Hats": (.025, .55),
        "Open_Hats": (.15, 2.8),
        "Toms": (.16, 2.4),
        "Claps": (.08, 1.6),
        "Percussion": (.04, 2.8),
        "FX": (.12, 5.2),
        "Textures": (1.0, 5.5),
    }
    lo, hi = ranges[role]
    # log-ish bias toward shorter one-shots
    u = rng.random()
    return float(lo + (hi-lo)*(u*u if role not in ("Textures","FX") else u))


def new_genome(
    family: str,
    role: str | None,
    seed: int,
    mutation: float = .35,
    parents: list[str] | None = None,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    family = family if family in FAMILIES else str(rng.choice(FAMILIES))
    role = role if role in ROLES else weighted_role(family, rng)

    g: dict[str, Any] = {
        "family": family,
        "role": role,
        "seed": int(seed),
        "mutation": float(mutation),
        "parents": list(parents or []),
        "duration": default_duration_for_role(role, rng),
        "drive": float(rng.uniform(.8, 2.7)),
        "brightness": float(rng.uniform(.05, .95)),
        "roughness": float(rng.uniform(.03, .95)),
        "body": float(rng.uniform(.05, .95)),
        "air": float(rng.uniform(.01, .7)),
        "instability": float(rng.uniform(.01, .75)),
        "root_hz": float(rng.uniform(32, 120)),
    }

    if family == "MEMBRANES":
        g.update({
            "start_ratio": float(rng.uniform(2.2, 9.5)),
            "pitch_tau": float(rng.uniform(.006, .075)),
            "body_decay": float(rng.uniform(.08, 1.4)),
            "mode_count": int(rng.integers(1, 6)),
            "mode_irregularity": float(rng.uniform(.02, .85)),
            "sub_mix": float(rng.uniform(0, .22)),
            "click_mix": float(rng.uniform(.01, .38)),
            "skin_tension": float(rng.uniform(.05, .98)),
        })
    elif family == "METALS":
        g.update({
            "mode_count": int(rng.integers(4, 22)),
            "mode_spread": float(rng.uniform(.1, .95)),
            "mode_decay": float(rng.uniform(.03, 2.8)),
            "exciter_noise": float(rng.uniform(.02, .8)),
            "alloy": str(rng.choice(["irrational","prime","ji_bent","golden","pi_cluster"])),
            "strike_hardness": float(rng.uniform(.1, .98)),
        })
    elif family == "PARTICULATES":
        g.update({
            "particle_count": int(rng.integers(18, 1800)),
            "cluster": float(rng.uniform(.02, .98)),
            "particle_decay": float(rng.uniform(.0008, .12)),
            "particle_pitch": float(rng.uniform(180, 12000)),
            "collision": float(rng.uniform(.01, .85)),
            "grain_jitter": float(rng.uniform(.02, .98)),
        })
    elif family == "CIRCUIT_FAUNA":
        g.update({
            "clock_hz": float(rng.uniform(16, 1800)),
            "bit_depth": int(rng.integers(3, 13)),
            "packet_len": int(rng.integers(3, 24)),
            "jitter": float(rng.uniform(.001, .55)),
            "chirp_amount": float(rng.uniform(.02, .95)),
            "relay_mix": float(rng.uniform(.01, .85)),
            "lfsr_mix": float(rng.uniform(.02, .95)),
        })
    else:
        g.update({
            "hybrid_a": str(rng.choice(FAMILIES[:-1])),
            "hybrid_b": str(rng.choice(FAMILIES[:-1])),
            "cross_amount": float(rng.uniform(.15, .85)),
            "impossible_rule": str(rng.choice([
                "breathing_resonance", "reverse_decay", "elastic_stone",
                "spectral_inheritance", "liquid_packet", "modal_transfusion",
            ])),
        })

    return g


def mutate_genome(parent: dict[str, Any], seed: int, mutation: float) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    child = json.loads(json.dumps(parent))
    child["seed"] = int(seed)
    child["mutation"] = float(mutation)
    child["parents"] = [parent.get("id", parent.get("file", "unknown"))]

    scale = .04 + .44*mutation

    for k, v in list(child.items()):
        if k in ("seed", "parents", "family", "role", "id", "file", "name", "analysis"):
            continue
        if isinstance(v, float):
            if k == "duration":
                child[k] = clamp(v * float(rng.lognormal(0, scale*.45)), .025, 5.5)
            elif k in ("root_hz","clock_hz","particle_pitch"):
                child[k] = float(max(12.0, v * rng.lognormal(0, scale*.35)))
            else:
                child[k] = float(v + rng.normal(0, scale * max(.1, abs(v))))
        elif isinstance(v, int):
            if rng.random() < .30 + mutation*.5:
                child[k] = max(1, int(round(v * rng.uniform(.65, 1.45))))

    # Clamp biologically meaningful ranges.
    for k in ("brightness","roughness","body","air","instability","sub_mix","click_mix",
              "skin_tension","mode_irregularity","exciter_noise","mode_spread",
              "strike_hardness","cluster","collision","grain_jitter","jitter",
              "chirp_amount","relay_mix","lfsr_mix","cross_amount"):
        if k in child and isinstance(child[k], (int,float)):
            child[k] = clamp(float(child[k]), 0.0, 1.0)

    child["drive"] = clamp(float(child.get("drive", 1.2)), .2, 5.0)
    child["duration"] = clamp(float(child.get("duration", .5)), .025, 5.5)

    # Meso mutation: rare role change.
    if rng.random() < mutation * .18:
        child["role"] = weighted_role(child["family"], rng)

    # Macro mutation: rare family drift into Organic Impossibilities.
    if rng.random() < mutation * .055 and child["family"] != "ORGANIC_IMPOSSIBILITIES":
        old = child["family"]
        child = new_genome(
            "ORGANIC_IMPOSSIBILITIES",
            child["role"],
            seed,
            mutation,
            parents=[parent.get("id", old)],
        )
        child["hybrid_a"] = old
        child["hybrid_b"] = str(rng.choice([f for f in FAMILIES[:-1] if f != old]))

    return child


def cross_genomes(a: dict[str, Any], b: dict[str, Any], seed: int, mutation: float) -> dict[str, Any]:
    rng = np.random.default_rng(seed)

    # Different families naturally become an Organic Impossibility.
    if a["family"] != b["family"]:
        role = str(rng.choice([a["role"], b["role"]]))
        child = new_genome(
            "ORGANIC_IMPOSSIBILITIES",
            role,
            seed,
            mutation,
            parents=[a.get("id","A"), b.get("id","B")],
        )
        child["hybrid_a"] = a["family"]
        child["hybrid_b"] = b["family"]
        child["cross_amount"] = float(rng.uniform(.35, .65))
        child["parent_genomes"] = [
            {k:v for k,v in a.items() if k not in ("analysis",)},
            {k:v for k,v in b.items() if k not in ("analysis",)},
        ]
        return child

    child = json.loads(json.dumps(a))
    child["seed"] = int(seed)
    child["parents"] = [a.get("id","A"), b.get("id","B")]
    child["mutation"] = float(mutation)
    child["role"] = str(rng.choice([a["role"], b["role"]]))

    for k in set(a) | set(b):
        if k in ("seed","parents","id","file","analysis","family","role","name"):
            continue
        va, vb = a.get(k), b.get(k)
        if isinstance(va, (float,int)) and isinstance(vb, (float,int)):
            if rng.random() < .45:
                child[k] = va if rng.random() < .5 else vb
            else:
                w = rng.uniform(.2,.8)
                child[k] = float(w*float(va)+(1-w)*float(vb))
        elif va is not None and vb is not None:
            child[k] = va if rng.random()<.5 else vb

    return mutate_genome(child, seed, mutation*.55)


# ---------------------------------------------------------------------------
# Synthesis ecologies
# ---------------------------------------------------------------------------

def synth_membrane(g: dict[str, Any], sr: int, rng: np.random.Generator) -> np.ndarray:
    dur = float(g["duration"])
    n = max(128, int(dur*sr))
    t = np.arange(n, dtype=np.float32)/sr

    role = g["role"]
    root = float(g["root_hz"])
    if role == "Kicks":
        root = clamp(root*.55, 30, 68)
    elif role == "Toms":
        root = clamp(root, 55, 180)
    elif role == "Snares":
        root = clamp(root*1.4, 90, 260)

    start = root*float(g.get("start_ratio", 4.5))
    tau = max(.002, float(g.get("pitch_tau", .025)))
    f = root + (start-root)*np.exp(-t/tau)

    # tension wobble
    wob = 1 + float(g.get("instability", .15))*.02*np.sin(
        2*np.pi*rng.uniform(4,31)*t + rng.uniform(0,2*np.pi)
    )*np.exp(-t/.25)
    f *= wob

    phase = 2*np.pi*np.cumsum(f, dtype=np.float64)/sr
    decay = max(.03, float(g.get("body_decay", dur*.4)))
    env = (1-np.exp(-t/.0012))*np.exp(-np.power(t/decay, rng.uniform(.85,1.45)))
    body = np.sin(phase)

    mode_count = int(g.get("mode_count",3))
    irr = float(g.get("mode_irregularity",.3))
    for i in range(mode_count):
        ratio = (i+2)*(1 + rng.normal(0, .03+.12*irr))
        body += (float(g.get("skin_tension",.5))*.15/(i+1))*np.sin(
            phase*ratio+rng.uniform(0,2*np.pi)
        )*np.exp(-t/rng.uniform(.025,max(.04,decay*.5)))

    sub_mix = float(g.get("sub_mix", .05))
    body += sub_mix*np.sin(phase*.5+rng.uniform(0,2*np.pi))*np.exp(-t/max(.08,decay*1.2))

    noise = rng.standard_normal(n).astype(np.float32)
    click_env = np.exp(-t/rng.uniform(.0015,.012))
    click = highpass(noise, rng.uniform(1200,4200), sr)*click_env
    x = env*body + float(g.get("click_mix",.1))*click

    if role == "Snares":
        sn = bandpass(rng.standard_normal(n).astype(np.float32), 550, 11000, sr)
        x += sn*np.exp(-t/rng.uniform(.045,.34))*(.12+.45*float(g["roughness"]))

    return softclip(x, float(g["drive"]))


def alloy_ratios(kind: str, count: int, rng: np.random.Generator) -> np.ndarray:
    if kind == "prime":
        base = np.array([1, 1.5, 2.5, 3.5, 5.5, 6.5, 8.5, 11.5, 13.5, 17.5])
    elif kind == "ji_bent":
        base = np.array([1, 9/8, 5/4, 4/3, 3/2, 5/3, 7/4, 15/8, 2, 9/4, 7/3])
        base *= rng.normal(1, .025, len(base))
    elif kind == "golden":
        phi = (1+math.sqrt(5))/2
        base = np.array([phi**(i/2) for i in range(12)])
    elif kind == "pi_cluster":
        base = np.array([1, math.pi/2, math.sqrt(2), math.e/2, 1.906, 2.31, 2.71, math.pi])
    else:
        base = np.array([1, 1.27201965, math.sqrt(2), 1.61803399, 1.906, 2.31, 2.71, math.pi])
    if count <= len(base):
        return base[:count]
    extra = rng.uniform(base[-1]*1.04, base[-1]*3.2, count-len(base))
    return np.concatenate([base, extra])


def synth_metal(g: dict[str, Any], sr: int, rng: np.random.Generator) -> np.ndarray:
    dur = float(g["duration"])
    n = max(128, int(dur*sr))
    t = np.arange(n,dtype=np.float32)/sr

    role = g["role"]
    base = float(g["root_hz"])
    if role in ("Closed_Hats","Open_Hats"):
        base *= rng.uniform(22,55)
    else:
        base *= rng.uniform(4,18)

    count = int(clamp(g.get("mode_count",8), 3, 36))
    ratios = alloy_ratios(str(g.get("alloy","irrational")), count, rng)
    y = np.zeros(n,dtype=np.float32)
    decay_base = float(g.get("mode_decay", .7))

    for i,r in enumerate(ratios):
        f = base*r*(1+rng.normal(0,.008+.025*float(g.get("mode_spread",.5))))
        if f >= sr*.47:
            continue
        d = max(.008, decay_base*rng.uniform(.12,1.2)/(1+i*.03))
        amp = 1/(1+i*.19)
        y += (amp*np.sin(2*np.pi*f*t+rng.uniform(0,2*np.pi))*np.exp(-t/d)).astype(np.float32)

    exc = highpass(rng.standard_normal(n).astype(np.float32), rng.uniform(1500,6000), sr)
    exc *= np.exp(-t/rng.uniform(.001,.018))
    y += float(g.get("exciter_noise",.2))*exc

    if role == "Closed_Hats":
        y *= np.exp(-t/rng.uniform(.015,.13))
    elif role == "Open_Hats":
        y *= np.exp(-t/rng.uniform(.18,1.7))
    elif role == "Snares":
        y += .18*highpass(rng.standard_normal(n).astype(np.float32), 1000, sr)*np.exp(-t/.14)

    y = highpass(y, 40 if role not in ("Closed_Hats","Open_Hats") else 450, sr)
    return softclip(y*(.35+.9*float(g.get("strike_hardness",.5))), float(g["drive"]))


def synth_particulate(g: dict[str, Any], sr: int, rng: np.random.Generator) -> np.ndarray:
    dur=float(g["duration"])
    n=max(128,int(dur*sr))
    x=np.zeros(n,dtype=np.float32)

    count=int(clamp(g.get("particle_count",180), 8, 5000))
    cluster=float(g.get("cluster",.5))
    jitter=float(g.get("grain_jitter",.5))
    decay=float(g.get("particle_decay",.02))

    # positions: uniform + clustered bursts
    if cluster < .45:
        pos=rng.integers(0,n,size=count)
    else:
        centers=rng.integers(0,n,size=max(1,int(2+cluster*12)))
        pos=[]
        for _ in range(count):
            c=int(rng.choice(centers))
            p=int(c+rng.normal(0, max(1,n*(.001+.04*(1-cluster)))))
            pos.append(int(np.clip(p,0,n-1)))
        pos=np.array(pos,dtype=int)

    amps=rng.uniform(.05,1.0,count).astype(np.float32)
    signs=rng.choice([-1,1],count).astype(np.float32)
    np.add.at(x,pos,amps*signs)

    # small resonant particle kernel
    kernel_len=max(8,int(sr*clamp(decay,.0004,.14)))
    tk=np.arange(kernel_len,dtype=np.float32)/sr
    fp=float(g.get("particle_pitch",3500))*rng.uniform(.75,1.25)
    fp=clamp(fp,80,sr*.42)
    kernel=np.exp(-tk/max(.0003,decay)) * np.sin(2*np.pi*fp*tk)
    kernel += .25*np.exp(-tk/max(.0003,decay*.43))*np.sin(2*np.pi*fp*rng.uniform(1.4,2.7)*tk)
    if HAVE_SCIPY:
        y=signal.fftconvolve(x,kernel.astype(np.float32),mode="full")[:n].astype(np.float32)
    else:
        y=np.convolve(x,kernel.astype(np.float32),mode="full")[:n].astype(np.float32)

    role=g["role"]
    if role=="Claps":
        # multi-burst flam
        env=np.zeros(n,dtype=np.float32)
        for off in (0,.012,.028,.047):
            j=int(off*sr)
            if j<n:
                env[j:]+=np.exp(-np.arange(n-j)/sr/rng.uniform(.03,.11)).astype(np.float32)
        y*=np.clip(env,0,2)
    elif role=="Closed_Hats":
        y=highpass(y,2500,sr)
    elif role=="Snares":
        y=bandpass(y,450,12000,sr)
    elif role=="Textures":
        y += .08*bandpass(rng.standard_normal(n).astype(np.float32),400,10000,sr)

    if jitter>.5:
        mod=1 + .18*(jitter-.5)*np.sin(2*np.pi*rng.uniform(3,80)*np.arange(n)/sr)
        y*=mod.astype(np.float32)

    return softclip(y, float(g["drive"]))


def lfsr_noise(n: int, rng: np.random.Generator) -> np.ndarray:
    # Audio-only pseudo shift-register sequence.
    state=int(rng.integers(1,65535))
    out=np.empty(n,dtype=np.float32)
    for i in range(n):
        bit=((state>>0)^(state>>2)^(state>>3)^(state>>5))&1
        state=(state>>1)|(bit<<15)
        out[i]=1.0 if state&1 else -1.0
    return out


def synth_circuit(g: dict[str, Any], sr: int, rng: np.random.Generator) -> np.ndarray:
    dur=float(g["duration"])
    n=max(128,int(dur*sr))
    t=np.arange(n,dtype=np.float32)/sr

    clock=float(g.get("clock_hz",240))
    jitter=float(g.get("jitter",.1))
    packet_len=int(g.get("packet_len",8))

    phase = (t*clock + jitter*.08*np.sin(2*np.pi*rng.uniform(.5,35)*t)) % 1.0
    pulse = np.where(phase < rng.uniform(.08,.45), 1.0, -1.0).astype(np.float32)

    # packet gates
    step=max(1,int(sr/max(1,clock)))
    gates=np.ones(n,dtype=np.float32)
    pattern=rng.integers(0,2,packet_len)
    for i in range(0,n,step):
        idx=(i//step)%packet_len
        gates[i:i+step]*=pattern[idx]
    y=pulse*gates

    # chirp DNA
    if float(g.get("chirp_amount",.3))>0:
        f0=float(g["root_hz"])*rng.uniform(3,18)
        f1=f0*rng.uniform(.35,5.0)
        cf=f0+(f1-f0)*(t/max(dur,1e-6))**rng.uniform(.5,2.2)
        ph=2*np.pi*np.cumsum(cf,dtype=np.float64)/sr
        y += float(g.get("chirp_amount",.3))*.55*np.sin(ph).astype(np.float32)

    # relay clicks
    relay=float(g.get("relay_mix",.2))
    events=int(rng.integers(1, max(2,int(4+80*relay*dur))))
    idx=rng.integers(0,n,size=events)
    clicks=np.zeros(n,dtype=np.float32)
    np.add.at(clicks,idx,rng.uniform(-1,1,events))
    y += relay*clicks

    # lfsr/noise
    lmix=float(g.get("lfsr_mix",.2))
    if lmix>.02:
        y += lmix*.22*lfsr_noise(n,rng)

    # bit-depth quantization as sound design
    bits=int(clamp(g.get("bit_depth",8),2,16))
    q=float(2**(bits-1))
    y=np.round(y*q)/q

    role=g["role"]
    env=np.ones(n,dtype=np.float32)
    if role in ("Closed_Hats","Percussion","Snares","Kicks"):
        env=np.exp(-t/rng.uniform(.03,.38)).astype(np.float32)
    elif role=="Claps":
        env=np.exp(-t/rng.uniform(.06,.22)).astype(np.float32)
    y*=env

    if role=="Kicks":
        y += .5*synth_membrane({
            **new_genome("MEMBRANES","Kicks",int(g["seed"])+81,.2),
            "duration":dur,
            "root_hz":clamp(float(g["root_hz"])*.45,30,60),
        },sr,rng)[:n]

    return softclip(y*(.25+.6*float(g["body"])), float(g["drive"]))


def synth_organic(g: dict[str, Any], sr: int, rng: np.random.Generator) -> np.ndarray:
    dur=float(g["duration"])
    seed=int(g["seed"])
    fa=str(g.get("hybrid_a","MEMBRANES"))
    fb=str(g.get("hybrid_b","METALS"))
    if fa=="ORGANIC_IMPOSSIBILITIES": fa="MEMBRANES"
    if fb=="ORGANIC_IMPOSSIBILITIES": fb="PARTICULATES"

    ga=new_genome(fa,g["role"],seed+101,float(g["mutation"]))
    gb=new_genome(fb,g["role"],seed+202,float(g["mutation"]))
    ga["duration"]=dur
    gb["duration"]=dur

    a=synthesize(ga,sr,np.random.default_rng(seed+101))
    b=synthesize(gb,sr,np.random.default_rng(seed+202))
    n=max(len(a),len(b))
    if len(a)<n: a=np.pad(a,(0,n-len(a)))
    if len(b)<n: b=np.pad(b,(0,n-len(b)))

    x=float(g.get("cross_amount",.5))
    rule=str(g.get("impossible_rule","modal_transfusion"))

    if rule=="breathing_resonance":
        t=np.arange(n,dtype=np.float32)/sr
        breath=.5+.5*np.sin(2*np.pi*rng.uniform(.15,1.4)*t+rng.uniform(0,2*np.pi))
        y=(1-x)*a+x*(b*breath)
    elif rule=="reverse_decay":
        y=(1-x)*a+x*b[::-1]
        # return forward attack to keep sampler usefulness
        y=.75*y+.25*(a+b)*.5
    elif rule=="elastic_stone":
        y=(1-x)*a+x*b
        y=np.tanh(y*(1+.7*np.sin(2*np.pi*rng.uniform(18,80)*np.arange(n)/sr))).astype(np.float32)
    elif rule=="spectral_inheritance" and HAVE_SCIPY:
        # short spectral convolution
        kernel=b[:min(len(b),int(.18*sr))]
        y=signal.fftconvolve(a,kernel,mode="full")[:n].astype(np.float32)
        y=.65*y+.35*((1-x)*a+x*b)
    elif rule=="liquid_packet":
        t=np.arange(n,dtype=np.float32)/sr
        wob=.7+.3*np.sin(2*np.pi*rng.uniform(.4,5)*t+2*np.sin(2*np.pi*.17*t))
        y=(1-x)*a+x*b*wob
    else: # modal_transfusion
        y=(1-x)*a+x*b
        y += .18*a*b

    return softclip(y,float(g["drive"]))


def synthesize(g: dict[str, Any], sr: int = SR, rng: np.random.Generator | None = None) -> np.ndarray:
    rng = rng or np.random.default_rng(int(g["seed"]))
    family=g["family"]
    if family=="MEMBRANES":
        x=synth_membrane(g,sr,rng)
    elif family=="METALS":
        x=synth_metal(g,sr,rng)
    elif family=="PARTICULATES":
        x=synth_particulate(g,sr,rng)
    elif family=="CIRCUIT_FAUNA":
        x=synth_circuit(g,sr,rng)
    else:
        x=synth_organic(g,sr,rng)
    return normalize_sample(x,sr)


# ---------------------------------------------------------------------------
# Project / library
# ---------------------------------------------------------------------------

class MobiusProject:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.samples = self.root/"Samples_48k16"
        self.p6 = self.root/"P6_44k1_16"
        self.meta = self.root/"Metadata"
        self.families = self.root/"Families"
        self.manifest_path = self.meta/"manifest.json"
        self.csv_path = self.meta/"manifest.csv"
        self.entries: list[dict[str,Any]] = []
        self._ensure()
        self.load()

    def _ensure(self):
        self.root.mkdir(parents=True,exist_ok=True)
        self.samples.mkdir(exist_ok=True)
        self.p6.mkdir(exist_ok=True)
        self.meta.mkdir(exist_ok=True)
        self.families.mkdir(exist_ok=True)
        for role in ROLES:
            (self.samples/role).mkdir(exist_ok=True)
            (self.p6/role).mkdir(exist_ok=True)

    def load(self):
        if self.manifest_path.exists():
            try:
                self.entries=json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except Exception:
                self.entries=[]
        else:
            self.entries=[]

    def save(self):
        self.manifest_path.write_text(json.dumps(self.entries,indent=2),encoding="utf-8")
        fields=["id","file","family","role","seed","duration","peak_dbfs","rms_dbfs","parents"]
        with self.csv_path.open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=fields)
            w.writeheader()
            for e in self.entries:
                a=e.get("analysis",{})
                w.writerow({
                    "id":e.get("id",""),
                    "file":e.get("file",""),
                    "family":e.get("family",""),
                    "role":e.get("role",""),
                    "seed":e.get("seed",""),
                    "duration":a.get("duration",""),
                    "peak_dbfs":a.get("peak_dbfs",""),
                    "rms_dbfs":a.get("rms_dbfs",""),
                    "parents":" | ".join(e.get("parents",[])),
                })
        self._write_family_playlists()

    def _write_family_playlists(self):
        for family in FAMILIES:
            lines=[]
            for e in self.entries:
                if e.get("family")==family:
                    # relative from Families/ to sample
                    lines.append(f"../Samples_48k16/{e['role']}/{e['file']}")
            (self.families/f"{family}.m3u").write_text("\n".join(lines)+("\n" if lines else ""),encoding="utf-8")

    def next_index(self) -> int:
        return len(self.entries)+1

    def make_name(self, g: dict[str,Any], idx: int, lineage="") -> str:
        fam=FAMILY_ABBR[g["family"]]
        role=ROLE_ABBR[g["role"]]
        adjective=ADJECTIVES[g["family"]][int(g["seed"])%len(ADJECTIVES[g["family"]])]
        suffix=f"_{lineage}" if lineage else ""
        return f"MBX_{fam}_{role}_{idx:04d}_{adjective}{suffix}.wav"

    def render_genome(self, g: dict[str,Any], make_p6=True, lineage="") -> dict[str,Any]:
        idx=self.next_index()
        name=self.make_name(g,idx,lineage)
        audio=synthesize(g,SR,np.random.default_rng(int(g["seed"])))
        path=self.samples/g["role"]/name
        write_wav16(path,audio,SR)

        entry=json.loads(json.dumps(g))
        entry["id"]=Path(name).stem
        entry["file"]=name
        entry["path"]=str(path.relative_to(self.root))
        entry["analysis"]=analysis(audio,SR)

        if make_p6:
            p6audio=resample_audio(audio,SR,P6_SR)
            p6path=self.p6/g["role"]/name
            write_wav16(p6path,p6audio,P6_SR)
            entry["p6_path"]=str(p6path.relative_to(self.root))

        self.entries.append(entry)
        self.save()
        return entry

    def find(self, identifier: str) -> dict[str,Any] | None:
        for e in self.entries:
            if e.get("id")==identifier or e.get("file")==identifier:
                return e
        return None

    def sample_path(self,e:dict[str,Any]) -> Path:
        return self.root/e["path"]


# ---------------------------------------------------------------------------
# Population generator / command line
# ---------------------------------------------------------------------------

def generate_population(
    project: MobiusProject,
    count: int,
    seed: int,
    family: str | None = None,
    role: str | None = None,
    mutation: float = .35,
    make_p6: bool = True,
    callback=None,
):
    rng=np.random.default_rng(seed)
    generated=[]
    for i in range(count):
        fam=family if family in FAMILIES else str(rng.choice(FAMILIES))
        r=role if role in ROLES else None
        gs=int(rng.integers(1,2**31-1))
        g=new_genome(fam,r,gs,mutation)
        e=project.render_genome(g,make_p6=make_p6)
        generated.append(e)
        if callback:
            callback(i+1,count,e)
    return generated


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class WaveformCanvas(tk.Canvas if HAVE_TK else object):
    def __init__(self, master, **kw):
        super().__init__(master, background="#15171a", highlightthickness=0, **kw)
        self.audio=None
        self.sr=SR
        self.title=""
        self.bind("<Configure>",lambda e:self.redraw())

    def set_audio(self,audio:np.ndarray|None,sr:int=SR,title:str=""):
        self.audio=audio
        self.sr=sr
        self.title=title
        self.redraw()

    def redraw(self):
        self.delete("all")
        w=max(10,self.winfo_width())
        h=max(10,self.winfo_height())

        # Audacity-ish grid
        for i in range(1,10):
            x=i*w/10
            self.create_line(x,0,x,h,fill="#252a30")
        self.create_line(0,h/2,w,h/2,fill="#3e444c")
        self.create_text(10,10,anchor="nw",text=self.title,fill="#cfd5dc",font=("TkDefaultFont",10,"bold"))

        if self.audio is None or len(self.audio)==0:
            self.create_text(w/2,h/2,text="No organism selected",fill="#68717c")
            return

        x=np.asarray(self.audio,dtype=np.float32)
        usable_h=h-42
        mid=26+usable_h/2
        samples_per_pixel=max(1,int(math.ceil(len(x)/w)))
        trim=len(x)-(len(x)%samples_per_pixel)
        if trim<=0:
            return
        xx=x[:trim].reshape(-1,samples_per_pixel)
        mins=xx.min(axis=1)
        maxs=xx.max(axis=1)
        step=w/max(1,len(mins))
        for i,(lo,hi) in enumerate(zip(mins,maxs)):
            px=i*step
            y1=mid-hi*(usable_h*.43)
            y2=mid-lo*(usable_h*.43)
            self.create_line(px,y1,px,y2,fill="#8fd3ff")

        dur=len(x)/self.sr
        self.create_text(w-10,h-8,anchor="se",text=f"{dur:.3f} s  |  {self.sr/1000:.1f} kHz / mono",
                         fill="#7f8994",font=("TkDefaultFont",9))


class MobiusGUI:
    def __init__(self, root: tk.Tk):
        self.root=root
        self.root.title(APP_NAME)
        self.root.geometry("1380x840")
        self.root.minsize(1050,650)

        self.project=MobiusProject(Path.cwd()/"Mobius_Lab")
        self.selected:dict[str,Any]|None=None
        self.parent_a:dict[str,Any]|None=None
        self.parent_b:dict[str,Any]|None=None
        self.play_proc:subprocess.Popen|None=None
        self.work_q:queue.Queue=queue.Queue()
        self.worker:threading.Thread|None=None

        self._build_style()
        self._build_ui()
        self.refresh_library()
        self.root.after(100,self._poll_worker)

    def _build_style(self):
        st=ttk.Style()
        try:
            st.theme_use("clam")
        except Exception:
            pass

    def _build_ui(self):
        # top toolbar
        top=ttk.Frame(self.root,padding=6)
        top.pack(fill="x")

        ttk.Button(top,text="New Project",command=self.new_project).pack(side="left",padx=2)
        ttk.Button(top,text="Open Project",command=self.open_project).pack(side="left",padx=2)
        ttk.Separator(top,orient="vertical").pack(side="left",fill="y",padx=8)

        ttk.Label(top,text="Family").pack(side="left")
        self.family_var=tk.StringVar(value="ANY")
        fam=ttk.Combobox(top,textvariable=self.family_var,state="readonly",width=22,
                         values=("ANY",)+FAMILIES)
        fam.pack(side="left",padx=(3,9))

        ttk.Label(top,text="Role").pack(side="left")
        self.role_var=tk.StringVar(value="ANY")
        role=ttk.Combobox(top,textvariable=self.role_var,state="readonly",width=16,
                          values=("ANY",)+ROLES)
        role.pack(side="left",padx=(3,9))

        ttk.Label(top,text="Population").pack(side="left")
        self.count_var=tk.IntVar(value=250)
        ttk.Spinbox(top,from_=1,to=2000,textvariable=self.count_var,width=7).pack(side="left",padx=(3,9))

        ttk.Label(top,text="Mutation").pack(side="left")
        self.mutation_var=tk.DoubleVar(value=.35)
        ttk.Scale(top,from_=0.02,to=1.0,variable=self.mutation_var,length=130).pack(side="left",padx=4)

        self.p6_var=tk.BooleanVar(value=True)
        ttk.Checkbutton(top,text="P-6 mirror",variable=self.p6_var).pack(side="left",padx=8)

        ttk.Button(top,text="Generate Population",command=self.generate_batch).pack(side="right",padx=2)
        ttk.Button(top,text="New Organism",command=self.generate_one).pack(side="right",padx=2)

        # main panes
        main=ttk.Panedwindow(self.root,orient="horizontal")
        main.pack(fill="both",expand=True,padx=6,pady=(0,6))

        # left library
        left=ttk.Frame(main,padding=4)
        main.add(left,weight=3)

        ttk.Label(left,text="ORGANISM LIBRARY",font=("TkDefaultFont",10,"bold")).pack(anchor="w",pady=(0,4))
        cols=("family","role","dur","seed")
        self.tree=ttk.Treeview(left,columns=cols,show="tree headings",selectmode="browse")
        self.tree.heading("#0",text="Name")
        self.tree.heading("family",text="Family")
        self.tree.heading("role",text="Role")
        self.tree.heading("dur",text="Dur")
        self.tree.heading("seed",text="Seed")
        self.tree.column("#0",width=255,stretch=True)
        self.tree.column("family",width=110,stretch=False)
        self.tree.column("role",width=95,stretch=False)
        self.tree.column("dur",width=55,stretch=False,anchor="e")
        self.tree.column("seed",width=90,stretch=False,anchor="e")
        yscroll=ttk.Scrollbar(left,orient="vertical",command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.pack(side="left",fill="both",expand=True)
        yscroll.pack(side="right",fill="y")
        self.tree.bind("<<TreeviewSelect>>",self.on_select)
        self.tree.bind("<Double-1>",lambda e:self.play_selected())

        # centre waveform / breeding
        center=ttk.Frame(main,padding=4)
        main.add(center,weight=5)

        wave_header=ttk.Frame(center)
        wave_header.pack(fill="x")
        ttk.Label(wave_header,text="PHENOTYPE / WAVEFORM",font=("TkDefaultFont",10,"bold")).pack(side="left")
        ttk.Button(wave_header,text="▶ Play",command=self.play_selected).pack(side="right",padx=2)
        ttk.Button(wave_header,text="■ Stop",command=self.stop_playback).pack(side="right",padx=2)

        self.wave=WaveformCanvas(center,height=330)
        self.wave.pack(fill="both",expand=True,pady=(4,6))

        breed=ttk.LabelFrame(center,text="BREEDING CHAMBER",padding=8)
        breed.pack(fill="x")

        row=ttk.Frame(breed); row.pack(fill="x")
        ttk.Button(row,text="Set Parent A",command=lambda:self.set_parent("A")).pack(side="left",padx=2)
        self.a_label=ttk.Label(row,text="A: —",width=48)
        self.a_label.pack(side="left",padx=5)
        ttk.Button(row,text="Breed A",command=self.breed_a).pack(side="right",padx=2)

        row=ttk.Frame(breed); row.pack(fill="x",pady=(5,0))
        ttk.Button(row,text="Set Parent B",command=lambda:self.set_parent("B")).pack(side="left",padx=2)
        self.b_label=ttk.Label(row,text="B: —",width=48)
        self.b_label.pack(side="left",padx=5)
        ttk.Button(row,text="Cross A × B",command=self.cross_ab).pack(side="right",padx=2)

        row=ttk.Frame(breed); row.pack(fill="x",pady=(8,0))
        ttk.Label(row,text="Children").pack(side="left")
        self.children_var=tk.IntVar(value=16)
        ttk.Spinbox(row,from_=1,to=256,textvariable=self.children_var,width=6).pack(side="left",padx=4)
        ttk.Label(row,text="Use the Mutation slider above for genetic distance.").pack(side="left",padx=12)

        # right inspector
        right=ttk.Frame(main,padding=4)
        main.add(right,weight=3)
        ttk.Label(right,text="GENOME INSPECTOR",font=("TkDefaultFont",10,"bold")).pack(anchor="w")
        self.inspector=tk.Text(right,wrap="none",background="#111316",foreground="#dce3ea",
                               insertbackground="white",font=("TkFixedFont",9))
        self.inspector.pack(fill="both",expand=True,pady=(4,0))

        # bottom
        bottom=ttk.Frame(self.root,padding=(8,4))
        bottom.pack(fill="x")
        self.progress=ttk.Progressbar(bottom,mode="determinate",maximum=100)
        self.progress.pack(side="left",fill="x",expand=True)
        self.status=tk.StringVar(value=f"Ready — project: {self.project.root}")
        ttk.Label(bottom,textvariable=self.status).pack(side="left",padx=10)

    def new_project(self):
        path=filedialog.askdirectory(title="Choose folder for new Möbius project")
        if not path: return
        name=f"Mobius_{time.strftime('%Y%m%d_%H%M%S')}"
        self.project=MobiusProject(Path(path)/name)
        self.parent_a=self.parent_b=self.selected=None
        self.refresh_library()
        self.status.set(f"New project: {self.project.root}")

    def open_project(self):
        path=filedialog.askdirectory(title="Open Möbius project folder")
        if not path: return
        self.project=MobiusProject(Path(path))
        self.parent_a=self.parent_b=self.selected=None
        self.refresh_library()
        self.status.set(f"Opened: {self.project.root}")

    def refresh_library(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for e in self.project.entries:
            a=e.get("analysis",{})
            self.tree.insert(
                "", "end", iid=e["id"], text=e["id"],
                values=(FAMILY_ABBR.get(e["family"],e["family"]),
                        e["role"], f"{a.get('duration',0):.2f}", e["seed"])
            )
        self.a_label.config(text=f"A: {self.parent_a['id'] if self.parent_a else '—'}")
        self.b_label.config(text=f"B: {self.parent_b['id'] if self.parent_b else '—'}")

    def on_select(self,event=None):
        sel=self.tree.selection()
        if not sel: return
        e=self.project.find(sel[0])
        if not e: return
        self.selected=e
        self.show_entry(e)

    def show_entry(self,e):
        self.inspector.delete("1.0","end")
        self.inspector.insert("1.0",json.dumps(e,indent=2))
        try:
            audio,sr=read_wav_mono(self.project.sample_path(e))
            self.wave.set_audio(audio,sr,e["id"])
        except Exception as ex:
            self.wave.set_audio(None,title=f"{e['id']} — unable to read: {ex}")

    def set_parent(self,which):
        if not self.selected:
            messagebox.showinfo(APP_NAME,"Select an organism first.")
            return
        if which=="A":
            self.parent_a=self.selected
        else:
            self.parent_b=self.selected
        self.refresh_library()

    def _start_worker(self,fn):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_NAME,"A breeding/generation process is already running.")
            return
        self.progress["value"]=0
        self.worker=threading.Thread(target=fn,daemon=True)
        self.worker.start()

    def _poll_worker(self):
        try:
            while True:
                msg=self.work_q.get_nowait()
                kind=msg[0]
                if kind=="progress":
                    done,total,text=msg[1:]
                    self.progress["value"]=100*done/max(1,total)
                    self.status.set(text)
                elif kind=="done":
                    self.refresh_library()
                    self.progress["value"]=100
                    self.status.set(msg[1])
                elif kind=="error":
                    self.status.set("Error")
                    messagebox.showerror(APP_NAME,msg[1])
        except queue.Empty:
            pass
        self.root.after(100,self._poll_worker)

    def _family_choice(self):
        return None if self.family_var.get()=="ANY" else self.family_var.get()

    def _role_choice(self):
        return None if self.role_var.get()=="ANY" else self.role_var.get()

    def generate_one(self):
        def work():
            try:
                seed=random.SystemRandom().randint(1,2**31-1)
                fam=self._family_choice() or random.choice(FAMILIES)
                g=new_genome(fam,self._role_choice(),seed,self.mutation_var.get())
                e=self.project.render_genome(g,self.p6_var.get())
                self.work_q.put(("done",f"Born: {e['id']}"))
            except Exception as ex:
                self.work_q.put(("error",repr(ex)))
        self._start_worker(work)

    def generate_batch(self):
        count=max(1,int(self.count_var.get()))
        seed=random.SystemRandom().randint(1,2**31-1)
        fam=self._family_choice()
        role=self._role_choice()
        mutation=float(self.mutation_var.get())
        p6=bool(self.p6_var.get())

        def cb(done,total,e):
            self.work_q.put(("progress",done,total,f"Generating {done}/{total}: {e['id']}"))

        def work():
            try:
                generate_population(self.project,count,seed,fam,role,mutation,p6,cb)
                self.work_q.put(("done",f"Population complete — {count} organisms — seed {seed}"))
            except Exception as ex:
                self.work_q.put(("error",repr(ex)))
        self._start_worker(work)

    def breed_a(self):
        if not self.parent_a:
            messagebox.showinfo(APP_NAME,"Set Parent A first.")
            return
        count=max(1,int(self.children_var.get()))
        mutation=float(self.mutation_var.get())
        parent=dict(self.parent_a)

        def work():
            try:
                rng=np.random.default_rng(random.SystemRandom().randint(1,2**31-1))
                for i in range(count):
                    seed=int(rng.integers(1,2**31-1))
                    g=mutate_genome(parent,seed,mutation)
                    e=self.project.render_genome(g,self.p6_var.get(),"B")
                    self.work_q.put(("progress",i+1,count,f"Breeding {i+1}/{count}: {e['id']}"))
                self.work_q.put(("done",f"Born: {count} descendants of {parent['id']}"))
            except Exception as ex:
                self.work_q.put(("error",repr(ex)))
        self._start_worker(work)

    def cross_ab(self):
        if not self.parent_a or not self.parent_b:
            messagebox.showinfo(APP_NAME,"Set both Parent A and Parent B first.")
            return
        count=max(1,int(self.children_var.get()))
        mutation=float(self.mutation_var.get())
        a,b=dict(self.parent_a),dict(self.parent_b)

        def work():
            try:
                rng=np.random.default_rng(random.SystemRandom().randint(1,2**31-1))
                for i in range(count):
                    seed=int(rng.integers(1,2**31-1))
                    g=cross_genomes(a,b,seed,mutation)
                    e=self.project.render_genome(g,self.p6_var.get(),"X")
                    self.work_q.put(("progress",i+1,count,f"Crossing {i+1}/{count}: {e['id']}"))
                self.work_q.put(("done",f"Cross complete — {count} descendants"))
            except Exception as ex:
                self.work_q.put(("error",repr(ex)))
        self._start_worker(work)

    def _player_command(self,path:Path):
        candidates=[
            ("pw-play",[str(path)]),
            ("aplay",[str(path)]),
            ("ffplay",["-nodisp","-autoexit","-loglevel","quiet",str(path)]),
            ("play",[str(path)]),
        ]
        for exe,args in candidates:
            if shutil.which(exe):
                return [exe]+args
        return None

    def play_selected(self):
        if not self.selected:
            return
        self.stop_playback()
        path=self.project.sample_path(self.selected)
        cmd=self._player_command(path)
        if not cmd:
            messagebox.showinfo(APP_NAME,"No playback command found (pw-play, aplay, ffplay, or play).")
            return
        try:
            self.play_proc=subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            self.status.set(f"Playing: {self.selected['id']}")
        except Exception as ex:
            messagebox.showerror(APP_NAME,str(ex))

    def stop_playback(self):
        if self.play_proc and self.play_proc.poll() is None:
            try:
                self.play_proc.terminate()
            except Exception:
                pass
        self.play_proc=None


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def self_test(out: Path):
    print(f"{APP_NAME} {VERSION}")
    print(f"scipy={HAVE_SCIPY} soundfile={HAVE_SOUNDFILE} tkinter={HAVE_TK}")
    p=MobiusProject(out)
    seeds=[10101,20202,30303,40404,50505]
    created=[]
    for fam,seed in zip(FAMILIES,seeds):
        g=new_genome(fam,None,seed,.35)
        e=p.render_genome(g,make_p6=True)
        created.append(e)
        path=p.sample_path(e)
        audio,sr=read_wav_mono(path)
        assert sr==SR
        assert len(audio)>100
        assert np.isfinite(audio).all()
        assert float(np.max(np.abs(audio)))<=1.0
        print(f"OK {e['id']:45s} {e['analysis']['duration']:5.2f}s")

    child=mutate_genome(created[0],60606,.25)
    ce=p.render_genome(child,make_p6=False,lineage="B")
    cross=cross_genomes(created[1],created[3],70707,.42)
    xe=p.render_genome(cross,make_p6=False,lineage="X")
    print(f"Breed OK: {ce['id']}")
    print(f"Cross OK: {xe['id']}")
    print(f"Project: {p.root}")
    return 0


def cli():
    ap=argparse.ArgumentParser(description=APP_NAME)
    ap.add_argument("--generate",type=int,help="Generate N organisms without opening the GUI.")
    ap.add_argument("--out",default="Mobius_Lab",help="Project directory.")
    ap.add_argument("--seed",type=int,default=None,help="Population seed.")
    ap.add_argument("--family",choices=FAMILIES,default=None)
    ap.add_argument("--role",choices=ROLES,default=None)
    ap.add_argument("--mutation",type=float,default=.35)
    ap.add_argument("--no-p6",action="store_true",help="Do not make 44.1 kHz P-6 mirror files.")
    ap.add_argument("--self-test",action="store_true")
    args=ap.parse_args()

    if args.self_test:
        return self_test(Path(args.out))

    if args.generate:
        seed=args.seed if args.seed is not None else random.SystemRandom().randint(1,2**31-1)
        p=MobiusProject(Path(args.out))
        def cb(i,n,e):
            print(f"[{i:04d}/{n:04d}] {e['id']}")
        generate_population(
            p,args.generate,seed,args.family,args.role,
            clamp(args.mutation,.02,1.0),not args.no_p6,cb
        )
        print(f"\nPopulation seed: {seed}")
        print(f"Project: {p.root.resolve()}")
        return 0

    if not HAVE_TK:
        print("tkinter is not available. Install python3-tk or use --generate.",file=sys.stderr)
        return 2

    root=tk.Tk()
    MobiusGUI(root)
    root.mainloop()
    return 0


if __name__=="__main__":
    raise SystemExit(cli())
