"""Compare closed SD logs from verify_gnss_health --comparison-report.

Read-only input. Uses fresh PVT epochs, never equates 100 Hz CSV rows with GNSS
samples. --stationary scatter is repeatability, NOT absolute position accuracy.
No automatic firmware changes or invented best profile from a single trial.
"""
import argparse
import csv
import json
import math
import statistics
from pathlib import Path


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def percentile(values, fraction):
    if not values:
        return None
    values = sorted(values)
    pos = (len(values)-1)*fraction
    lower = int(pos)
    return values[lower] + (values[min(lower+1,len(values)-1)]-values[lower])*(pos-lower)


def analyze_rows(rows, period_ms, stationary=False):
    if period_ms <= 0 or len(rows) < 2:
        raise ValueError('Need a valid period and at least two SD rows')
    ticks = [int(r['monotonic_us']) for r in rows]
    intervals = [b-a for a,b in zip(ticks,ticks[1:])]
    if min(intervals) <= 0:
        raise ValueError('Logs must be one ordered boot/segment; never join reboots')
    duration = (ticks[-1]-ticks[0])/1e6
    points, previous = [], None
    fresh_count, missing_start, longest = 0, None, 0.0
    for tick, row in zip(ticks,rows):
        tow = number(row.get('GPSTow'))
        lat, lon = number(row.get('Lat')), number(row.get('Lon'))
        valid = number(row.get('GPSFix')) in (3,4) and lat is not None and lon is not None
        age = number(row.get('GNSSAge'))
        fresh = valid and age is not None and age <= 2*period_ms+30
        fresh_count += fresh
        if fresh:
            if missing_start is not None:
                longest = max(longest,(tick-missing_start)/1e6)
                missing_start = None
        elif missing_start is None:
            missing_start = tick
        if tow is not None and tow != previous:
            points.append((tick,tow,row,valid))
            previous = tow
    if missing_start is not None:
        longest = max(longest,(ticks[-1]-missing_start+statistics.median(intervals))/1e6)
    valid_points = [p for p in points if p[3]]
    def values(key):
        return [x for p in valid_points if (x := number(p[2].get(key))) is not None]
    steps = [(b[1]-a[1]) % 604800000 for a,b in zip(points,points[1:])]
    result = {
        'duration_s':duration, 'sd_hz':(len(rows)-1)/duration,
        'max_sd_gap_ms':max(intervals)/1000, 'epochs':len(points),
        'configured_hz':1000/period_ms,
        # Full-window denominator detects a silent tail or head, too.
        'epoch_delivery_pct':min(100,100*len(points)/(duration*1000/period_ms+1)),
        'fresh_fix_pct':100*fresh_count/len(rows),
        'longest_no_fresh_fix_s':longest,
        'valid_fix_hz':len(valid_points)/duration,
        'max_epoch_step_ms':max(steps) if steps else None,
        'satellites_p10':percentile(values('GPSSats'),.1),
        'satellites_median':percentile(values('GPSSats'),.5),
        'hacc_estimate_p95_m':percentile(values('GPSHAcc'),.95),
        'static_scatter_p95_m':None,
    }
    if stationary and valid_points:
        lat0 = statistics.median(values('Lat')); lon0 = statistics.median(values('Lon'))
        distances = [math.hypot((float(p[2]['Lat'])-lat0)*111319.49,
                     (float(p[2]['Lon'])-lon0)*111319.49*math.cos(math.radians(lat0))) for p in valid_points]
        result['static_scatter_p95_m'] = percentile(distances,.95)
    return result


def analyze_report(path, stationary):
    report = json.loads(path.read_text(encoding='utf-8-sig'))
    cfg = report.get('configuration') or {}
    if not cfg.get('verified') or not cfg.get('profileId') or not cfg.get('periodMs'):
        raise ValueError(f'{path}: missing verified profile; use g firmware')
    name = report.get('csv_file')
    if not name or Path(name).name != name:
        raise ValueError(f'{path}: missing or invalid CSV filename')
    with (path.parent/name).open(encoding='utf-8-sig',newline='') as f:
        result = analyze_rows(list(csv.DictReader(f)),cfg['periodMs'],stationary)
    result.update(profile=cfg['profileId'], report=str(path.resolve()),
                  satellite_systems_max_used=report.get('satellite_systems_max_used',{}))
    required = ('sd_100hz','sd_clean_close','metadata_matches_columns','imu_100hz_valid',
                'no_sd_errors_or_drops','no_gnss_retries_or_errors',
                'gnss_configuration_readback_verified','gnss_profile_unchanged','existing_files_preserved')
    result['measurement_valid'] = all(report.get('checks',{}).get(k) is True for k in required)
    # A UTC/schema rotation can truncate the downloaded segment; don't compare
    # a short easy interval against a complete 180-second trial.
    result['measurement_valid'] &= result['duration_s'] >= .9*report.get('requested_seconds',math.inf)
    result['quality_gate'] = (result['measurement_valid'] and result['fresh_fix_pct'] >= 99 and
                              result['epoch_delivery_pct'] >= 98 and result['longest_no_fresh_fix_s'] <= 1)
    return result


def summarize(trials):
    families = {}
    for trial in trials:
        families.setdefault(trial['profile'],[]).append(trial)
    summaries = []
    for name, runs in families.items():
        summaries.append({'profile':name, 'trials':len(runs),
            'repeated_quality_pass':len(runs)>=2 and all(r['quality_gate'] for r in runs),
            'minimum_fresh_fix_pct':min(r['fresh_fix_pct'] for r in runs),
            'minimum_epoch_delivery_pct':min(r['epoch_delivery_pct'] for r in runs),
            'configured_hz':runs[0]['configured_hz']})
    # No scalar score hides outages behind satellite count or sample rate.
    return {'trials':trials,'profiles':summaries,'selected_profile':None,
            'selection_note':'Compare repeated quality passes, then scatter and actual update rate; repeat on the same walking route. No absolute accuracy without a reference.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('reports',type=Path,nargs='+')
    p.add_argument('--stationary',action='store_true')
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    result=summarize([analyze_report(path,args.stationary) for path in args.reports])
    args.output.mkdir(parents=True,exist_ok=True)
    with (args.output/'comparison.json').open('x',encoding='utf-8') as f:
        json.dump(result,f,indent=2,ensure_ascii=False,allow_nan=False)
    fields=['profile','duration_s','configured_hz','epoch_delivery_pct','fresh_fix_pct',
            'longest_no_fresh_fix_s','satellites_median','hacc_estimate_p95_m',
            'static_scatter_p95_m','measurement_valid','quality_gate']
    with (args.output/'comparison.csv').open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
        writer.writeheader(); writer.writerows(result['trials'])
    print(json.dumps(result['profiles'],indent=2))


if __name__=='__main__':
    main()
