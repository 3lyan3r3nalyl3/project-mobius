########################################################################
# Project Möbius — Sound Breeder v0.3
#
# This program is free software: released under the GNU General Public
# License v3.0 or later.
#
########################################################################

A graphical procedural sound-breeding environment for Linux/Python.

Sound Breeder Möbius is not primarily a sound editor. It is a **sound genetics
laboratory**: generate organisms, inspect their genomes, choose parents, breed
descendants, cross unrelated families, and export sampler-ready WAV files.

## Five ecologies

- MEMBRANES
- METALS
- PARTICULATES
- CIRCUIT_FAUNA
- ORGANIC_IMPOSSIBILITIES

Every sound also receives a practical sampler role:

- Kicks
- Snares
- Closed_Hats
- Open_Hats
- Toms
- Claps
- Percussion
- FX
- Textures

## Debian / Ubuntu setup

```bash
sudo apt install python3 python3-tk python3-numpy python3-scipy python3-soundfile
```

For convenient playback, at least one of these is useful:

```bash
sudo apt install pipewire-audio-client-libraries
sudo apt install alsa-utils
sudo apt install ffmpeg
sudo apt install sox
```

The program automatically looks for `pw-play`, `aplay`, `ffplay`, or `play`.

## Start the GUI

```bash
python3 mobius_breeder.py
```

By default it creates/opens `./Mobius_Lab`.

## The GUI

### Organism Library
Left pane. Every generated sample is listed with:
- name
- genetic family
- sampler role
- duration
- seed

Double-click an organism to audition it.

### Phenotype / Waveform
Middle pane. Audacity-like visual waveform display with Play and Stop.

### Genome Inspector
Right pane. Shows the complete JSON genome, lineage, parents, synthesis traits,
technical analysis, and output locations.

### Breeding Chamber
1. Select a sample.
2. Press `Set Parent A`.
3. Set `Children` and the Mutation slider.
4. Press `Breed A`.

For crossbreeding:
1. Set Parent A.
2. Select another sample and set Parent B.
3. Press `Cross A × B`.

Crosses between different genetic families naturally become
ORGANIC_IMPOSSIBILITIES.

## Generate 250 samples

Set Population = 250 and press `Generate Population`.

The default Family/Role values of ANY create an ecology rather than a rigid
fixed count per category.

Mutation controls genetic distance:
- ~0.10 = close siblings
- ~0.25 = recognizable descendants
- ~0.50 = adventurous mutation
- ~0.80 = distant / unstable descendants
- ~1.00 = maximum mutation

## Output

A project looks like:

```text
Mobius_Lab/
├── Samples_48k16/
│   ├── Kicks/
│   ├── Snares/
│   ├── Closed_Hats/
│   ├── Open_Hats/
│   ├── Toms/
│   ├── Claps/
│   ├── Percussion/
│   ├── FX/
│   └── Textures/
├── P6_44k1_16/
│   └── [same practical folders]
├── Families/
│   ├── MEMBRANES.m3u
│   ├── METALS.m3u
│   ├── PARTICULATES.m3u
│   ├── CIRCUIT_FAUNA.m3u
│   └── ORGANIC_IMPOSSIBILITIES.m3u
└── Metadata/
    ├── manifest.json
    └── manifest.csv
```

`Samples_48k16` is the canonical 48 kHz / 16-bit mono library for samplers and
external processing.

With `P-6 mirror` enabled, every organism also receives a 44.1 kHz / 16-bit
mono version.

## Command line twin

The GUI is optional.

```bash
python3 mobius_breeder.py --generate 250 --out Mobius_001 --seed 918273
```

Only one family:

```bash
python3 mobius_breeder.py \
  --generate 50 \
  --family METALS \
  --out Alloy_Test
```

Only a practical role:

```bash
python3 mobius_breeder.py \
  --generate 40 \
  --role Closed_Hats \
  --out Hat_Test
```

No P-6 mirror:

```bash
python3 mobius_breeder.py --generate 250 --no-p6
```

Self-test:

```bash
python3 mobius_breeder.py --self-test --out Mobius_Test
```

## Philosophy

The generator creates abundance. Human listening supplies selection.

A sound is not merely a file. It is:
- a phenotype,
- a genome,
- a seed,
- a lineage,
- and a possible parent of future sounds.

That is here the Möbius loop: samples return to the engine as ancestors.

The samples were basically thought of to be used either in Roland P-6,
Elektron Model:Samples and Elektron Tonverk.
