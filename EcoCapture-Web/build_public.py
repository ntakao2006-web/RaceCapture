"""Build a separate read-only document; admin scripts and controls are not shipped to it."""
import re
import shutil
from pathlib import Path
root=Path(__file__).parent
out=root/'public';out.mkdir(exist_ok=True)
html=(root/'web/index.html').read_text(encoding='utf-8')
for name in ('logs','settings','device'):
    html=re.sub(r'<section id="'+name+r'".*?</section>','',html,flags=re.S)
    html=re.sub(r'<button class="nav" data-page="'+name+r'".*?</button>','',html)
html=html.replace('<script src="/app.js" defer></script><script src="/device.js" defer></script>','<script src="/viewer.js" defer></script>')
html=re.sub(r'<dialog id="delete-dialog".*?</dialog>','',html,flags=re.S)
html=html.replace('<div class="button-row"><button class="primary" id="start-log">記録開始</button><button id="stop-log" disabled>記録停止</button></div>','<span>閲覧専用</span>')
html=html.replace('WEB / 0.1','WEB / VIEWER')
(out/'index.html').write_text(html,encoding='utf-8')
for file in ('style.css','map-view.js'):shutil.copyfile(root/'web'/file,out/file)
assert all(text not in html for text in ('wifi-password','config-form','start-log','device.js','/app.js','delete-dialog'))
