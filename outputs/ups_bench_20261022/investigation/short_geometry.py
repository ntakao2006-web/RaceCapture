from pathlib import Path
import pcbnew,json,math
root=Path(__file__).resolve().parents[3]
out=Path(__file__).parent
b=pcbnew.LoadBoard(str(root/'circuit/logger_v2_ups/logger_v2_ups.kicad_pcb'))
mm=lambda v:round(pcbnew.ToMM(v),6)
pads=[]
for f,p in ((f,p) for f in b.GetFootprints() for p in f.Pads()):
    if not p.GetNumber() or not p.GetNetname():continue
    box=p.GetBoundingBox()
    pads.append({'id':f.GetReference()+'.'+p.GetNumber(),'ref':f.GetReference(),
                 'net':p.GetNetname(),'x':mm(p.GetPosition().x),'y':mm(p.GetPosition().y),
                 'bbox':[mm(box.GetX()),mm(box.GetY()),mm(box.GetRight()),mm(box.GetBottom())],
                 'layers':[int(x) for x in p.GetLayerSet().Seq() if int(x) in [0,31]]})
pairs=[]
for i,a in enumerate(pads):
 for z in pads[i+1:]:
  layers=set(a['layers'])&set(z['layers'])
  if not layers or a['net']==z['net']:continue
  aa,bb=a['bbox'],z['bbox']
  dx=max(0,aa[0]-bb[2],bb[0]-aa[2]);dy=max(0,aa[1]-bb[3],bb[1]-aa[3])
  gap=math.hypot(dx,dy)
  if gap<=.65:
   pairs.append({'a':a['id'],'a_net':a['net'],'b':z['id'],'b_net':z['net'],
                 'bbox_gap_mm':round(gap,4),'layers':['F.Cu' if x==0 else 'B.Cu' for x in sorted(layers)]})
pairs.sort(key=lambda p:p['bbox_gap_mm'])
data={'method':'Same-layer pad bounding-box gap, screening only. Rounded/circular pad corners can increase actual gap. Does not include traces, zones, component cases, leads bent above the board, or physical solder defects. DRC is a separate check.',
      'pads':pads,'near_pad_pairs':pairs}
(out/'short_geometry.json').write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
print('pads',len(pads),'near different-net pairs',len(pairs))
for p in pairs[:25]:print(p)
