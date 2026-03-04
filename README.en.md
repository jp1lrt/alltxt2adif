# ALLTXT2ADIF

**ADIF Log Recovery Tool for WSJT-X / JTDX**

Reconstructs ADIF logs from `ALL.TXT` decode history when log files have been lost.  
Analyzes decode messages and rebuilds probable QSOs with confidence tagging.

🌐 [日本語はこちら](README.md)

---

## Design Philosophy

This tool is not designed to "output everything possible."  
It is designed to **explain why each QSO is considered valid.**

- Every record receives a **confidence tag (high / medium / low)** based on evidence strength
- Uncertain QSOs are exported to a separate **review CSV** for human verification
- This is a **log recovery aid**, not a replacement for official logging software

---

## Features

- 🔍 **QSO Recovery** — Rebuild QSOs from ALL.TXT decode history
- 📋 **ADIF Output** — Standard ADIF format (v3.1.6)
- 🏷️ **Confidence Tagging** — Three-level evidence classification
- 📊 **Review CSV** — Export low / medium confidence QSOs for manual review
- 🔄 **Strict / Lenient Modes** — Control recovery aggressiveness
- 🖥️ **Windows GUI** — Easy-to-use GUI application (alltxt2adif.exe)

---

## Confidence Tags

| confidence | meaning |
|---|---|
| `high` | Strong evidence of completed QSO (RR73 received, both RST confirmed, etc.) |
| `medium` | Likely QSO (one-sided evidence, etc.) |
| `low` | Weak evidence — manual review recommended |

---

## ALL.TXT Location

**WSJT-X**
```
C:\Users\<username>\AppData\Local\WSJT-X\ALL.TXT
```

**JTDX**
```
C:\Users\<username>\AppData\Local\JTDX\ALL.TXT
```

---

## GUI Usage (Windows)

1. Launch `alltxt2adif.exe`
2. Select ALL.TXT
3. Enter your station callsign
4. Specify the output ADIF file
5. Click "Start Recovery"

---

## CLI Usage

```bash
python convert_all_to_adif.py ALL.TXT -o recovered.adi --station-call YOURCALL
```

With review CSV (recommended):

```bash
python convert_all_to_adif.py ALL.TXT \
  -o recovered.adi \
  --station-call YOURCALL \
  --review-csv review.csv
```

---

## Options

| Option | Description |
|---|---|
| `--station-call` | Your callsign |
| `-o` | Output ADIF file |
| `--mode strict\|lenient` | Recovery mode (default: strict) |
| `--review-csv` | Export uncertain QSOs to CSV |
| `--review-level` | Review threshold |
| `--window-sec N` | Evidence time window in seconds |
| `--merge-window` | Duplicate merge window |
| `--no-confidence` | Omit confidence fields from output |

---

## Known Behavior

- Default time window is **120 seconds** for all modes.  
  For FT4 or Q65 operation, specify explicitly:
  ```
  --window-sec 60    # FT4
  --window-sec 180   # Q65 / EME
  ```
- Recovered QSOs are sorted by **QSO_DATE → TIME_ON** ascending (oldest first).

---

## Recommended Workflow

⚠️ **Always review the recovered log before use.**

Manual verification is especially important for:

- LoTW / eQSL uploads
- Contest log submissions

Using `--review-csv` and inspecting low / medium confidence records is the safest approach.

---

## Download

Official distribution via GitHub Releases.

- Latest release: https://github.com/jp1lrt/alltxt2adif/releases/latest
- `alltxt2adif.exe` — Windows executable
- `checksums.txt` — SHA256 checksums
- `checksums.txt.asc` — GPG signature

---

## Verifying the Downloaded Binary

### VirusTotal Scan

v4.1.1 scan result:  
https://www.virustotal.com/gui/file/ab9934ac644535b9d05f0aed428001ab13c02d56f7e7ccd9b221065614869d42/detection

**4 / 70** vendors flagged (as of 2026-03-04)

> ⚠️ PyInstaller-packaged Python executables are widely known to trigger  
> false positives in ML-based scanners.  
> The full source code is available in this repository — you can build it yourself to verify.

### SHA256 Checksum Verification (PowerShell)

```powershell
Get-FileHash .\alltxt2adif.exe -Algorithm SHA256
```

Expected hash for v4.1.1:

```
AB9934AC644535B9D05F0AED428001AB13C02D56F7E7CCD9B221065614869D42
```

Compare the output with `checksums.txt`.

### GPG Signature Verification

```powershell
# Import public key
Invoke-WebRequest -Uri https://github.com/jp1lrt.gpg -OutFile mypubkey.asc
gpg --import mypubkey.asc

# Verify signature
gpg --verify checksums.txt.asc checksums.txt
```

You should see **"Good signature"** with:

- Key ID: `864FA6445EE4D4E3`
- UID: `Yoshiharu Tsukuura <jp1lrt@jarl.com>`

---

## License

GPL v3

---

## Author

**津久浦 慶治 / Yoshiharu Tsukuura**  
Amateur Radio Station **JP1LRT** / [@jp1lrt](https://github.com/jp1lrt)
https://www.qrz.com/db/JP1LRT

---

## Donate

If this tool has been useful to you, any support is greatly appreciated 🪙

[![Donate](https://img.shields.io/badge/Donate-PayPal-blue)](https://www.paypal.me/jp1lrt)
[![Coffee](https://img.shields.io/badge/Coffee-%E2%98%95-yellow)](https://www.paypal.me/jp1lrt)
