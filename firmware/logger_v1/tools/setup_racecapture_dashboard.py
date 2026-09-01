"""Add a logger dashboard, retaining existing dashboards and backing up preferences.

Close RaceCapture normally first; otherwise it will overwrite the changes on exit.
"""
import argparse
import copy
import datetime
import json
from pathlib import Path


def configure(prefs):
    candidates = [g for d in prefs['dashboard'].values() for g in d.get('gauges', [])
                  if g.get('config', {}).get('Gauge Type', {}).get('gauge') == 'Digital']
    if not candidates:
        raise ValueError('No existing Digital gauge template; preferences were not changed')
    gauges = []
    names = ['Lat', 'Lon', 'GPSSpeed', 'GPSSats', 'GPSFix', 'GPSHAcc',
             'GNSSHz', 'UTCValid', 'LogDrops', 'GForceX', 'GForceY', 'IMUHz']
    for i, name in enumerate(names):
        g = copy.deepcopy(candidates[0])
        g.update(center_x=(i % 3 + .5) / 3, center_y=1-(i // 3 + .5) / 4,
                 size_hint_x=.31, size_hint_y=.22)
        g['config']['Channel'] = {'channel': name}
        g['config']['Text Values'] = {}
        visual = g['config'].setdefault('Settings', {}).setdefault('visual_settings', {})
        visual.update(show_channel_name=True, show_channel_unit=True,
                      channel_labels_font_size_pct=[.36, .18, .13],
                      background_color=[.03, .08, .13, 1],
                      outline_color=[.15, .7, .75, 1])
        gauges.append(g)
    key = 'dashboard_logger_v1_gnss_imu'
    prefs['dashboard'][key] = dict(dash_name='Logger GPS / IMU', dash_type='freeform',
                                    gauges=gauges, locked=True)
    prefs['general_prefs']['dashboard_preferences']['last_dash_screen'] = key
    prefs['general_prefs']['dashboard_preferences']['bottom_gauge_bar_enabled'] = '0'
    prefs['general_prefs']['preferences']['startup_screen'] = 'Dashboard'
    return prefs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prefs', type=Path, default=Path.home()/'AppData/Roaming/racecapture/prefs.json')
    p.add_argument('--backup-dir', type=Path, required=True)
    args = p.parse_args()
    original = args.prefs.read_bytes()
    updated = configure(json.loads(original))
    args.backup_dir.mkdir(parents=True, exist_ok=True)
    backup = args.backup_dir / ('prefs_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json')
    with backup.open('xb') as f:
        f.write(original)
    staged = args.prefs.with_suffix('.logger-new.json')
    staged.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding='utf-8')
    staged.replace(args.prefs)
    print('Added Logger GPS / IMU dashboard; backup:', backup)


if __name__ == '__main__':
    main()
