"""Analyze SD originals without modifying them. Run with WSL workpy Python."""
import csv
import base64
import html
import hashlib
import io
import json
import re
import sys
import math
import urllib.request
from concurrent.futures import ThreadPoolExecutor
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from PIL import Image

FONT = '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf'
if Path(FONT).exists():
    font_manager.fontManager.addfont(FONT)
    plt.rcParams['font.family'] = ['DejaVu Sans', font_manager.FontProperties(fname=FONT).get_name()]
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.titleweight': 'bold', 'axes.labelcolor': '#334155',
                     'text.color': '#172b46', 'axes.edgecolor': '#cbd5e1',
                     'grid.color': '#e2e8f0', 'figure.facecolor': '#f8fafc', 'savefig.facecolor': '#f8fafc'})

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'analysis' / 'walk_20260831'
OUT.mkdir(parents=True, exist_ok=True)


def load_logs():
    source = ROOT / 'logs.zip'
    frames, inventory = [], []
    with zipfile.ZipFile(source) as z:
        names = set(z.namelist())
        assert sum(i.file_size for i in z.infolist()) < 500_000_000
        assert z.testzip() is None, 'ZIP CRC failed'
        for name in sorted(names):
            if not name.endswith('.csv') or name.endswith('_can.csv'):
                continue
            raw = z.read(name)
            records = list(csv.reader(io.StringIO(raw.decode('utf-8-sig'))))
            header, data = records[0], records[1:]
            bad = [i + 2 for i, row in enumerate(data) if len(row) != len(header)]
            clean = [row for row in data if len(row) == len(header)]
            df = pd.DataFrame(clean, columns=header).apply(pd.to_numeric, errors='coerce')
            base = name[:-4]
            meta = json.loads(z.read(base + '.meta.json')) if base + '.meta.json' in names else {}
            ending = json.loads(z.read(base + '.end.json')) if base + '.end.json' in names else None
            boot = re.search(r'L[0-9A-F]{8}', name)[0]
            df['boot'] = boot
            df['file'] = Path(name).name
            df['t'] = df.monotonic_us / 1e6
            fix = df.GPSFix.isin([2, 3, 4]) & df.Lat.notna() & df.Lon.notna()
            item = dict(file=Path(name).name, boot=boot, rows=len(df), bad_lines=bad,
                        ends_with_newline=raw.endswith(b'\n'), clean_close=bool(ending and ending.get('clean_close')),
                        end_rows=ending.get('rows') if ending else None, meta=meta,
                        first_t=float(df.t.min()), last_t=float(df.t.max()),
                        valid_fix_rows=int(fix.sum()), utc_rows=int(df.utc_us.notna().sum()),
                        imu_rows=int(df.GForceX.notna().sum()),
                        lat_range=[float(df.loc[fix, 'Lat'].min()), float(df.loc[fix, 'Lat'].max())],
                        lon_range=[float(df.loc[fix, 'Lon'].min()), float(df.loc[fix, 'Lon'].max())],
                        speed_max=float(df.loc[fix, 'GPSSpeed'].max()),
                        hacc_median=float(df.loc[fix, 'GPSHAcc'].median()))
            inventory.append(item)
            frames.append(df)
    all_data = pd.concat(frames, ignore_index=True).sort_values(['boot', 't'])
    assert not all_data.duplicated(['boot', 'monotonic_us']).any(), 'Duplicate sample timestamps'
    manifest = {'source': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'files': inventory}
    (OUT / 'inventory.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=True))
    all_data.to_pickle(OUT / 'samples.pkl')
    return all_data, manifest


def explore():
    d = pd.read_pickle(OUT / 'samples.pkl')
    for boot, b in d.groupby('boot'):
        print('\nBOOT', boot)
        f = b.GPSFix.isin([2,3,4]) & b.Lat.notna() & b.Lon.notna()
        u = b.loc[f & b.GPSTow.notna() & b.GPSTow.ne(b.GPSTow.shift())].copy()
        if len(u):
            dt = u.t.diff()
            step = np.hypot(u.Lat.diff()*111132, u.Lon.diff()*111320*np.cos(np.deg2rad(u.Lat)))
            print('FIXES', len(u), 'hacc', u.GPSHAcc.quantile([0,.5,.9,1]).to_dict(),
                  'speed_kmh', u.GPSSpeed.quantile([0,.5,.9,1]).to_dict(),
                  'coord_speed_mps', (step/dt).quantile([.5,.9,.99,1]).to_dict())
            u['bin'] = (u.t//10).astype(int)
            print(u.groupby('bin').agg(t=('t','min'),n=('t','size'),lat=('Lat','median'),lon=('Lon','median'),v=('GPSSpeed','median'),h=('GPSHAcc','median'),s=('GPSSats','median')).round(5).to_string())
        valid = b.GForceX.notna() & b.GForceY.notna() & b.GForceZ.notna() & b.IMULink.eq(1)
        a = np.sqrt((b.loc[valid,['GForceX','GForceY','GForceZ']]**2).sum(axis=1))
        gy = np.sqrt((b.loc[valid,['GyroX','GyroY','GyroZ']]**2).sum(axis=1))
        print('IMU norms G', a.quantile([.5,.9,.99,1]).to_dict(), 'gyro_dps', gy.quantile([.5,.9,.99,1]).to_dict())
        if 'GNSSCNoMax' in b and b.GNSSCNoMax.notna().any():
            print('CNO', b.GNSSCNoMax.quantile([0,.5,.9,1]).to_dict())


def project(lat, lon):
    return np.deg2rad(lon) * 6378137, 6378137*np.log(np.tan(np.pi/4+np.deg2rad(lat)/2))


def basemap(ax, bounds):
    x0, x1, y0, y1 = bounds
    zoom = 18 if max(x1-x0, y1-y0) < 1100 else 15
    world = 2*np.pi*6378137
    tile_m = world/(2**zoom)
    tx0, tx1 = math.floor((x0+world/2)/tile_m), math.floor((x1+world/2)/tile_m)
    ty0, ty1 = math.floor((world/2-y1)/tile_m), math.floor((world/2-y0)/tile_m)
    cache = OUT/'tiles'; cache.mkdir(exist_ok=True)
    def fetch(tile):
        tx, ty = tile
        path = cache/f'{zoom}_{tx}_{ty}.png'
        if not path.exists():
            url = f'https://cyberjapandata.gsi.go.jp/xyz/pale/{zoom}/{tx}/{ty}.png'
            req = urllib.request.Request(url, headers={'User-Agent': 'logger-v1-local-analysis/1.0'})
            with urllib.request.urlopen(req, timeout=20) as response:
                data = response.read()
            Image.open(io.BytesIO(data)).verify()
            path.write_bytes(data)
        return tx, ty, np.asarray(Image.open(path).convert('RGB'))
    tiles = [(tx,ty) for tx in range(tx0,tx1+1) for ty in range(ty0,ty1+1)]
    assert len(tiles) <= 64
    with ThreadPoolExecutor(max_workers=4) as pool:
        for tx,ty,pixels in pool.map(fetch, tiles):
            left = tx*tile_m-world/2
            top = world/2-ty*tile_m
            ax.imshow(pixels, extent=[left,left+tile_m,top-tile_m,top], origin='upper', zorder=0)
    ax.set(xlim=(x0,x1),ylim=(y0,y1),aspect='equal')
    ax.set_xticks([]); ax.set_yticks([])
    # Web Mercator distances require latitude correction.
    latitude = np.rad2deg(2*np.arctan(np.exp((y0+y1)/2/6378137))-np.pi/2)
    ground_width = (x1-x0)*np.cos(np.deg2rad(latitude))
    meters = 50 if ground_width < 800 else 500
    length = meters/np.cos(np.deg2rad(latitude))
    xx, yy = x0+(x1-x0)*.05, y0+(y1-y0)*.045
    ax.plot([xx,xx+length],[yy,yy],color='#0f172a',lw=3)
    ax.text(xx+length/2,yy+(y1-y0)*.013,f'{meters} m',ha='center',fontsize=9,
            bbox=dict(facecolor='white',edgecolor='none',alpha=.85,pad=2))


def build_products():
    if not (OUT/'samples.pkl').exists():
        load_logs()
    df = pd.read_pickle(OUT/'samples.pkl')
    manifest = json.loads((OUT/'inventory.json').read_text())
    order = ['LD3A0293F','L5FCBB457','LE17DFD8E','L7910FD12','LDFC3BA92','L937F6476','LAF7F0162','LF51C0BC3']
    colors = dict(zip(order, ['#2563eb','#8b5cf6','#059669','#ea580c','#be185d','#64748b','#a16207','#0891b2']))
    groups, summary, exports = {}, [], []
    for boot in order:
        b = df[df.boot.eq(boot)].copy()
        b['sec'] = np.floor(b.t).astype(int)
        b['imu_good'] = b.IMULink.eq(1) & b.GForceX.notna() & b.GForceY.notna() & b.GForceZ.notna()
        for c in ['GForceX','GForceY','GForceZ','GyroX','GyroY','GyroZ']:
            b.loc[~b.imu_good,c] = np.nan
        b['gyro_sq'] = b[['GyroX','GyroY','GyroZ']].pow(2).sum(axis=1,min_count=3)
        b['acc_sq'] = b[['GForceX','GForceY','GForceZ']].pow(2).sum(axis=1,min_count=3)
        gb = b.groupby('sec')
        seconds = gb.agg(t=('t','median'), samples=('t','size'), imu_n=('GForceX','count'),
                         gyro_sq=('gyro_sq','mean'), acc_sq=('acc_sq','mean'),
                         speed=('GPSSpeed','median'), hacc=('GPSHAcc','median'),
                         sats=('GPSSats','median'), fix=('GPSFix','max'),
                         cno=('GNSSCNoMax','median'), cno4=('GNSSCNoTop4','median'))
        seconds['acc_rms_g'] = np.sqrt(gb[['GForceX','GForceY','GForceZ']].var(ddof=0).sum(axis=1,min_count=3))
        seconds['gyro_rms_dps'] = np.sqrt(seconds.gyro_sq)
        seconds['imu_available'] = (seconds.imu_n >= 70) & (seconds.imu_n/seconds.samples >= .8)
        seconds['quiet'] = seconds.imu_available & seconds.acc_rms_g.lt(.025) & seconds.gyro_rms_dps.lt(3)
        seconds['active'] = seconds.imu_available & (seconds.acc_rms_g.gt(.06) | seconds.gyro_rms_dps.gt(10))
        seconds['motion'] = np.select([~seconds.imu_available, seconds.quiet, seconds.active],['missing','quiet','active'],default='intermediate')
        seconds.loc[~seconds.imu_available,['acc_rms_g','gyro_rms_dps']] = np.nan
        b['fix_good'] = b.GPSFix.isin([2,3,4]) & b.Lat.between(-90,90) & b.Lon.between(-180,180)
        new_epoch = b.GPSTow.notna() & (b.GPSTow.ne(b.GPSTow.shift()) | b.GNSSLink.ne(b.GNSSLink.shift()))
        u = b.loc[b.fix_good & new_epoch].copy()
        u['x'],u['y'] = project(u.Lat,u.Lon)
        # Keep all valid fixes in the export. Quality levels are annotations.
        u['preliminary'] = u.GPSFix.eq(3) & u.GPSSats.ge(4) & u.GPSHAcc.between(0,10,inclusive='right') & u.GPSSpeed.between(0,20)
        u['sec'] = np.floor(u.t).astype(int)
        s = u.groupby('sec').agg(t=('t','median'),Lat=('Lat','median'),Lon=('Lon','median'),
                               GPSSpeed=('GPSSpeed','median'),GPSHAcc=('GPSHAcc','median'),
                               GPSSats=('GPSSats','median'),preliminary=('preliminary','mean'),
                               n=('t','size'))
        s['x'],s['y'] = project(s.Lat,s.Lon)
        s = s.join(seconds[['motion','acc_rms_g','gyro_rms_dps']])
        s['candidate'] = s.preliminary.ge(.8) & s.n.ge(10)
        dt = s.t.diff()
        ground_step = np.hypot(s.x.diff(),s.y.diff())*np.cos(np.deg2rad(s.Lat))
        s['coordinate_speed_mps'] = ground_step/dt
        # A jump breaks BOTH sides of the edge; never connect across missing seconds.
        edge_bad = dt.le(2) & s.coordinate_speed_mps.gt(10)
        s.loc[edge_bad | edge_bad.shift(-1,fill_value=False),'candidate'] = False
        s['quality'] = np.select([~s.candidate, s.GPSSats.lt(5)], ['excluded','limited'], default='candidate')
        s['segment'] = (s.index.to_series().diff().ne(1) | s.candidate.ne(s.candidate.shift()) | s.quality.ne(s.quality.shift())).cumsum()
        s['boot'] = boot
        metadata = [i for i in manifest['files'] if i['boot']==boot]
        offset = next((m['meta'].get('estimated_boot_utc_us',0)/1e6 for m in metadata if m['meta'].get('estimated_boot_utc_us')),np.nan)
        start = pd.to_datetime(offset,unit='s',utc=True).tz_convert('Asia/Tokyo').strftime('%H:%M:%S') if np.isfinite(offset) else None
        s['estimated_jst'] = [pd.to_datetime(offset+t,unit='s',utc=True).tz_convert('Asia/Tokyo').isoformat() if np.isfinite(offset) else '' for t in s.t]
        label = f'{boot}  '+(f'{start} JST' if start else '日時未確定')
        s['sample_count'] = s.n
        exports.append(s.reset_index())
        gaps = np.diff(b.t)
        item = dict(boot=boot,label=label,boot_jst=start,rows=len(b),duration_s=float(b.t.iloc[-1]-b.t.iloc[0]),
                    fix_rows=int(b.fix_good.sum()),unique_fixes=len(u),imu_rows=int(b.imu_good.sum()),
                    valid_fix_seconds=int(b.groupby('sec').fix_good.mean().ge(.5).sum()),
                    candidate_seconds=int(s.candidate.sum()),limited_seconds=int((s.quality=='limited').sum()),
                    active_seconds=int(seconds.active.sum()),quiet_seconds=int(seconds.quiet.sum()),
                    active_without_fix_seconds=int((seconds.active & ~seconds.fix.isin([2,3,4])).sum()),
                    max_speed_kmh=float(u.GPSSpeed.max()) if len(u) else None,
                    file_count=len(metadata),unclean_files=sum(not m['clean_close'] for m in metadata),
                    bad_lines=sum(len(m['bad_lines']) for m in metadata),max_sample_gap_ms=float(gaps.max()*1000),
                    full_calibration_rows=int(b.IMUCal.eq(255).sum()))
        summary.append(item)
        groups[boot] = dict(b=b,s=s,u=u,seconds=seconds,info=item)
        u[['boot','file','t','GPSTow','Lat','Lon','GPSFix','GPSSats','GPSHAcc','GPSSpeed','preliminary']].to_csv(OUT/f'raw_fixes_{boot}.csv',index=False)
    pd.concat(exports,ignore_index=True).to_csv(OUT/'trajectory_1s.csv',index=False)
    pd.DataFrame(summary).to_csv(OUT/'sessions.csv',index=False)
    (OUT/'summary.json').write_text(json.dumps({'source_sha256':manifest['sha256'],'sessions':summary},indent=2,ensure_ascii=False))

    valid_groups = [boot for boot in order if len(groups[boot]['u'])]
    all_raw = pd.concat([groups[k]['u'] for k in valid_groups])
    all_selected = pd.concat([groups[k]['s'].loc[groups[k]['s'].candidate] for k in valid_groups])
    def bounds(data,pad=.12):
        x0,x1,y0,y1 = data.x.min(),data.x.max(),data.y.min(),data.y.max()
        size=max(x1-x0,y1-y0,150)*(1+2*pad)
        return ((x0+x1-size)/2,(x0+x1+size)/2,(y0+y1-size)/2,(y0+y1+size)/2)
    fig,axs=plt.subplots(1,2,figsize=(16,9.8))
    fig.suptitle('GNSSの移動軌跡と、IMUから見た動作',fontsize=20,x=.06,ha='left',y=.98)
    basemap(axs[0],bounds(all_raw))
    basemap(axs[1],bounds(all_selected,.18))
    axs[0].set_title('① 元の全測位点：大きな位置飛びも表示',loc='left',pad=12)
    axs[1].set_title('② 品質選別した軌跡：線を引ける区間だけ',loc='left',pad=12)
    for boot in valid_groups:
        g=groups[boot]; u=g['u']; s=g['s']; color=colors[boot]
        axs[0].scatter(u.x,u.y,s=3,color=color,alpha=.35,rasterized=True)
        for _,line in s[s.candidate].groupby('segment'):
            axs[1].plot(line.x,line.y,color=color,lw=1.3,alpha=.55,ls='--' if line.quality.iloc[0]=='limited' else '-')
        active=s[s.candidate & s.motion.eq('active')]
        axs[1].scatter(active.x,active.y,s=15,c=color,edgecolors='white',linewidths=.2,zorder=4)
        quiet=s[s.candidate & s.motion.eq('quiet')]
        axs[1].scatter(quiet.x,quiet.y,s=4,c=color,alpha=.5,zorder=3)
    handles=[Line2D([0],[0],color=colors[k],lw=3,label=groups[k]['info']['label']) for k in valid_groups]
    fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,.045),ncol=3,frameon=False,fontsize=10)
    fig.text(.06,.115,'太めの点：IMUの動作あり ／ 小さな点：IMU静穏 ／ 破線：衛星4機の参考区間\nIMU静穏でも等速移動は否定できません。線の長さは歩行距離ではありません。',fontsize=10)
    fig.text(.06,.012,'背景：国土地理院「地理院タイル（淡色地図）」 https://maps.gsi.go.jp/development/ichiran.html',fontsize=8,color='#64748b')
    fig.subplots_adjust(top=.90,bottom=.18,left=.04,right=.98,wspace=.08)
    fig.savefig(OUT/'trajectory_map.png',dpi=180); plt.close(fig)

    # Separate boots and monotonic clocks; no invented chronological stitching.
    fig,axs=plt.subplots(8,1,figsize=(14,14),sharex=False)
    fig.suptitle('8回の起動を別々に確認する — GNSSとIMUの有効区間',fontsize=18,y=.99)
    availability_colors={'missing':'#e2e8f0','quiet':'#14b8a6','active':'#f97316','intermediate':'#fde68a'}
    for ax,boot in zip(axs,order):
        g=groups[boot]; sec=g['seconds']; inf=g['info']
        ax.bar(sec.index,1,width=1,color=[availability_colors[m] for m in sec.motion],bottom=0,align='edge')
        ax.bar(sec.index,1,width=1,color=np.where(sec.fix.isin([2,3,4]),'#3b82f6','#e2e8f0'),bottom=1.2,align='edge')
        ax.set_yticks([.5,1.7],['IMU','GNSS']); ax.set_xlim(0,math.ceil(inf['duration_s']/10)*10+1)
        ax.set_title(inf['label']+f"   {inf['duration_s']:.1f}秒 / {inf['rows']:,}行",loc='left',fontsize=10)
        ax.set_xlabel('起動後の経過時間 [秒]',fontsize=9); ax.grid(axis='x',alpha=.5)
    fig.text(.05,.008,'GNSS 青=測位あり ／ IMU 橙=動作あり・緑=静穏・黄=中間 ／ 灰=欠測。上下の起動間を時系列で接続していません。',fontsize=9)
    fig.tight_layout(rect=[0,.025,1,.97]); fig.savefig(OUT/'availability.png',dpi=150); plt.close(fig)

    for boot in order:
        g=groups[boot]; sec=g['seconds']; s=g['s']; inf=g['info']
        fig,axs=plt.subplots(4,1,figsize=(14,10),sharex=True,gridspec_kw={'height_ratios':[1,1.3,1,1]})
        fig.suptitle(inf['label']+' — GNSSとIMUの照合',fontsize=18,x=.08,ha='left',y=.98)
        axs[0].plot(sec.t,sec.speed,color='#2563eb',lw=1.3,label='GNSS速度')
        if sec.speed.max() >= 15:
            axs[0].axhline(20,color='#dc2626',ls='--',lw=.8,label='徒歩用選別の上限 20 km/h')
        if sec.speed.notna().any():
            axs[0].set_ylim(bottom=0)
        else:
            axs[0].text(.02,.55,'この起動では有効なGNSS位置・速度がありません',transform=axs[0].transAxes)
        axs[0].set_ylabel('速度 [km/h]'); axs[0].legend(loc='upper right',fontsize=8)
        axs[1].plot(sec.t,sec.acc_rms_g,color='#f97316',label='加速度の変動 RMS（1秒）')
        axs[1].axhline(.06,color='#f97316',ls=':',lw=1)
        axs[1].set_ylabel('加速度変動 [G]'); ay=axs[1].twinx()
        ay.plot(sec.t,sec.gyro_rms_dps,color='#7c3aed',alpha=.6,label='角速度 RMS（1秒）')
        ay.set_ylabel('角速度 [°/s]',color='#7c3aed'); ay.spines['right'].set_visible(True)
        axs[1].legend(loc='upper left',fontsize=8); ay.legend(loc='upper right',fontsize=8)
        if not sec.imu_available.any():
            axs[1].text(.02,.45,'動作判定に必要なIMU有効サンプルがありません',transform=axs[1].transAxes)
        axs[2].plot(sec.t,sec.sats,color='#059669',lw=1.2,label='測位使用衛星数')
        axs[2].set_ylabel('衛星数'); axh=axs[2].twinx()
        axh.plot(sec.t,sec.hacc,color='#be185d',alpha=.7,label='受信機の精度推定')
        axh.set_ylabel('GPSHAcc [m]',color='#be185d'); axh.spines['right'].set_visible(True)
        axs[2].legend(loc='upper left',fontsize=8); axh.legend(loc='upper right',fontsize=8)
        if sec.cno.notna().any():
            axs[3].plot(sec.t,sec.cno,color='#0891b2',label='最大 C/N0')
            axs[3].plot(sec.t,sec.cno4,color='#64748b',label='上位4機平均 C/N0')
            axs[3].set_ylabel('受信強度 [dB-Hz]'); axs[3].legend(loc='upper right',fontsize=8)
        else:
            axs[3].text(.02,.55,'このファーム版には受信強度の記録がありません',transform=axs[3].transAxes)
            axs[3].set_ylim(0,1); axs[3].set_yticks([])
        for ax in axs:
            ax.grid(alpha=.6)
            # Explicit missing-fix intervals, computed independently for each second.
            missing=~sec.fix.isin([2,3,4])
            ax.fill_between(sec.t,0,1,where=missing,color='#94a3b8',alpha=.12,transform=ax.get_xaxis_transform(),step='mid')
        axs[-1].set_xlabel('起動後の経過時間 [秒]')
        fig.text(.08,.012,'薄い灰色の区間：GNSS測位なし。IMUの動作は検出できますが、そこから絶対位置は復元していません。',fontsize=9)
        fig.tight_layout(rect=[0,.035,1,.95]);fig.savefig(OUT/f'sensors_{boot}.png',dpi=150);plt.close(fig)

    # GPX contains selected GNSS medians only, never inertial-only positions.
    from xml.etree.ElementTree import Element,SubElement,ElementTree
    root=Element('gpx',version='1.1',creator='logger_v1 local GNSS analysis',xmlns='http://www.topografix.com/GPX/1/1')
    for boot in valid_groups:
        track=SubElement(root,'trk');SubElement(track,'name').text=groups[boot]['info']['label']+' / quality-filtered GNSS'
        s=groups[boot]['s']
        for _,line in s[s.candidate].groupby('segment'):
            if len(line)<2:continue
            seg=SubElement(track,'trkseg')
            for row in line.itertuples():
                p=SubElement(seg,'trkpt',lat=f'{row.Lat:.7f}',lon=f'{row.Lon:.7f}')
                if row.estimated_jst:
                    SubElement(p,'time').text=pd.Timestamp(row.estimated_jst).tz_convert('UTC').isoformat().replace('+00:00','Z')
    ElementTree(root).write(OUT/'trajectory_filtered.gpx',encoding='utf-8',xml_declaration=True)
    write_report(manifest,summary,groups,order)
    print(json.dumps(summary,indent=2,ensure_ascii=False),flush=True)


def write_report(manifest,summary,groups,order):
    total=sum(i['rows'] for i in summary); fix=sum(i['fix_rows'] for i in summary)
    bad=sum(i['bad_lines'] for i in summary); unclean=sum(i['unclean_files'] for i in summary)
    notes=f'''# 2026-08-31 SDログの軌跡とIMU解析

元データ：`firmware/logger_v1/logs.zip`。SHA-256：`{manifest['sha256']}`。元ZIP・ファームウェア・実機は変更していません。

## 結果

- 8回の起動、22個のセンサーCSV、合計{total:,}行。測位有効は{fix:,}行（{fix/total:.1%}）。
- 徒歩と整合しない最大259.66km/hの値、数km規模の位置飛びを含みます。全点を結んだ線を実際の歩行経路とは扱えません。
- 日時確定は3起動分のみ。他の起動は経過秒で表示し、前後の起動へ無理に接続していません。
- 旧版のLDFC3BA92はIMU有効値がほぼ欠測です。一方、L7910FD12などではIMUの動作があるのにGNSSが測位していない区間があります。
- GPSFix=3や小さなGPSHAccだけで位置が正しいとは保証できません。IMUが静穏な時間にも位置が動いており、軌跡長には漂いが含まれます。
- 全CSVの列数不一致は{bad}行。正常終了を証明するend.jsonがないCSVが{unclean}個あります。末尾まで構文は読めますが、電源断前の全データ保存は保証できません。

## ファイル

- `trajectory_map.png`：全測位点と品質選別した近傍軌跡の比較。点の大きさでIMUの動作を区別。
- `availability.png`：8回の起動それぞれのGNSS・IMU有効区間。
- `sensors_起動ID.png`：GNSS速度、加速度変動、角速度、衛星数、精度、受信強度。
- `trajectory_filtered.gpx`：選別したGNSS位置の1秒中央値。欠測・除外・再起動を別セグメントに分割。
- `trajectory_1s.csv`：候補・除外・衛星4機の参考点と、IMU動作ラベルを含む1秒集計。
- `sessions.csv`：起動単位の集計。`raw_fixes_*.csv`：重複保持を除いた元のGNSS測位点。

## 選別・IMU利用の方法

100Hz行には25HzのGPS値が繰り返されるため、まずGPSTowの変化で新しい測位を選びます。
GPSFix=3、衛星4機以上、0<GPSHAcc≤10m、GNSS速度0～20km/hを満たす点が1秒内に80%以上あり、
新しい測位が10点以上ある秒を候補としました。1秒中央値の隣接点から計算した速度が10m/sを超える場合は両側を除外します。
衛星4機だけの候補は破線の参考区間です。基準は徒歩を想定した解析上の閾値であり、受信機の正しさを保証しません。
候補の間に1秒以上の欠けがある場合は結ばず、別起動や長い未測位区間もつなぎません。

IMUは3軸の重力除去加速度GForceと角速度を使います。IMULink=1で3軸が有効なサンプルが1秒に70点以上、
かつその秒の80%以上にある場合だけ判定します。加速度は各軸の1秒平均を引いた変動の合成RMS、角速度は合成RMSです。
静穏：加速度変動<0.025Gかつ角速度<3°/s。動作あり：加速度変動>0.06Gまたは角速度>10°/s。それ以外は中間です。
これは移動や歩数の確定ではなく機器の動作判定です。等速移動はIMU静穏と両立し、手で回しただけでも動作ありになります。
IMUの二階積分による架空の位置は追加していません。搭載軸の地図方向への対応と校正が未確定で、
GNSS欠測が長い区間をこのログだけで正確に補うことはできません。

日時は同じ起動のmeta.jsonに保存された推定起動UTCと経過秒から算出しました。GPSUTCの測位時刻とは区別してください。
GPSHAccは受信機内部の推定です。受信強度RFJam=0は「妨害なし」ではなく、状態不明または機能無効を含みます。

背景地図：国土地理院「地理院タイル（淡色地図）」 https://maps.gsi.go.jp/development/ichiran.html 。
地図タイルの取得以外にログを外部へ送信していません。report.htmlは画像を内包し、オフラインで閲覧できます。
'''
    (OUT/'README.md').write_text(notes,encoding='utf-8')
    def image_tag(filename):
        data=base64.b64encode((OUT/filename).read_bytes()).decode()
        return f'<a href="{filename}"><img loading="lazy" alt="{html.escape(filename)}" src="data:image/png;base64,{data}"></a>'
    cards=''.join(f'<div class="card"><strong>{a}</strong><span>{b}</span></div>' for a,b in [(f'{total:,}','100Hzログ行'),('8','起動セッション'),(f'{fix/total:.1%}','測位有効の行'),('259.66 km/h','GNSSの異常速度・実移動ではない')])
    rows=''.join(f"<tr><td>{i['boot']}</td><td>{i['boot_jst'] or '日時未確定'}</td><td>{i['duration_s']:.1f}秒</td><td>{i['fix_rows']/i['rows']:.1%}</td><td>{i['imu_rows']/i['rows']:.1%}</td><td>{i['active_without_fix_seconds']}秒</td></tr>" for i in summary)
    details=''.join(f'<details {"open" if k=="L7910FD12" else ""}><summary>{html.escape(groups[k]["info"]["label"])}</summary>{image_tag("sensors_"+k+".png")}</details>' for k in order)
    document='''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>SDログの軌跡とIMU解析</title><style>
body{font-family:system-ui,sans-serif;margin:0;background:#f1f5f9;color:#172b46;line-height:1.75}main{max-width:1280px;margin:auto;padding:38px 28px}h1{font-size:30px;margin-bottom:6px}h2{margin-top:36px}.eyebrow{color:#059669;font-weight:bold;letter-spacing:2px}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:24px 0}.card{padding:18px;background:white;border-radius:12px}.card strong{font-size:25px;display:block}.card span{font-size:13px;color:#64748b}.notice{padding:18px 22px;background:#fff7ed;border-left:5px solid #f97316;border-radius:6px}img{width:100%;height:auto;border-radius:12px;background:white;margin:14px 0}table{width:100%;border-collapse:collapse;background:white}th,td{padding:10px 12px;border-bottom:1px solid #e2e8f0;text-align:left}summary{cursor:pointer;font-weight:600;padding:15px;background:white;border-radius:8px;margin-top:10px}a{color:#2563eb}.muted{color:#64748b}pre{white-space:pre-wrap;font:inherit;background:white;padding:24px;border-radius:12px;font-size:14px}@media(max-width:700px){main{padding:20px 12px}.cards{grid-template-columns:1fr 1fr}table{font-size:12px}th,td{padding:5px}}
</style><main><div class="eyebrow">LOGGER V1 · 2026-08-31</div><h1>移動軌跡とIMUの解析</h1><p class="muted">SD原本から再構成。未測位区間や再起動を、推測の線でつないでいません。</p>'''+cards+'''<div class="notice"><b>完全な散歩経路の復元はできません。</b> 測位有効でも位置飛びがあり、GNSSが途切れている間はIMUから動作だけを確認できます。地図の線は選別した測位軌跡で、実際の歩行経路や距離の保証ではありません。</div><h2>軌跡：元データと品質選別</h2>'''+image_tag('trajectory_map.png')+'''<p>点が大きい場所はIMUにも動作があります。小さい点はIMU静穏、破線は衛星4機の参考区間です。</p><h2>記録が取れている区間</h2>'''+image_tag('availability.png')+'''<table><thead><tr><th>起動ID</th><th>推定起動時刻 JST</th><th>収録時間</th><th>測位有効</th><th>IMU有効</th><th>動作あり・未測位</th></tr></thead><tbody>'''+rows+'''</tbody></table><h2>起動ごとのGNSS・IMUグラフ</h2><p>見出しを押すとグラフが開きます。横軸は各起動からの経過秒です。</p>'''+details+'''<h2>データと解析条件</h2><p><a href="trajectory_filtered.gpx">GPX軌跡</a> · <a href="trajectory_1s.csv">1秒集計CSV</a> · <a href="sessions.csv">起動別集計</a> · <a href="README.md">解析資料</a></p><pre>'''+html.escape(notes)+'''</pre><p class="muted">背景地図：<a href="https://maps.gsi.go.jp/development/ichiran.html">国土地理院・地理院タイル</a>。ログの外部送信はありません。</p></main></html>'''
    (OUT/'report.html').write_text(document,encoding='utf-8')


if __name__ == '__main__' and '--build' in sys.argv:
    build_products()
elif __name__ == '__main__' and '--explore' in sys.argv:
    explore()
elif __name__ == '__main__':
    df, manifest = load_logs()
    for item in manifest['files']:
        print(json.dumps({k:v for k,v in item.items() if k != 'meta'}, ensure_ascii=False), flush=True)
    print('META EXAMPLE', json.dumps(manifest['files'][0]['meta'], ensure_ascii=False)[:1500])
    for boot, b in df.groupby('boot'):
        valid = b.utc_us.notna()
        offset = ((b.loc[valid, 'utc_us']-b.loc[valid, 'monotonic_us'])/1e6).median()
        print('BOOT', boot, 'duration', b.t.max()-b.t.min(), 'time_offset', offset,
              'IMUCal', b.IMUCal.value_counts().head(6).to_dict(),
              'UTC start', pd.to_datetime(offset, unit='s', utc=True).tz_convert('Asia/Tokyo') if np.isfinite(offset) else None)
