"""Convert one physical bus's received SD frames for root can_diff/can_correlate."""
import argparse
import csv
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('input', type=Path)
p.add_argument('output', type=Path)
p.add_argument('--bus', type=int, choices=[1, 2], required=True)
args = p.parse_args()
with args.input.open(newline='', encoding='utf-8') as source, args.output.open('x', newline='', encoding='utf-8') as dest:
    writer = csv.writer(dest)
    writer.writerow(['host_iso', 't_us', 'can_id', 'ext', 'rtr', 'dlc', 'data_hex'])
    for row in csv.DictReader(source):
        if int(row['bus']) == args.bus and row['direction'] == 'RX':
            writer.writerow(['', row['monotonic_us'], '0x' + row['id'], row['extended'], row['rtr'], row['dlc'], row['data']])
