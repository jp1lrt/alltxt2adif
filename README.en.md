# ALLTXT2ADIF

🛰 **Recover lost FT8 / FT4 logs from WSJT-X or JTDX ALL.TXT**

If your PC crashed and you lost:

- `wsjtx_log.adi`
- `wsjtx.log`

…but **ALL.TXT still exists**,  
this tool can reconstruct many of your QSOs.

ALLTXT2ADIF analyzes decode history and rebuilds probable QSOs, exporting them as **standard ADIF logs** with confidence tagging.

🌐 [日本語 README](README.md)

<img width="822" height="652" alt="image" src="https://github.com/user-attachments/assets/8f11b6ba-7eeb-4b22-b0ee-0f82896fdf4b" />
---

# Typical Recovery Scenario

```
PC crash
↓
wsjtx_log.adi lost
wsjtx.log lost
↓
ALL.TXT still exists
↓
Run ALLTXT2ADIF
↓
Recovered ADIF log
```

This situation is more common than many operators expect.

ALLTXT2ADIF was created specifically to help recover logs after such incidents.

---

# Design Philosophy

This tool is **not designed to blindly output everything possible.**

Instead, it focuses on **explainable recovery**:

- Every recovered QSO receives a **confidence tag (high / medium / low)**
- Uncertain QSOs are exported to a **review CSV** for manual verification
- The tool acts as a **recovery aid**, not a replacement for logging software

The operator remains in control of the final log.

---

# Key Features

🔍 **Recover QSOs from decode history**  
Reconstruct probable QSOs using message patterns and timing.

📋 **Standard ADIF output**  
Compatible with logging software, LoTW, eQSL, etc.

🏷 **Confidence tagging**  
Each recovered QSO includes evidence strength: `high` / `medium` / `low`

📊 **Review CSV**  
Export uncertain QSOs for manual inspection.

🔄 **Strict / Lenient modes**  
Choose conservative or aggressive recovery behavior.

🖥 **Simple Windows GUI**  
Just run the executable — no Python required.

⚙ **CLI version available**  
Works on Linux / macOS with Python.

---

# Confidence Levels

| confidence | meaning |
|---|---|
| `high` | Strong evidence (RR73 exchange etc.) |
| `medium` | Likely QSO |
| `low` | Weak evidence — manual review recommended |

---

# Example Output

Recovered ADIF records are sorted chronologically:

```
QSO_DATE → TIME_ON
```

Oldest QSO appears first. Confidence tags are included:

```
APP_ALLTXT2ADIF_CONFIDENCE:high
```

This makes it easy to review uncertain records.

---

# GUI Usage (Windows)

1️⃣ Launch `alltxt2adif.exe`  
2️⃣ Select `ALL.TXT`  
3️⃣ Enter your callsign  
4️⃣ Choose output ADIF file  
5️⃣ Click **Start Recovery**

The GUI builds the correct command automatically.

---

# CLI Usage

Basic usage:

```bash
python convert_all_to_adif.py ALL.TXT -o recovered.adi --station-call YOURCALL
```

Recommended (with review CSV):

```bash
python convert_all_to_adif.py ALL.TXT \
  -o recovered.adi \
  --station-call YOURCALL \
  --review-csv review.csv
```

---

# Options

| Option | Description |
|---|---|
| `--station-call` | Your callsign |
| `-o` | Output ADIF file |
| `--mode strict\|lenient` | Recovery mode (default: strict) |
| `--review-csv` | Export uncertain QSOs |
| `--review-level` | Confidence threshold for review |
| `--window-sec N` | Evidence time window in seconds |
| `--merge-window` | Duplicate merge window |
| `--no-confidence` | Omit confidence fields |

---

# Known Behavior

- Default evidence window is **120 seconds** for all modes.  
  Override for specific modes:

  ```
  --window-sec 60    # FT4
  --window-sec 180   # Q65 / EME
  ```

- Recovered QSOs are sorted by **QSO_DATE → TIME_ON** (oldest first).
- FT8 / FT2 and other modes (JT65, JT9, MSK144, etc.) use a 120-second window. Mode-optimized windows are only applied for FT4 (60s) and Q65 (180s).

---

# Location of ALL.TXT

**WSJT-X**

```
C:\Users\<username>\AppData\Local\WSJT-X\ALL.TXT
```

**JTDX**

```
C:\Users\<username>\AppData\Local\JTDX\ALL.TXT
```

---

# Important: Split ALL.TXT Files

### JTDX

JTDX automatically **splits ALL.TXT monthly**:

```
202506_ALL.TXT
202507_ALL.TXT
202508_ALL.TXT
```

Process each file individually.

### WSJT-X

WSJT-X can optionally split ALL.TXT using:

```
Split ALL.TXT yearly
Split ALL.TXT monthly
```

If enabled, process each generated file separately.

---

# Recommended Workflow

⚠ **Always verify recovered logs before uploading.**

Suggested workflow:

1. Run recovery
2. Import ADIF into your logging software
3. Inspect `low` and `medium` confidence QSOs
4. Correct or remove uncertain entries

Especially important before submitting to:

- LoTW
- eQSL
- Contest logs

---

# Download

Latest release:  
https://github.com/jp1lrt/alltxt2adif/releases/latest

Files included:

- `alltxt2adif.exe` — Windows executable
- `checksums.txt` — SHA256 checksums
- `checksums.txt.asc` — GPG signature

---

# Verifying the Download

### VirusTotal

v4.1.1 scan:  
https://www.virustotal.com/gui/file/753879d5e9cead7e5824448720ae99e9664dc29f2c598ed58c0c458c02dc90ce/detection

**7 / 72** detections (as of 2026-03-05)

> ⚠ PyInstaller-built Python executables commonly trigger false positives in ML-based scanners.  
> Full source code is available in this repository — you can build it yourself.

### SHA256 Verification (PowerShell)

```powershell
Get-FileHash .\alltxt2adif.exe -Algorithm SHA256
```

Expected hash for v4.1.1:

```
753879D5E9CEAD7E5824448720AE99E9664DC29F2C598ED58C0C458C02DC90CE
```

Compare with `checksums.txt`.

### GPG Signature Verification

```powershell
Invoke-WebRequest -Uri https://github.com/jp1lrt.gpg -OutFile mypubkey.asc
gpg --import mypubkey.asc
gpg --verify checksums.txt.asc checksums.txt
```

Expected result: **Good signature**

- Key ID: `864FA6445EE4D4E3`
- UID: `Yoshiharu Tsukuura <jp1lrt@jarl.com>`

---

# License

GPL v3

---

# Author

**Yoshiharu Tsukuura — JP1LRT**  
Amateur Radio Operator  
https://www.qrz.com/db/JP1LRT  
https://github.com/jp1lrt

---

# Support

If this tool helped recover your log, consider buying me a coffee ☕

[![Donate](https://img.shields.io/badge/Donate-PayPal-blue)](https://www.paypal.me/jp1lrt)
[![Coffee](https://img.shields.io/badge/Coffee-%E2%98%95-yellow)](https://www.paypal.me/jp1lrt)
