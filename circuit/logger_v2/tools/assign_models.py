from pathlib import Path
import sexpdata as sx
import shutil,json,copy
P=Path(__file__).resolve().parents[1]
K=Path.home()/'AppData/Local/Programs/KiCad/9.0/share/kicad'
S=sx.Symbol
def ch(a,k):return [z for z in a if isinstance(z,list) and str(z[0])==k]
def one(a,k):return ch(a,k)[0]
def prop(a,k):return next(z for z in ch(a,'property') if z[1]==k)
def n(k,*v):return [S(k),*v]
def write(p,a):p.write_text(sx.dumps(a,pretty_print=True)+'\n',encoding='utf-8')
def copy_model(src,dst):
    data=src.read_bytes()
    if dst.exists():
        if dst.read_bytes()==data:return
        dst.chmod(0o666)
    dst.write_bytes(data)
sch=sx.loads((P/'logger_v2.kicad_sch').read_text(encoding='utf-8'))
parts=[z for z in ch(sch,'symbol') if not prop(z,'Reference')[2].startswith('#')]
out=P/'logger_v2_custom.pretty';out.mkdir(exist_ok=True)
models=P/'3dmodels';models.mkdir(exist_ok=True)
model_log=[]; done={}
for c in parts:
    ref=prop(c,'Reference')[2];fp=prop(c,'Footprint')[2]
    if fp not in done:
        lib,name=fp.split(':')
        src=(P.parent/'logger_v1/logger_v1_custom.pretty' if lib=='logger_v1_custom' else K/'footprints'/(lib+'.pretty'))/(name+'.kicad_mod')
        f=sx.loads(src.read_text(encoding='utf-8'));model=one(f,'model')
        if name=='ublox_NEO':
            filename='u-blox_NEO-M9N-00B_mechanical.step';source='u-blox UBX-19014285 R08 mechanical dimensions; generated STEP'
            model=[S('model'),'',n('offset',n('xyz',0,0,0)),n('scale',n('xyz',1,1,1)),n('rotate',n('xyz',0,0,0))]
            one(f,'descr')[1]='u-blox NEO-M9N-00B; 24 pads; 12.2x16.0 mm; 2.4 mm nominal height'
        elif name=='SMA_S-037-TGG_Horizontal':
            filename='COSMTEC_S-037-TGG_mechanical.step';source='COSMTEC S-037-TGG dimensioned drawing, 2008-09-16; generated mechanical STEP'
            model=[S('model'),'',n('offset',n('xyz',0,0,0)),n('scale',n('xyz',1,1,1)),n('rotate',n('xyz',0,0,0))]
            one(f,'descr')[1]='COSMTEC S-037-TGG: 15 mm length, 7 mm square body, 5x diameter 1.5 mm drills on 5.08 mm pattern; own dimension-based mechanical STEP'
        elif name=='AE_BNO055_BO':
            filename='Akizuki_AE-BNO055-BO_mechanical.step';source='Akizuki module drawing: 18x11 mm, DIP8 2.54/7.62 mm; generated mechanical STEP, nominal assembly height'
            model=[S('model'),'',n('offset',n('xyz',0,0,0)),n('scale',n('xyz',1,1,1)),n('rotate',n('xyz',0,0,0))]
        elif name.startswith('Molex_Micro-Fit'):
            filename='Molex_43045-0402_same_geometry_as_0400.step'
            real=Path.home()/'Documents/datalogger/circuit/logger_v1/3dmodels/Molex_43045-0402.step'
            copy_model(real,models/filename)
            source='Molex 43045-0402 STEP. 43045-0400 / 0402 share the same drawing and geometry; finish A (tin) vs C (gold).'
        else:
            srcmodel=Path(model[1].replace('${KICAD9_3DMODEL_DIR}',str(K/'3dmodels')))
            assert srcmodel.exists(),str(srcmodel)
            filename=srcmodel.name
            copy_model(srcmodel,models/filename);source='KiCad 9 package model: '+srcmodel.name
        f[:]=[z for z in f if not(isinstance(z,list) and str(z[0])=='model')]
        model[1]='${KIPRJMOD}/3dmodels/'+filename;f.append(model)
        write(out/(name+'.kicad_mod'),f)
        done[fp]='logger_v2_custom:'+name
        model_log.append({'footprint':done[fp],'model':filename,'source':source})
    prop(c,'Footprint')[2]=done[fp]
library=sx.loads((P/'logger_v2_custom.kicad_sym').read_text(encoding='utf-8'))
defaults={}
for c in parts:
    key=one(c,'lib_id')[1].split(':')[-1]
    fp=prop(c,'Footprint')[2]
    if key not in defaults or 'R_0603' in fp:defaults[key]=fp
for lib in ch(library,'symbol'):
    if lib[1] in defaults:prop(lib,'Footprint')[2]=defaults[lib[1]]
for lib in ch(one(sch,'lib_symbols'),'symbol'):
    key=lib[1].split(':')[-1]
    if key in defaults:prop(lib,'Footprint')[2]=defaults[key]
write(P/'logger_v2_custom.kicad_sym',library)
write(P/'logger_v2.kicad_sch',sch)
write(P/'fp-lib-table',n('fp_lib_table',n('version',7),n('lib',n('name','logger_v2_custom'),n('type','KiCad'),n('uri','${KIPRJMOD}/logger_v2_custom.pretty'),n('options',''),n('descr','EcoLogger v2 portable footprints and models')),n('lib',n('name','Arduino_MountingHole'),n('type','KiCad'),n('uri','${KIPRJMOD}/Arduino_MountingHole.pretty'),n('options',''),n('descr','Existing shield mechanics'))))
(P/'output/model_sources.json').write_text(json.dumps(model_log,indent=2,ensure_ascii=False),encoding='utf-8')
print('Assigned',len(parts),'parts;',len(done),'footprints with local models.')
