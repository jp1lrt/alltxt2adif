#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_all_to_adif.py  v4.1.1
ALL.TXT (WSJT-X / JTDX) -> ADIF

Release (4.1.1):
- Bumped VERSION to 4.1.1 for release packaging.
- Includes validated V6 codebase (process_wsjtx present).
- Features/fixes:
  - APP_ALLTXT2ADIF_SOURCE output for JTDX qso_logged records.
  - Contest rr73 handling (promotion on contest frequencies).
  - Grid+73 detection limited to contest frequencies (tight tolerance).
  - APP_ALLTXT2ADIF_COMPLETION field added ('confirmed'|'provisional').
  - Dedupe improvements and post-merge pass.
  - sanitize_msg auto-remove option (--sanitize-auto).
  - Mode-aware default windows (FT4=60s, FT8=120s, Q65=180s).
  - --mode strict|lenient option for Rx-only handling.
"""
from __future__ import annotations
import re
import argparse
import bisect
import csv
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any

# Version constant used in ADIF header
VERSION = '4.1.1'

# ---------- Helpers ----------
def year_from_two_digit(yy: str) -> int:
    return 2000 + int(yy)

def parse_ts_generic(ts_str: str) -> Optional[datetime]:
    ts_clean = re.sub(r'\.\d+\(\d+\)', '', ts_str.strip())
    m8 = re.match(r'^(?P<y4>\d{4})(?P<m>\d{2})(?P<d>\d{2})_(?P<H>\d{2})(?P<M>\d{2})(?P<S>\d{2})$', ts_clean)
    if m8:
        try:
            return datetime(int(m8.group('y4')), int(m8.group('m')), int(m8.group('d')),
                            int(m8.group('H')), int(m8.group('M')), int(m8.group('S')))
        except Exception:
            return None
    m6 = re.match(r'^(?P<y2>\d{2})(?P<m>\d{2})(?P<d>\d{2})_(?P<H>\d{2})(?P<M>\d{2})(?P<S>\d{2})$', ts_clean)
    if m6:
        try:
            y = year_from_two_digit(m6.group('y2'))
            return datetime(y, int(m6.group('m')), int(m6.group('d')),
                            int(m6.group('H')), int(m6.group('M')), int(m6.group('S')))
        except Exception:
            return None
    return None

def safe_float(s: Any) -> Optional[float]:
    """Safe float conversion — returns None on failure instead of raising."""
    try:
        return float(s)
    except (TypeError, ValueError):
        return None

def freq_to_band(freq_mhz: float) -> str:
    f = safe_float(freq_mhz)
    if f is None: return ''
    if 1.8 <= f < 2.0: return '160m'
    if 3.5 <= f < 4.0: return '80m'
    if 7.0 <= f < 7.35: return '40m'   # upper extended: 7.300 MHz is valid 40m
    if 10.1 <= f < 10.15: return '30m'
    if 14.0 <= f < 14.35: return '20m'
    if 18.068 <= f < 18.168: return '17m'
    if 21.0 <= f < 21.45: return '15m'
    if 24.89 <= f < 24.99: return '12m'
    if 28.0 <= f < 29.7: return '10m'
    # 60m
    if 5.25 <= f < 5.45: return '60m'
    if 50.0 <= f < 54.0: return '6m'
    if 144.0 <= f < 148.0: return '2m'
    return ''

# ---------- Regex / token patterns ----------
re_wsjtx = re.compile(
    r'^(?P<ts>\d{6}_\d{6}|\d{8}_\d{6})\s+'
    r'(?P<freq>\d+\.\d+)\s+'
    r'(?P<dir>Rx|Tx)\s+'
    r'(?P<mode>\S+)\s+'
    r'(?P<snr>-?\d+)\s+'
    r'(?P<dt>[-\d\.]+)\s+'
    r'(?P<bin>\d+)\s+'
    r'(?P<msg>.+)$'
)
re_jtdx_trans = re.compile(
    r'^(?P<ts>\d{8}_\d{6}(?:\.\d+\(\d+\))?)\s+Transmitting\s+(?P<mhz>[\d\.]+)\s+MHz.*?(?P<mode>FT\d):\s*(?P<msg>.+)$',
    re.I
)
re_jtdx_decode = re.compile(r'^(?P<ts>\d{8}_\d{6})\s+(?P<snr>-?\d+)\s+(?P<dt>[-\d\.]+)\s+(?P<bin>\d+)\s+~\s+(?P<msg>.+)$')
re_jtdx_qso_logged = re.compile(r'^(?P<ts>\d{8}_\d{6}(?:\.\d+\(\d+\))?)\s+QSO logged:\s*(?P<call>\S+)', re.I)

# report token (RR73 / 73 / R+02 / +02 / -11 / R standalone)
re_report_token = re.compile(r'^(?:RRR|RR?73|73|[Rr][+\-]\d{1,3}|[+\-]\d{1,3}|R)$')
re_report_in_text = re.compile(r'\b(?:RRR|RR?73|73|[Rr]?[+\-]?\d{1,3})\b', re.I)
re_grid_strict = re.compile(r'^[A-R]{2}\d{2}(?:[A-X]{2})?$', re.I)
re_call_candidate = re.compile(r'^(?=[A-Z0-9/]{3,15}$)(?=.*[A-Z])(?=.*\d)[A-Z0-9/]+$', re.I)
# Noise tokens: standard + Q65 decode quality suffix (q0, q1, ...) + R standalone handled separately
_noise_tokens = set(['CQ', 'DX', '<...>', ',', 'WW'])
_q65_suffix_re = re.compile(r'^[aq]\d{1,2}$', re.I)  # matches a1/a2/q1/q32 etc.

# ---------- Token utilities ----------
def tokenize_msg(msg: str, *, keep_noise: bool = False, upper: bool = True) -> List[str]:
    """Tokenize message.

    - Removes known noise tokens (CQ/DX/...) unless keep_noise=True (used for semantic parsing).
    - Removes decode quality suffix tokens like a1/a2/q3/q32 etc.
    - By default returns UPPERCASE tokens for consistent matching.
    """
    raw = (msg or '').strip().split()
    toks: List[str] = []
    for t in raw:
        if _q65_suffix_re.match(t):
            continue
        if (not keep_noise) and (t.upper() in _noise_tokens):
            continue
        toks.append(t.upper() if upper else t)
    return toks

def extract_callee_caller(msg: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract (callee, caller) from an FT8/FT4 free-text message.

    FT8/FT4 standard message structure (in human-readable decode):
        CALLEE  CALLER  INFO...

    This helper returns the first two *call-looking* tokens after basic tokenization.
    It intentionally ignores report tokens (RR73/73/+nn/R-nn/R) and grid tokens.

    Returns (None, None) if it cannot confidently extract both calls.
    """
    toks = tokenize_msg(msg, keep_noise=True)
    calls: List[str] = []
    for t in toks:
        if re_report_token.match(t):
            continue
        if re_grid_strict.match(t):
            continue
        if re_call_candidate.match(t):
            calls.append(t)
            if len(calls) >= 2:
                break
    if len(calls) >= 2:
        return calls[0], calls[1]
    return None, None

def classify_tokens(msg: str) -> Tuple[List[str], List[Tuple[int, str]], List[Tuple[int, str]]]:
    toks = tokenize_msg(msg)
    calls = []
    grids = []
    for i, t in enumerate(toks):
        # Report check first — prevents RR73 / 73 from matching as grid (RR73 looks like 4-char grid)
        if re_report_token.match(t):
            continue
        if re_grid_strict.match(t):
            grids.append((i, t.upper()))
            continue
        if re_call_candidate.match(t):
            calls.append((i, t))
    return toks, calls, grids

def associate_grid_to_call(toks: List[str], calls_with_pos: List[Tuple[int, str]], grids_with_pos: List[Tuple[int, str]]) -> Dict[str, str]:
    """Associate grid tokens to call tokens. Prefer CALL GRID (c_idx+1==g_idx) pattern; fallback to nearest (distance<=2). Keys uppercased."""
    mapping: Dict[str, str] = {}
    calls_pos_upper = [(c_idx, c.upper()) for (c_idx, c) in calls_with_pos]
    for g_idx, g in grids_with_pos:
        assigned = False
        for c_idx, c_upper in calls_pos_upper:
            if c_idx + 1 == g_idx:
                mapping[c_upper] = g.upper()
                assigned = True
                break
        if assigned:
            continue
        best = None
        bestd = None
        for c_idx, c_upper in calls_pos_upper:
            d = abs(g_idx - c_idx)
            if best is None or d < bestd:
                best = c_upper
                bestd = d
        if best is not None and bestd is not None and bestd <= 2:
            mapping[best] = g.upper()
    return mapping

def extract_partner_grid(msgs_with_dir: List[Tuple[str, str]], station_call: str, partner: str) -> str:
    """Return the partner's grid square from the exchange messages."""
    p_upper = partner.upper()
    for dir_, msg in msgs_with_dir:
        toks = tokenize_msg(msg, keep_noise=True, upper=True)
        if not toks:
            continue
        call_toks = []
        for t in toks:
            if re_report_token.match(t):
                continue
            if re_grid_strict.match(t):
                continue
            if re_call_candidate.match(t):
                call_toks.append(t)
        if len(call_toks) < 2:
            continue
        sender = call_toks[1]
        if sender != p_upper:
            continue
        _, calls_pos, grids_pos = classify_tokens(msg)
        if not grids_pos:
            continue
        mapping = associate_grid_to_call(toks, calls_pos, grids_pos)
        gs = mapping.get(p_upper)
        if gs:
            return gs
        # fallback: partner に最も近い grid を返す（先頭gridは誤取得リスクあり）
        if grids_pos:
            # calls_pos から partner の token index を探す
            _, calls_pos_f, _ = classify_tokens(msg)
            p_idx = next((c_idx for c_idx, c in calls_pos_f if c.upper() == p_upper), None)
            if p_idx is not None:
                nearest = min(grids_pos, key=lambda x: abs(x[0] - p_idx))
                return nearest[1].upper()
    return ''

# ---------- Merge / dedupe ----------
def merge_records(records: List[Dict], merge_window_sec: int = 60) -> List[Dict]:
    """
    Merge records grouped by (CALL, BAND).
    Records with unparsable/missing timestamps are not merged and appended
    as-is to the end of the result with a warning (they are never lost).
    """
    def to_dt_safe(qdate: str, tstr: str) -> Optional[datetime]:
        try:
            return datetime.strptime(qdate + tstr, '%Y%m%d%H%M%S')
        except Exception:
            return None

    # Partition: valid records only enter the merge logic
    valid_records: List[Dict] = []
    invalid_records: List[Dict] = []
    for r in records:
        dt_on  = to_dt_safe(r.get('QSO_DATE', ''),     r.get('TIME_ON',  ''))
        dt_off = to_dt_safe(r.get('QSO_DATE_OFF', ''), r.get('TIME_OFF', ''))
        if dt_on is None or dt_off is None:
            invalid_records.append(r)
        else:
            valid_records.append(r)

    if invalid_records:
        print(f"Warning: {len(invalid_records)} record(s) have invalid/missing timestamps "
              f"and will be left unmerged.", flush=True)

    grouped: Dict[Tuple[str, str], List[Dict]] = {}
    for r in valid_records:
        key = (r['CALL'], r.get('BAND', ''))
        grouped.setdefault(key, []).append(r)

    merged_all = []
    for key, recs in grouped.items():
        def sort_key(x: Dict) -> Tuple[str, str]:
            return (x.get('QSO_DATE', ''), x.get('TIME_ON', ''))
        recs_sorted = sorted(recs, key=sort_key)

        cur = recs_sorted[0].copy()
        cur_on  = to_dt_safe(cur['QSO_DATE'],     cur['TIME_ON'])
        cur_off = to_dt_safe(cur['QSO_DATE_OFF'], cur['TIME_OFF'])
        for nx in recs_sorted[1:]:
            nx_on  = to_dt_safe(nx['QSO_DATE'],     nx['TIME_ON'])
            nx_off = to_dt_safe(nx['QSO_DATE_OFF'], nx['TIME_OFF'])
            if nx_on is None or nx_off is None:
                continue  # prefiltered above; guard anyway
            gap = (nx_on - cur_off).total_seconds()
            freq_ok = True
            try:
                if cur.get('FREQ') and nx.get('FREQ'):
                    freq_ok = abs(float(cur['FREQ']) - float(nx['FREQ'])) < 0.05
            except Exception:
                freq_ok = True
            if (nx_on <= cur_off) or (0 < gap <= merge_window_sec and freq_ok):
                if nx_off > cur_off:
                    cur['TIME_OFF']     = nx['TIME_OFF']
                    cur['QSO_DATE_OFF'] = nx['QSO_DATE_OFF']
                    cur_off = nx_off
                if nx_on < cur_on:
                    cur['TIME_ON']  = nx['TIME_ON']
                    cur['QSO_DATE'] = nx['QSO_DATE']
                    cur_on = nx_on
                if not cur.get('FREQ')     and nx.get('FREQ'):     cur['FREQ']     = nx['FREQ']
                if not cur.get('RST_SENT') and nx.get('RST_SENT'): cur['RST_SENT'] = nx['RST_SENT']
                if not cur.get('RST_RCVD') and nx.get('RST_RCVD'): cur['RST_RCVD'] = nx['RST_RCVD']
                if not cur.get('GRIDSQUARE') and nx.get('GRIDSQUARE'): cur['GRIDSQUARE'] = nx['GRIDSQUARE']
            else:
                merged_all.append(cur)
                cur = nx.copy()
                cur_on  = to_dt_safe(cur['QSO_DATE'],     cur['TIME_ON'])
                cur_off = to_dt_safe(cur['QSO_DATE_OFF'], cur['TIME_OFF'])
        merged_all.append(cur)

    merged_sorted = sorted(merged_all, key=lambda r: (r['QSO_DATE'], r['TIME_ON']))

    # Append invalid records unchanged so they are never silently lost
    if invalid_records:
        merged_sorted.extend(invalid_records)

    return merged_sorted

def dedupe_by_time_and_freq(records: List[Dict], merge_window_sec: int = 30, freq_tol_mhz: float = 0.05) -> List[Dict]:
    """
    Post-merge pass: for same CALL, merge records that overlap or are within merge_window_sec
    and whose frequencies are within freq_tol_mhz. Helps absorb duplicates caused by slight
    lookback timestamp differences.
    """
    res: List[Dict] = []
    # sort by CALL, then QSO_DATE+TIME_ON
    recs_sorted = sorted(records, key=lambda r: (r['CALL'].upper(), r.get('QSO_DATE',''), r.get('TIME_ON','')))
    i = 0
    n = len(recs_sorted)
    while i < n:
        base = recs_sorted[i].copy()
        try:
            base_on = datetime.strptime(base['QSO_DATE'] + base['TIME_ON'], '%Y%m%d%H%M%S')
            base_off = datetime.strptime(base['QSO_DATE_OFF'] + base['TIME_OFF'], '%Y%m%d%H%M%S')
        except Exception:
            res.append(base)
            i += 1
            continue
        j = i + 1
        while j < n and recs_sorted[j]['CALL'].upper() == base['CALL'].upper():
            nxt = recs_sorted[j]
            try:
                nxt_on = datetime.strptime(nxt['QSO_DATE'] + nxt['TIME_ON'], '%Y%m%d%H%M%S')
                nxt_off = datetime.strptime(nxt['QSO_DATE_OFF'] + nxt['TIME_OFF'], '%Y%m%d%H%M%S')
            except Exception:
                break
            # compute gap: if nxt_on <= base_off overlap; else gap = nxt_on - base_off
            if nxt_on <= base_off:
                time_overlap = True
                gap = 0
            else:
                gap = (nxt_on - base_off).total_seconds()
                time_overlap = 0 <= gap <= merge_window_sec
            # freq comparison
            try:
                f1 = safe_float(str(base.get('FREQ') or ''))
                f2 = safe_float(str(nxt.get('FREQ') or ''))
                freq_ok = (f1 is None or f2 is None) or (abs(f1 - f2) <= freq_tol_mhz)
            except Exception:
                freq_ok = True
            if time_overlap and freq_ok:
                # merge nxt into base (extend on/off, fill missing fields)
                if nxt_off > base_off:
                    base['TIME_OFF'] = nxt['TIME_OFF']
                    base['QSO_DATE_OFF'] = nxt['QSO_DATE_OFF']
                    base_off = nxt_off
                if nxt_on < base_on:
                    base['TIME_ON'] = nxt['TIME_ON']
                    base['QSO_DATE'] = nxt['QSO_DATE']
                    base_on = nxt_on
                for fld in ['FREQ','RST_SENT','RST_RCVD','GRIDSQUARE','MODE','BAND','STATION_CALLSIGN']:
                    if not base.get(fld) and nxt.get(fld):
                        base[fld] = nxt[fld]
                j += 1
            else:
                break
        res.append(base)
        i = j
    return res

# ---------- Report parsing helpers ----------
def normalize_report_token(tok: str) -> Optional[str]:
    if not tok:
        return None
    t = tok.strip()
    if re.fullmatch(r'73|RR73|RRR', t, re.I):
        return None
    # Standalone R = receipt acknowledgement, not a numeric RST value
    if re.fullmatch(r'R', t, re.I):
        return None
    if t.startswith(('R', 'r')):
        t2 = t[1:]
    else:
        t2 = t
    m = re.match(r'^([+\-]?\d{1,3})$', t2)
    if m:
        val = m.group(1)
        if val[0] not in ['+', '-'] and val.isdigit():
            val = '+' + val
        return val
    return None

def assign_reports_from_msg(msg: str, station_call: str, partner: str,
                            current_sent: Optional[str], current_rcvd: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    toks, calls_pos, grids_pos = classify_tokens(msg)
    pos_station = None
    pos_partner = None
    for i, t in enumerate(toks):
        ut = t.upper()
        if ut == station_call.upper() and pos_station is None:
            pos_station = i
        if ut == partner.upper() and pos_partner is None:
            pos_partner = i
    # Only process reports when BOTH station and partner appear in the message.
    if pos_station is None or pos_partner is None:
        return current_sent, current_rcvd
    report_tokens = [t for t in toks if re_report_token.match(t)]
    for rt in report_tokens:
        norm = normalize_report_token(rt)
        if not norm:
            continue
        # FT8 structure: CALLEE CALLER INFO
        if pos_partner < pos_station:
            if not current_sent:
                current_sent = norm
        else:
            if not current_rcvd:
                current_rcvd = norm
    return current_sent, current_rcvd

# ---------- JTDX processor ----------
def process_jtdx(lines: List[str], station_call: Optional[str], window_sec: int, mode_setting: str, *, sanitize_auto: bool = False) -> Tuple[List[Dict], Dict]:
    events = []
    warned_sanitize = False
    for L in lines:
        s_raw = L.rstrip('\n')
        s, changed = sanitize_msg(s_raw, auto=sanitize_auto)
        if changed and (not sanitize_auto) and (not warned_sanitize):
            print("Warning: control characters detected in input; use --sanitize-auto to auto-remove them.", flush=True)
            warned_sanitize = True
        s = s.strip()
        if not s:
            continue
        m_t = re_jtdx_trans.match(s)
        if m_t:
            ts = parse_ts_generic(m_t.group('ts'))
            if ts is None:
                continue  # skip lines with unparseable timestamp
            events.append({'type': 'transmit', 'ts': ts, 'freq': m_t.group('mhz'), 'mode': m_t.group('mode'), 'msg': m_t.group('msg')})
            continue
        m_q = re_jtdx_qso_logged.match(s)
        if m_q:
            ts = parse_ts_generic(m_q.group('ts'))
            if ts is None:
                continue  # skip lines with unparseable timestamp
            events.append({'type': 'qso_logged', 'ts': ts, 'call': m_q.group('call')})
            continue
        m_d = re_jtdx_decode.match(s)
        if m_d:
            ts = parse_ts_generic(m_d.group('ts'))
            if ts is None:
                continue  # skip lines with unparseable timestamp
            events.append({'type': 'decode', 'ts': ts, 'msg': m_d.group('msg')})
            continue

    records: List[Dict] = []

    # Build a set of (call, approx_time) covered by QSO logged entries
    logged_calls: List[Tuple[str, Any]] = []
    for ev in events:
        if ev['type'] == 'qso_logged' and ev.get('ts') and ev.get('call'):
            logged_calls.append((ev['call'].upper(), ev['ts']))

    def is_covered_by_logged(call: str, ts: Any) -> bool:
        cu = call.upper()
        for lc, lt in logged_calls:
            if lc == cu and lt is not None and ts is not None:
                diff = (lt - ts).total_seconds()
                if -30 <= diff <= 300:
                    return True
        return False

    # Pass 1: transmit-as-completion  (only for QSOs NOT covered by QSO logged)
    for ei, ev in enumerate(events):
        if ev['type'] != 'transmit' or not ev.get('msg') or not station_call:
            continue
        toks = tokenize_msg(ev['msg'])
        if station_call.upper() not in toks:
            continue
        if not re_report_in_text.search(ev['msg']):
            continue
        toks_all, calls_pos, grids_pos = classify_tokens(ev['msg'])
        partners = [tok for idx, tok in calls_pos if tok.upper() != station_call.upper()]
        if not partners:
            continue
        partner = partners[0]
        time_off = ev['ts']
        # Skip if QSO logged covers this partner+time
        if is_covered_by_logged(partner, time_off):
            continue
        # find time_on
        time_on = None
        for back_ev in reversed(events[:ei]):
            if back_ev.get('ts') is None:
                continue
            if (time_off - back_ev['ts']).total_seconds() > window_sec:
                break
            if back_ev['type'] in ('transmit', 'decode'):
                btoks = tokenize_msg(back_ev.get('msg', ''))
                if (station_call.upper() in btoks) and (partner.upper() in btoks):
                    time_on = back_ev['ts']
                    break
        if not time_on:
            time_on = time_off
        rst_sent, rst_rcvd = None, None
        for ewin in events[max(0, ei - 8): ei + 3]:
            if ewin.get('msg'):
                rst_sent, rst_rcvd = assign_reports_from_msg(ewin['msg'], station_call, partner, rst_sent, rst_rcvd)
        band = ''
        try:
            band = freq_to_band(float(ev['freq']))
        except Exception:
            pass
        rec = {
            'CALL': partner,
            **dict(zip(('QSO_DATE','TIME_ON','QSO_DATE_OFF','TIME_OFF'),
                       normalize_on_off(time_on, time_off))),
            'MODE': ev.get('mode', 'FT8'),
            'BAND': band,
            'FREQ': ev.get('freq', ''),
            'RST_SENT': rst_sent or '',
            'RST_RCVD': rst_rcvd or '',
            'STATION_CALLSIGN': station_call or '',
            'GRIDSQUARE': ''
        }
        if not re_report_token.match(rec['CALL']):
            records.append(rec)

    # Pass 2: QSO logged (authoritative — each entry = one confirmed QSO)
    for i, ev in enumerate(events):
        if ev['type'] != 'qso_logged':
            continue
        call = ev['call']
        t_end = ev['ts']
        cand = {
            'CALL': call, 'TIME_OFF': t_end, 'TIME_ON': None,
            'FREQ': None, 'MODE': None,
            'RST_SENT': '', 'RST_RCVD': '', 'GRIDSQUARE': ''
        }
        for j in range(i - 1, -1, -1):
            e2 = events[j]
            if e2.get('ts') is None:
                continue
            delta = (t_end - e2['ts']).total_seconds()
            if delta > 300:
                break
            if delta < 0:
                continue
            try:
                if e2['type'] == 'transmit':
                    if not cand['TIME_ON']:
                        cand['TIME_ON'] = e2['ts']
                    if not cand['FREQ']:
                        cand['FREQ'] = e2['freq']
                    if e2.get('mode'):
                        cand['MODE'] = e2['mode']
                    msgs_so_far = [(e2.get('type', ''), e2.get('msg', ''))]
                elif e2['type'] == 'decode':
                    msgs_so_far = [(e2.get('type', ''), e2.get('msg', ''))]
                else:
                    msgs_so_far = []
                for _, msg in msgs_so_far:
                    if not msg:
                        continue
                    toks, calls_pos, grids_pos = classify_tokens(msg)
                    call_toks = [t for _, t in calls_pos]
                    if len(call_toks) >= 2 and call_toks[1].upper() == call.upper():
                        mapping = associate_grid_to_call(toks, calls_pos, grids_pos)
                        call_u = (call or '').upper()
                        if call_u in mapping and not cand['GRIDSQUARE']:
                            cand['GRIDSQUARE'] = mapping[call_u]
                        elif grids_pos and not cand['GRIDSQUARE']:
                            cand['GRIDSQUARE'] = grids_pos[0][1]
                    rst_s, rst_r = assign_reports_from_msg(msg, station_call, call, cand['RST_SENT'] or None, cand['RST_RCVD'] or None)
                    cand['RST_SENT'] = rst_s or cand['RST_SENT']
                    cand['RST_RCVD'] = rst_r or cand['RST_RCVD']
            except Exception:
                continue
        if not cand['TIME_ON']:
            cand['TIME_ON'] = cand['TIME_OFF']
        freq = cand.get('FREQ') or ''
        band = ''
        if freq:
            try:
                band = freq_to_band(float(freq))
            except Exception:
                pass
        rec = {
            'CALL': cand['CALL'],
            **dict(zip(('QSO_DATE','TIME_ON','QSO_DATE_OFF','TIME_OFF'),
                       normalize_on_off(cand['TIME_ON'], cand['TIME_OFF']))),
            'MODE': cand.get('MODE') or 'FT8',
            'BAND': band,
            'FREQ': freq,
            'RST_SENT': cand.get('RST_SENT', '') or '',
            'RST_RCVD': cand.get('RST_RCVD', '') or '',
            'STATION_CALLSIGN': station_call or '',
            'GRIDSQUARE': cand.get('GRIDSQUARE', ''),
            'APP_ALLTXT2ADIF_SOURCE': 'qso_logged'  # important tag for compute_confidence
        }
        if re_report_token.match(rec['CALL']):
            continue
        if rec['GRIDSQUARE'] and not re_grid_strict.match(rec['GRIDSQUARE']):
            rec['GRIDSQUARE'] = ''
        records.append(rec)

    merged = merge_records(records, merge_window_sec=90)
    meta = {'format': 'JTDX', 'count': len(merged)}
    return merged, meta

# ---------- WSJT-X processor ----------
def process_wsjtx(lines: List[str], station_call: Optional[str], window_sec: int, mode_setting: str, *, sanitize_auto: bool = False) -> Tuple[List[Dict], Dict]:
    parsed = []
    warned_sanitize = False
    for L in lines:
        s_raw = L.rstrip('\n')
        s, changed = sanitize_msg(s_raw, auto=sanitize_auto)
        if changed and (not sanitize_auto) and (not warned_sanitize):
            print("Warning: control characters detected in input; use --sanitize-auto to auto-remove them.", flush=True)
            warned_sanitize = True
        s = s.strip()
        if not s:
            continue
        m = re_wsjtx.match(s)
        if m:
            ts = parse_ts_generic(m.group('ts'))
            raw_dir = m.group('dir')
            msg = m.group('msg')
            msg_toks = msg.strip().split()

            effective_dir = raw_dir
            if station_call:
                sc = station_call.upper()
                callee, caller = extract_callee_caller(msg)
                if caller and caller.upper() == sc:
                    effective_dir = 'Tx_station'
                elif callee and callee.upper() == sc:
                    effective_dir = 'Rx_station'
                else:
                    if sc in [t.upper() for t in msg_toks]:
                        effective_dir = 'Rx_station_other'
                    else:
                        effective_dir = 'Rx_other'
            if ts is None:
                continue
            parsed.append({
                'ts': ts,
                'freq': m.group('freq'),
                'dir': effective_dir,
                'raw_dir': raw_dir,
                'mode': m.group('mode'),
                'msg': msg,
                'raw': s
            })
    records: List[Dict] = []
    n = len(parsed)
    i = 0
    while i < n:
        ln = parsed[i]
        # Process lines where station_call is the sender (actual station transmissions)
        if ln['dir'] == 'Tx_station' and ln.get('raw_dir') == 'Tx':
            toks = tokenize_msg(ln['msg'])
            if station_call and station_call.upper() in toks:
                tx_ts = ln['ts']
                tx_freq = ln['freq']
                tx_mode = ln['mode']
                is_final_tx = bool(re.search(r'\bRR73\b|\b73\b|\bRRR\b', ln['msg'] or '', flags=re.I))
                if is_final_tx and re_report_in_text.search(ln['msg'] or ''):
                    toks_all, calls_pos, grids_pos = classify_tokens(ln['msg'])
                    partners = [tok for idx, tok in calls_pos if tok.upper() != station_call.upper()]
                    if partners:
                        partner = partners[0]
                        # Look back to find TIME_ON: earliest Tx/Rx involving this partner
                        time_on = tx_ts
                        for k in range(i - 1, max(-1, i - 20), -1):
                            ek = parsed[k]
                            if ek['ts'] is None:
                                continue
                            if (tx_ts - ek['ts']).total_seconds() > window_sec:
                                break
                            ktoks = tokenize_msg(ek.get('msg', ''))
                            if (partner.upper() in ktoks) and (station_call.upper() in ktoks):
                                time_on = ek['ts']
                                break
                        time_off = tx_ts
                        rst_sent = None
                        rst_rcvd = None
                        window_range = range(max(0, i - 10), min(n, i + 2))
                        window_msgs_with_dir = [(parsed[k]['dir'], parsed[k]['msg']) for k in window_range]
                        for _, msgk in window_msgs_with_dir:
                            rst_sent, rst_rcvd = assign_reports_from_msg(msgk, station_call, partner, rst_sent, rst_rcvd)
                        gridsquare = extract_partner_grid(window_msgs_with_dir, station_call, partner)
                        try:
                            band = freq_to_band(float(tx_freq))
                        except Exception:
                            band = ''
                        rec = {
                            'CALL': partner,
                            **dict(zip(('QSO_DATE','TIME_ON','QSO_DATE_OFF','TIME_OFF'),
                                       normalize_on_off(time_on, time_off))),
                            'MODE': tx_mode,
                            'BAND': band,
                            'FREQ': tx_freq,
                            'RST_SENT': rst_sent or '',
                            'RST_RCVD': rst_rcvd or '',
                            'STATION_CALLSIGN': station_call or '',
                            'GRIDSQUARE': gridsquare
                        }
                        if not re_report_token.match(rec['CALL']):
                            records.append(rec)
                    i += 1
                    continue
                # For non-final Tx: forward scan for completion
                j = i + 1
                window_end_time = tx_ts + timedelta(seconds=window_sec)
                partner = None
                partner_first_ts = None
                partner_last_ts = None
                completion_ts = None
                _toks_tx, _calls_tx, _ = classify_tokens(ln['msg'])
                _partners_tx = [t for _, t in _calls_tx if t.upper() != station_call.upper()]
                if _partners_tx:
                    rst_sent, rst_rcvd = assign_reports_from_msg(ln['msg'], station_call, _partners_tx[0], None, None)
                else:
                    rst_sent = None
                    rst_rcvd = None
                while j < n and parsed[j]['ts'] is not None and parsed[j]['ts'] <= window_end_time:
                    w = parsed[j]
                    wtoks, wcalls_pos, wgrids_pos = classify_tokens(w['msg'])
                    msg_has_station = station_call.upper() in wtoks

                    # Identify partner from any message that contains station_call
                    if msg_has_station:
                        calls_in_msg = [tok for idx, tok in wcalls_pos if tok.upper() != station_call.upper()]
                        if calls_in_msg:
                            if partner is None:
                                partner = calls_in_msg[0]
                            if partner_first_ts is None:
                                partner_first_ts = w['ts']
                            partner_last_ts = w['ts']
                            rst_sent, rst_rcvd = assign_reports_from_msg(w['msg'], station_call, partner, rst_sent, rst_rcvd)

                            # Rule A: partner sends RR73/73 to station_call (partner is sender/caller).
                            if w['dir'] == 'Rx_station' and re.search(r'\bRR73\b|\bRRR\b|\b73\b', w['msg'], flags=re.I):
                                callee, caller = extract_callee_caller(w['msg'])
                                if callee and caller and callee.upper() == station_call.upper() and caller.upper() == partner.upper():
                                    completion_ts = w['ts']
                                    j += 1
                                    break

                            # Rule B: station_call sends RR73/73 to partner (station is sender/caller).
                            if w['dir'] == 'Tx_station' and re.search(r'\bRR73\b|\bRRR\b|\b73\b', w['msg'], flags=re.I):
                                callee, caller = extract_callee_caller(w['msg'])
                                if callee and caller and caller.upper() == station_call.upper() and callee.upper() == partner.upper():
                                    completion_ts = w['ts']
                                    j += 1
                                    break
                    j += 1

                if partner:
                    completed = completion_ts is not None
                    partner_replied = bool(rst_rcvd)
                    if mode_setting == 'strict' and not completed:
                        pass
                    elif not completed and not partner_replied:
                        pass
                    else:
                        time_on = tx_ts
                        time_off = completion_ts or partner_last_ts or partner_first_ts or tx_ts
                        try:
                            band = freq_to_band(float(tx_freq))
                        except Exception:
                            band = ''
                        window_msgs_with_dir = [(parsed[k]['dir'], parsed[k]['msg']) for k in range(i, min(n, j + 1))]
                        gridsquare = extract_partner_grid(window_msgs_with_dir, station_call, partner)
                        rec = {
                            'CALL': partner,
                            **dict(zip(('QSO_DATE','TIME_ON','QSO_DATE_OFF','TIME_OFF'),
                                       normalize_on_off(time_on, time_off))),
                            'MODE': tx_mode,
                            'BAND': band,
                            'FREQ': tx_freq,
                            'RST_SENT': rst_sent or '',
                            'RST_RCVD': rst_rcvd or '',
                            'STATION_CALLSIGN': station_call or '',
                            'GRIDSQUARE': gridsquare
                        }
                        if not re_report_token.match(rec['CALL']):
                            records.append(rec)
                i += 1
                continue
        i += 1
    merged = merge_records(records, merge_window_sec=90)
    meta = {'format': 'WSJT-X', 'count': len(merged)}
    return merged, meta

# ---------- Time normalization ----------
def normalize_on_off(time_on: datetime, time_off: datetime) -> Tuple[str, str, str, str]:
    """
    Ensure time_off >= time_on (guards against rare cross-midnight edge case).
    If time_off < time_on, add one day to time_off.
    Returns (qso_date_on, time_on_str, qso_date_off, time_off_str).
    """
    if time_off < time_on:
        time_off = time_off + timedelta(days=1)
    return (time_on.strftime('%Y%m%d'), time_on.strftime('%H%M%S'),
            time_off.strftime('%Y%m%d'), time_off.strftime('%H%M%S'))

# ---------- Confidence & review helpers ----------
def _extract_msg_from_raw_line(line: str) -> Optional[str]:
    """Extract the message field from a raw ALL.TXT line."""
    s = line.strip()
    if not s:
        return None
    m = re_wsjtx.match(s)
    if m:
        return m.group('msg')
    m = re_jtdx_decode.match(s)
    if m:
        return m.group('msg')
    m = re_jtdx_trans.match(s)
    if m:
        return m.group('msg')
    return None

def _semantic_sender_recipients(msg: str) -> Tuple[Optional[str], List[str], List[str]]:
    """
    Infer (sender, recipients, content_tokens) using FT8 CALLEE CALLER INFO semantics.
    Returns (sender_upper or None, recipients_upper_list, content_tokens_list).
    NOTE: semantic parsing must preserve noise tokens like 'CQ', so use keep_noise=True and preserve case.
    """
    toks = tokenize_msg(msg, keep_noise=True, upper=False)
    if not toks:
        return None, [], []
    up0 = toks[0].upper()
    if up0 == 'CQ':
        caller_idx = 1
        if len(toks) >= 3 and len(toks[1]) <= 3:  # e.g. CQ DX, CQ JA
            caller_idx = 2
        if len(toks) > caller_idx:
            return toks[caller_idx].upper(), ['CQ'], toks[caller_idx + 1:]
        return None, ['CQ'], toks[1:]
    # Non-CQ: find first report/grid token; sender is immediately before it
    first_info_idx = None
    for idx, t in enumerate(toks):
        if re_report_token.match(t) or re_grid_strict.match(t):
            first_info_idx = idx
            break
    if first_info_idx is None:
        if len(toks) >= 2:
            return toks[1].upper(), [toks[0].upper()], toks[2:]
        return None, [], toks[1:]
    sender_idx = first_info_idx - 1
    if sender_idx < 0:
        return None, [], toks[first_info_idx:]
    return toks[sender_idx].upper(), [x.upper() for x in toks[:sender_idx]], toks[sender_idx + 1:]

def _build_time_index(lines: List[str]) -> Tuple[List[datetime], List[int]]:
    """Build sorted (times, line_indices) for fast bisect range lookup."""
    times: List[datetime] = []
    idxs: List[int] = []
    for i, L in enumerate(lines):
        parts = L.strip().split()
        if not parts:
            continue
        ts = parse_ts_generic(parts[0])
        if ts is None:
            continue
        times.append(ts)
        idxs.append(i)
    return times, idxs

def default_window_for_mode(mode: str) -> int:
    """Mode-aware default time window (seconds) for matching messages."""
    m = (mode or '').upper()
    if m.startswith('FT4'):
        return 60
    if m.startswith('Q65'):
        return 180
    # FT8 / FT2 / others
    return 120

_CONTEST_FREQS = {21.090, 21.091, 14.090, 14.091}

def _is_contest_freq(f: Optional[float], tol: float = 0.0005) -> bool:
    """Return True if f is within tol MHz of any contest center freq."""
    if f is None:
        return False
    for cf in _CONTEST_FREQS:
        try:
            if abs(f - cf) <= tol:
                return True
        except Exception:
            continue
    return False

_CONTROL_CHARS_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')

def has_control_chars(msg: str) -> bool:
    """Return True if msg contains ASCII control characters that should be sanitized."""
    if not msg:
        return False
    return bool(_CONTROL_CHARS_RE.search(msg))

def sanitize_msg(msg: str, *, auto: bool) -> Tuple[str, bool]:
    """Detect/remove ASCII control chars in message text. Returns (msg, changed)."""
    if not msg:
        return msg, False
    if not _CONTROL_CHARS_RE.search(msg):
        return msg, False
    if auto:
        return _CONTROL_CHARS_RE.sub('', msg), True
    # detected but not removed => changed=True to trigger warning
    return msg, True

def compute_confidence(records: List[Dict], lines: List[str], station_call: str,
                       *, window_sec: Optional[int], mode_setting: str = 'strict', semantic_line_window: int = 3) -> None:
    """Annotate records in-place with APP_ALLTXT2ADIF_* fields.

    Evidence layers (strong -> weak):
      - qso_logged (JTDX only; authoritative)
      - RR73 / RRR (completion)
      - both_rst (exchange)
      - we_sent_rr73 (semantic required; +extra evidence => high else medium)
      - 73-only (semantic => medium, ambiguous => low)

    Always writes:
      APP_ALLTXT2ADIF_CONFIDENCE, APP_ALLTXT2ADIF_CONF_REASON, APP_ALLTXT2ADIF_SRC_LINE
      Optionally writes APP_ALLTXT2ADIF_COMPLETION = 'confirmed'|'provisional'
    """
    sc = (station_call or '').strip().upper()

    # Pre-parse timestamps for time-window scanning
    line_times: List[Optional[datetime]] = []
    for L in lines:
        parts = L.strip().split()
        if not parts:
            line_times.append(None)
            continue
        line_times.append(parse_ts_generic(parts[0]))

    def iter_context_indices(ton: datetime, toff: datetime, mode: str) -> List[int]:
        w = window_sec if window_sec is not None else default_window_for_mode(mode)
        ws = ton - timedelta(seconds=w)
        we = toff + timedelta(seconds=w)
        idxs = []
        for i, lt in enumerate(line_times):
            if lt is None:
                continue
            if ws <= lt <= we:
                idxs.append(i)
        return idxs

    def iter_line_window(center: int) -> List[int]:
        if center < 0:
            return []
        a = max(0, center - semantic_line_window)
        b = min(len(lines), center + semantic_line_window + 1)
        return list(range(a, b))

    def scan_evidence(partner: str, ctx_idxs: List[int]) -> Dict[str, Any]:
        pu = (partner or '').upper()
        flags = {
            'both_calls': False,
            'rr73': False,
            'rrr': False,
            'tok_73': False,
            'partner_sent_completion': False,
            'we_sent_completion': False,
            'semantic_ok': False,
            'first_line': -1,
            'grid': False,
            'grid_token': None,
        }
        for i in ctx_idxs:
            raw_line = lines[i]
            up = raw_line.upper()
            if sc in up and pu in up:
                if flags['first_line'] < 0:
                    flags['first_line'] = i
                flags['both_calls'] = True

                has_rr73 = bool(re.search(r'\bRR73\b', up))
                has_rrr  = bool(re.search(r'\bRRR\b', up))
                has_73   = bool(re.search(r'\b73\b', up)) and not has_rr73

                if has_rr73:
                    flags['rr73'] = True
                if has_rrr:
                    flags['rrr'] = True
                if has_73:
                    flags['tok_73'] = True

                if has_rr73 or has_rrr or has_73:
                    flags['semantic_ok'] = True

                # detect whether this line is a transmit or decode line using patterns
                if ' TRANSMITTING ' in up or re.search(r'\sTX\s', up):
                    if has_rr73 or has_rrr or has_73:
                        flags['we_sent_completion'] = True
                if re.search(r'\sRX\s', up) or re.search(r'\s~\s', up):
                    if has_rr73 or has_rrr or has_73:
                        flags['partner_sent_completion'] = True

            # grid detection uses tokenization that preserves noise/grid tokens
            raw_tokens = tokenize_msg(raw_line, keep_noise=True, upper=False)
            for tok in raw_tokens:
                if re_grid_strict.match(tok):
                    flags['grid'] = True
                    if flags['grid_token'] is None:
                        flags['grid_token'] = tok.upper()
                    break
        return flags

    for rec in records:
        # defaults
        rec['APP_ALLTXT2ADIF_CONFIDENCE'] = 'low'
        rec['APP_ALLTXT2ADIF_CONF_REASON'] = 'no_evidence'
        rec['APP_ALLTXT2ADIF_SRC_LINE'] = '-1'
        rec.pop('APP_ALLTXT2ADIF_COMPLETION', None)

        partner = (rec.get('CALL') or '').strip().upper()
        if not partner or partner == sc:
            continue

        # JTDX-only: authoritative line created from qso_logged
        if str(rec.get('APP_ALLTXT2ADIF_SOURCE', '')).lower() == 'qso_logged':
            rec['APP_ALLTXT2ADIF_CONFIDENCE'] = 'high'
            rec['APP_ALLTXT2ADIF_CONF_REASON'] = 'qso_logged'
            rec['APP_ALLTXT2ADIF_COMPLETION'] = 'confirmed'
            if rec.get('APP_ALLTXT2ADIF_SRC_LINE'):
                rec['APP_ALLTXT2ADIF_SRC_LINE'] = str(rec['APP_ALLTXT2ADIF_SRC_LINE'])
            continue

        try:
            ton = datetime.strptime(rec['QSO_DATE'] + rec['TIME_ON'], '%Y%m%d%H%M%S')
            toff = datetime.strptime(rec['QSO_DATE_OFF'] + rec['TIME_OFF'], '%Y%m%d%H%M%S')
        except Exception:
            continue

        # Build context indices: time-window around the QSO
        ctx = iter_context_indices(ton, toff, rec.get('MODE', ''))
        try:
            src_line = int(rec.get('APP_ALLTXT2ADIF_SRC_LINE', -1))
        except Exception:
            src_line = -1
        ctx2 = set(ctx)
        for i in iter_line_window(src_line):
            ctx2.add(i)
        ctx_idxs = sorted(ctx2)

        flags = scan_evidence(partner, ctx_idxs)
        if flags['first_line'] >= 0:
            rec['APP_ALLTXT2ADIF_SRC_LINE'] = str(flags['first_line'])

        has_sent = bool(rec.get('RST_SENT'))
        has_rcvd = bool(rec.get('RST_RCVD'))
        both_rst = has_sent and has_rcvd

        # ---- Decision (strong -> weak) ----
        # grid+73 special case for contest-like exchanges
        # grid+73 special case for contest-like exchanges (frequency-limited):
        try:
            freq_val = safe_float(str(rec.get('FREQ') or ''))
        except Exception:
            freq_val = None
        if flags.get('grid') and flags.get('tok_73') and flags.get('both_calls') and _is_contest_freq(freq_val):
            rec['APP_ALLTXT2ADIF_CONFIDENCE'] = 'high'
            rec['APP_ALLTXT2ADIF_CONF_REASON'] = 'grid_73'
            rec['APP_ALLTXT2ADIF_COMPLETION'] = 'confirmed'
            continue

        if flags['rr73'] and flags['semantic_ok'] and flags['partner_sent_completion']:
            rec['APP_ALLTXT2ADIF_CONFIDENCE'] = 'high'
            rec['APP_ALLTXT2ADIF_CONF_REASON'] = 'rr73'
            rec['APP_ALLTXT2ADIF_COMPLETION'] = 'confirmed'
        elif flags['rrr'] and flags['semantic_ok'] and flags['partner_sent_completion']:
            rec['APP_ALLTXT2ADIF_CONFIDENCE'] = 'high'
            rec['APP_ALLTXT2ADIF_CONF_REASON'] = 'rrr'
            rec['APP_ALLTXT2ADIF_COMPLETION'] = 'confirmed'
        elif flags['rr73'] and flags['semantic_ok'] and flags['we_sent_completion'] and _is_contest_freq(freq_val):
            rec['APP_ALLTXT2ADIF_CONFIDENCE'] = 'high'
            rec['APP_ALLTXT2ADIF_CONF_REASON'] = 'rr73_contest'
            rec['APP_ALLTXT2ADIF_COMPLETION'] = 'confirmed'
        elif flags['rr73'] and flags['semantic_ok']:
            rec['APP_ALLTXT2ADIF_CONFIDENCE'] = 'medium'
            rec['APP_ALLTXT2ADIF_CONF_REASON'] = 'rr73_no_semantic_dir'
            # mark provisional completion if token exists
            rec['APP_ALLTXT2ADIF_COMPLETION'] = 'provisional'
        elif flags['rrr'] and flags['semantic_ok']:
            rec['APP_ALLTXT2ADIF_CONFIDENCE'] = 'medium'
            rec['APP_ALLTXT2ADIF_CONF_REASON'] = 'rrr_no_semantic_dir'
            rec['APP_ALLTXT2ADIF_COMPLETION'] = 'provisional'
        elif both_rst:
            if flags['semantic_ok'] or flags['both_calls']:
                rec['APP_ALLTXT2ADIF_CONFIDENCE'] = 'high'
                rec['APP_ALLTXT2ADIF_CONF_REASON'] = 'both_rst'
                # both_rst is exchange evidence; completion may still be provisional if no completion token
                if flags['partner_sent_completion'] or flags['we_sent_completion'] or flags['rr73'] or flags['rrr'] or flags['tok_73']:
                    rec['APP_ALLTXT2ADIF_COMPLETION'] = 'confirmed'
            else:
                rec['APP_ALLTXT2ADIF_CONFIDENCE'] = 'medium'
                rec['APP_ALLTXT2ADIF_CONF_REASON'] = 'both_rst_no_semantic'
        elif (flags['we_sent_completion'] and (flags['rr73'] or flags['rrr']) and flags['semantic_ok']):
            if flags['partner_sent_completion'] or both_rst or (flags['we_sent_completion'] and _is_contest_freq(freq_val)):
                rec['APP_ALLTXT2ADIF_CONFIDENCE'] = 'high'
                rec['APP_ALLTXT2ADIF_CONF_REASON'] = 'we_sent_rr73'
                rec['APP_ALLTXT2ADIF_COMPLETION'] = 'confirmed'
            else:
                rec['APP_ALLTXT2ADIF_CONFIDENCE'] = 'medium'
                rec['APP_ALLTXT2ADIF_CONF_REASON'] = 'we_sent_rr73_no_reply'
                rec['APP_ALLTXT2ADIF_COMPLETION'] = 'provisional'
        elif flags['tok_73']:
            if flags['semantic_ok']:
                rec['APP_ALLTXT2ADIF_CONFIDENCE'] = 'medium'
                rec['APP_ALLTXT2ADIF_CONF_REASON'] = '73_semantic'
                rec['APP_ALLTXT2ADIF_COMPLETION'] = 'provisional'
            else:
                rec['APP_ALLTXT2ADIF_CONFIDENCE'] = 'low'
                rec['APP_ALLTXT2ADIF_CONF_REASON'] = '73_only'
                rec['APP_ALLTXT2ADIF_COMPLETION'] = 'provisional'
        elif mode_setting == 'lenient' and flags.get('partner_sent_completion') and flags.get('semantic_ok'):
            # Lenient mode: partner sent completion addressed to station; no station Tx found.
            # Accept as provisional (medium) — opt-in only, not default strict behavior.
            rec['APP_ALLTXT2ADIF_CONFIDENCE'] = 'medium'
            rec['APP_ALLTXT2ADIF_CONF_REASON'] = 'partner_completion_lenient'
            rec['APP_ALLTXT2ADIF_COMPLETION'] = 'provisional'
        elif has_sent or has_rcvd:
            rec['APP_ALLTXT2ADIF_CONFIDENCE'] = 'medium'
            rec['APP_ALLTXT2ADIF_CONF_REASON'] = 'one_rst'
        elif flags['both_calls']:
            rec['APP_ALLTXT2ADIF_CONFIDENCE'] = 'low'
            rec['APP_ALLTXT2ADIF_CONF_REASON'] = 'both_calls'
        else:
            rec['APP_ALLTXT2ADIF_CONFIDENCE'] = 'low'
            rec['APP_ALLTXT2ADIF_CONF_REASON'] = 'no_evidence'


def write_review_csv(records: List[Dict], lines: List[str], outpath: str,
                     min_confidence: str = 'low', context_lines: int = 5, snippet_chars: int = 1200) -> int:
    include = {'low'}
    if min_confidence == 'medium':
        include.add('medium')
    if min_confidence == 'all':
        include.add('medium'); include.add('high')
    count = 0
    with open(outpath, 'w', newline='', encoding='utf-8') as cf:
        w = csv.writer(cf)
        w.writerow(['CALL', 'QSO_DATE', 'TIME_ON', 'TIME_OFF', 'BAND', 'FREQ',
                    'RST_SENT', 'RST_RCVD', 'GRIDSQUARE', 'CONFIDENCE', 'REASON', 'SRC_LINE', 'CONTEXT'])
        for r in records:
            if r.get('APP_ALLTXT2ADIF_CONFIDENCE', 'low') not in include:
                continue
            sl = r.get('APP_ALLTXT2ADIF_SRC_LINE') or ''
            snippet = ''
            if sl.isdigit():
                i = int(sl)
                start = max(0, i - context_lines)
                end   = min(len(lines), i + context_lines + 1)
                snippet = "\n".join(lines[start:end])
                if len(snippet) > snippet_chars:
                    snippet = snippet[:snippet_chars] + "\n...[truncated]..."
            w.writerow([
                r.get('CALL',''), r.get('QSO_DATE',''), r.get('TIME_ON',''), r.get('TIME_OFF',''),
                r.get('BAND',''), r.get('FREQ',''), r.get('RST_SENT',''), r.get('RST_RCVD',''),
                r.get('GRIDSQUARE',''), r.get('APP_ALLTXT2ADIF_CONFIDENCE',''),
                r.get('APP_ALLTXT2ADIF_CONF_REASON',''), sl, snippet
            ])
            count += 1
    return count

# ---------- IO ----------
_ADIF_FIELDS = ('CALL', 'QSO_DATE', 'TIME_ON', 'QSO_DATE_OFF', 'TIME_OFF',
                'MODE', 'BAND', 'FREQ', 'RST_SENT', 'RST_RCVD',
                'STATION_CALLSIGN', 'GRIDSQUARE', 'COMMENT')
_APP_FIELDS  = ('APP_ALLTXT2ADIF_ORIG_MODE', 'APP_ALLTXT2ADIF_CONFIDENCE', 'APP_ALLTXT2ADIF_CONF_REASON',
                'APP_ALLTXT2ADIF_SRC_LINE', 'APP_ALLTXT2ADIF_COMPLETION', 'APP_ALLTXT2ADIF_SOURCE')

def write_adif(records: List[Dict], out_path: str, *, adif_ver: str = '3.1.6', program: str = 'ALL.TXT2ADIF') -> None:
    """Write ADIF file."""
    def _fmt_field(name: str, value: str) -> str:
        b = value.encode('utf-8', errors='replace')
        return f"<{name}:{len(b)}>{value}"

    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        f.write(f"Generated by {program}\n")
        f.write(_fmt_field('ADIF_VER', adif_ver) + "\n")
        f.write(_fmt_field('PROGRAMID', program) + "\n")
        f.write(_fmt_field('PROGRAMVERSION', VERSION) + "\n")
        f.write("<EOH>\n")
        for r in records:
            parts = []
            # Preferred ADIF fields (some may be absent)
            for k in (_ADIF_FIELDS + _APP_FIELDS):
                v = r.get(k)
                if v is None:
                    continue
                vs = str(v).strip()
                if not vs:
                    continue
                parts.append(_fmt_field(k, vs))
            f.write(" ".join(parts) + " <EOR>\n")

def detect_format(lines: List[str]) -> str:
    jtdx_score = 0
    wsjtx_score = 0
    for L in lines[:200]:
        s = L.strip()
        if not s:
            continue
        if re_jtdx_trans.match(s) or re_jtdx_qso_logged.match(s):
            jtdx_score += 2
        elif re_jtdx_decode.match(s):
            jtdx_score += 1
        elif re_wsjtx.match(s):
            wsjtx_score += 1
    if jtdx_score == 0 and wsjtx_score == 0:
        return 'UNKNOWN'
    return 'JTDX' if jtdx_score > wsjtx_score else 'WSJT-X'


def warn_if_station_not_seen(lines: List[str], station_call: str):
    seen = False
    for L in lines:
        if station_call in L:
            seen = True
            break
    if not seen:
        print(f"Warning: station call '{station_call}' not found in input file. Are you processing another station's ALL.TXT?")

# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser(description='Convert WSJT-X / JTDX ALL.TXT into ADIF (updated)')
    ap.add_argument('input', help='ALL.TXT input file')
    ap.add_argument('-o', '--output', default='out.adi', help='output ADIF file')
    ap.add_argument('--station-call', default='JP1LRT', help='your station callsign')
    ap.add_argument('--window-sec', type=int, default=None,
                    help='override evidence window seconds (default: mode-aware: FT8/FT2=120, FT4=60, Q65=180)')
    ap.add_argument('--semantic-line-window', type=int, default=3,
                    help='line-window fallback (+/-N lines) for semantic/evidence scan (default: 3)')
    ap.add_argument('--sanitize-auto', action='store_true',
                    help='auto-remove ASCII control chars in message text (default: detect+warn only)')
    ap.add_argument('--adif-mode', choices=['compat','strict'], default='compat',
                    help='ADIF mode mapping: compat (default) or strict (MODE=MFSK + SUBMODE for FT4/Q65/FT2)')
    ap.add_argument('--mode', choices=['strict', 'lenient'], default='strict', help='mode: strict or lenient')
    ap.add_argument('--merge-window', type=int, default=60, help='merge window seconds for dedupe')
    ap.add_argument('--review-csv', default='', help='write low/medium-confidence QSOs to this CSV (optional)')
    ap.add_argument('--review-level', choices=['low', 'medium', 'all'], default='low',
                    help='minimum confidence level for review CSV (default: low only)')
    ap.add_argument('--no-confidence', action='store_true', help='suppress APP_ALLTXT2ADIF_* fields in output')
    args = ap.parse_args()

    try:
        with open(args.input, 'r', encoding='utf-8', errors='replace') as f:
            lines = [l.rstrip('\n') for l in f]
    except Exception as e:
        print(f"Error: cannot read input file: {e}")
        return

    # Normalize station callsign to uppercase for consistent comparison
    args.station_call = args.station_call.strip().upper()
    warn_if_station_not_seen(lines, args.station_call)

    # If user didn't set window-sec, provide a safe baseline to avoid None arithmetic errors.
    if args.window_sec is None:
        args.window_sec = 120  # baseline; processors will use mode-aware defaults where applicable

    fmt = detect_format(lines)
    if fmt == 'JTDX':
        records, meta = process_jtdx(lines, args.station_call, args.window_sec, args.mode, sanitize_auto=args.sanitize_auto)
    elif fmt == 'WSJT-X':
        records, meta = process_wsjtx(lines, args.station_call, args.window_sec, args.mode, sanitize_auto=args.sanitize_auto)
    else:
        rec_j, _ = process_jtdx(lines, args.station_call, args.window_sec, args.mode, sanitize_auto=args.sanitize_auto)
        rec_w, _ = process_wsjtx(lines, args.station_call, args.window_sec, args.mode, sanitize_auto=args.sanitize_auto)
        combined = rec_j + rec_w
        records = merge_records(combined, merge_window_sec=args.merge_window)
        # post-merge dedupe to absorb small lookback differences
        records = dedupe_by_time_and_freq(records, merge_window_sec=args.merge_window)
        meta = {'format': 'AUTO', 'count': len(records)}

    # If single-format branch, also run post-merge dedupe to catch lookback-induced dups
    if fmt in ('JTDX','WSJT-X'):
        records = dedupe_by_time_and_freq(records, merge_window_sec=args.merge_window)

    # remove self-QSO
    records = [r for r in records if r['CALL'].upper() != args.station_call.upper()]

    # Confidence tagging (APP_ALLTXT2ADIF_* fields)
    if not args.no_confidence:
        compute_confidence(records, lines, args.station_call, window_sec=args.window_sec, mode_setting=args.mode, semantic_line_window=args.semantic_line_window)

    # ADIF mode mapping (keep original token in APP field)
    for r in records:
        orig_mode = (r.get('MODE') or '').strip()
        if orig_mode:
            r['APP_ALLTXT2ADIF_ORIG_MODE'] = orig_mode
        if args.adif_mode == 'strict':
            m = orig_mode.upper()
            if m in ('FT4', 'Q65', 'FT2'):
                r['MODE'] = 'MFSK'
                r['SUBMODE'] = m

    # Optional review CSV
    if args.review_csv:
        n_review = write_review_csv(records, lines, args.review_csv,
                                    min_confidence=args.review_level)
        print(f"Review CSV: {n_review} records -> {args.review_csv}")

    try:
        # Sort by QSO date/time before writing (chronological order, oldest first)
        records.sort(key=lambda r: (
            r.get('QSO_DATE', ''),
            (r.get('TIME_ON', '') or '').zfill(6),
            r.get('CALL', ''),
            r.get('BAND', ''),
            r.get('MODE', ''),
        ))
        write_adif(records, args.output)
    except Exception as e:
        print(f"Error writing ADIF: {e}")
        return

    print(f"Detected format: {fmt}")
    print(f"Extracted {len(records)} records -> {args.output}")
    bands = {}
    for r in records:
        bands[r.get('BAND', '')] = bands.get(r.get('BAND', ''), 0) + 1
    if bands:
        print("By band:")
        for b, c in bands.items():
            print(f"  {b}: {c}")
    if records:
        print("Sample records:")
        for r in records[:20]:
            print(f"  {r['CALL']} {r['QSO_DATE']} {r['TIME_ON']} - {r['TIME_OFF']} {r['BAND']} {r['FREQ']} gs={r.get('GRIDSQUARE','')} rst={r.get('RST_SENT','')}/{r.get('RST_RCVD','')} compl={r.get('APP_ALLTXT2ADIF_COMPLETION','')}")
if __name__ == '__main__':
    main()