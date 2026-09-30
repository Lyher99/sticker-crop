from __future__ import annotations

import io
import json
import math
import os
import re
import zipfile
from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, render_template_string, request, send_file
from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).parent
UPLOADS = ROOT / "uploads"
UPLOADS.mkdir(exist_ok=True)
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 80 * 1024 * 1024
sheets: dict[str, dict] = {}
stickers: list[dict] = []
STATE_PATH = ROOT / "project.json"


def save_state() -> None:
    payload = {"sheets": [{"id": s["id"], "name": s["name"], "filename": s["path"].name} for s in sheets.values()],
               "stickers": [{k: v for k, v in s.items() if k != "data"} | {"data": s["data"].hex()} for s in stickers]}
    temp = STATE_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(payload), encoding="utf-8")
    temp.replace(STATE_PATH)


def restore_state() -> None:
    if not STATE_PATH.exists():
        return
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        for s in payload.get("sheets", []):
            path = UPLOADS / Path(s["filename"]).name
            if path.is_file():
                with Image.open(path) as im:
                    sheets[s["id"]] = {"id": s["id"], "name": Path(s["name"]).name, "path": path, "width": im.width, "height": im.height}
        stickers.extend({**s, "data": bytes.fromhex(s["data"])} for s in payload.get("stickers", []))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        stickers.clear()
        sheets.clear()


restore_state()

PAGE = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>StickerCrop</title>
<style>
:root{color-scheme:dark;--bg:#11151c;--panel:#1a202a;--line:#303947;--muted:#aab4c2;--accent:#63d5bd}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#eef3f8;font:14px system-ui,Segoe UI,sans-serif;height:100vh;overflow:hidden}header{height:54px;display:flex;align-items:center;gap:10px;padding:0 16px;border-bottom:1px solid var(--line);background:#171c24}header strong{font-size:17px;margin-right:12px}button,.button{border:1px solid #3c4858;background:#252e3b;color:#eff5fa;border-radius:6px;padding:7px 11px;cursor:pointer;font:inherit}button:hover,.button:hover{border-color:var(--accent)}button.primary{background:#176d61;border-color:#299985}.layout{display:grid;grid-template-columns:205px minmax(300px,1fr) 285px;height:calc(100vh - 54px)}aside{background:var(--panel);padding:13px;overflow:auto}aside.left{border-right:1px solid var(--line)}aside.right{border-left:1px solid var(--line)}h2{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:2px 0 12px}.sheets,.tray{display:flex;flex-direction:column;gap:8px}.sheet,.sticker{display:flex;align-items:center;gap:9px;padding:7px;border:1px solid transparent;border-radius:7px;cursor:pointer;min-width:0}.sheet.active,.sticker.active{border-color:var(--accent);background:#252f39}.sheet img{width:48px;height:42px;object-fit:contain;background:#111;border-radius:4px}.sheet span,.sticker span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.sticker{background:#202733}.sticker img{width:54px;height:48px;object-fit:contain;background-color:#fff;background-image:linear-gradient(45deg,#ccc 25%,transparent 25%),linear-gradient(-45deg,#ccc 25%,transparent 25%),linear-gradient(45deg,transparent 75%,#ccc 75%),linear-gradient(-45deg,transparent 75%,#ccc 75%);background-size:12px 12px;background-position:0 0,0 6px,6px -6px,-6px 0;border-radius:4px}.workspace{display:flex;flex-direction:column;min-width:0}.toolbar{display:flex;align-items:center;gap:7px;padding:9px;border-bottom:1px solid var(--line);flex-wrap:wrap}.toolbar .spacer{flex:1}.toolbar small,.muted{color:var(--muted)}.view{flex:1;position:relative;overflow:hidden;background-color:#10151b;background-image:radial-gradient(#29313b 1px,transparent 1px);background-size:18px 18px}canvas{position:absolute;touch-action:none;cursor:crosshair}canvas:focus{outline:2px solid var(--accent);outline-offset:-2px}.welcome{position:absolute;inset:0;display:grid;place-items:center;text-align:center;color:var(--muted);pointer-events:none}.welcome div{max-width:360px}.drop{border:1px dashed #586575;border-radius:10px;padding:20px;margin-top:14px}.hint{font-size:12px;line-height:1.5;color:var(--muted);margin-top:14px}.count{color:var(--accent)}.tray-head{display:flex;justify-content:space-between;align-items:center}.tray{padding-bottom:18px}.name{background:#121820;border:1px solid #384453;color:white;border-radius:4px;padding:5px;width:125px}.actions{display:flex;gap:4px;margin-left:auto}.actions button{padding:4px 7px}.message{position:fixed;bottom:14px;left:50%;transform:translateX(-50%);background:#25313e;border:1px solid #556477;padding:9px 14px;border-radius:7px;display:none;z-index:10}.busy{opacity:.65;pointer-events:none}@media(max-width:850px){.layout{grid-template-columns:150px minmax(250px,1fr)}aside.right{display:none}} 
.workspace{min-height:0}.toolbar{flex:0 0 auto;min-height:50px}.toolbar button{flex:0 0 auto;white-space:nowrap}.view{min-height:0}.output-settings{border:1px solid var(--line);border-radius:7px;padding:9px;margin:0 0 12px;background:#171d26}.output-settings label{font-size:12px;color:var(--muted)}.output-dims{display:flex;align-items:center;gap:5px;margin-top:7px}.output-dims input{width:76px;background:#111720;color:white;border:1px solid #3a4654;border-radius:4px;padding:5px}#panHint{white-space:nowrap;color:#aab4c2}@media(max-width:1100px){ #panHint{display:none}}.toolbar label#cropSizeControls{display:inline-flex;align-items:center;gap:5px;padding:4px 7px;background:#1b222c;border:1px solid #394554;border-radius:6px;font-size:12px;color:#d3dce6}.toolbar label#cropSizeControls input[type=number]{background:#10161d;color:#fff;border:1px solid #465366;border-radius:4px;padding:4px}.toolbar label#cropSizeControls input[type=checkbox]{accent-color:#63d5bd}.name{width:72px}.sticker{gap:4px;padding:5px}.sticker img{width:40px;height:40px}.sticker button{padding:4px 5px;font-size:12px}</style></head><body><header><strong>✂ StickerCrop</strong><label class="button">Add image sheets<input id="files" type="file" accept="image/png,image/jpeg,image/webp" multiple hidden></label><button id="fit">Fit sheet</button><button id="zoomOut">−</button><button id="zoomIn">+</button><span class="spacer"></span><button id="zip" class="primary">Download all as ZIP</button></header>
<div class="layout"><aside class="left"><h2>Image sheets</h2><div class="sheets" id="sheets"></div><div class="hint">Drop PNG, JPG or WebP sheets here. Image processing stays on this computer.</div></aside><main class="workspace"><div class="toolbar"><button id="extract" class="primary">Extract selection ↵</button><button id="saveCrop" class="primary" style="display:none">Save new crop ↵</button><button id="backEdit" style="display:none">Back to sheet</button><button id="redrawCrop" style="display:none">Draw new bounds</button><button id="clear">Clear selection</button><label id="cropSizeControls" title="Keep the crop proportions while resizing. A new locked selection starts square." style="display:none;white-space:nowrap">Lock ratio <input id="lockRatio" type="checkbox"><span>W</span><input id="cropWidth" type="number" min="2" aria-label="Crop width in source pixels" style="width:62px"><span>H</span><input id="cropHeight" type="number" min="2" aria-label="Crop height in source pixels" style="width:62px"></label><small id="editLabel" style="display:none">Move inside crop or drag handles to resize</small><span class="spacer"></span><small id="dimensions">No selection</small><small id="panHint">Space + drag pans ? wheel or +/- zooms</small></div><div class="view" id="view"><canvas id="canvas" tabindex="0" aria-label="Image sheet canvas. Press Space and drag to pan, use arrow keys to move the crop, plus or minus to zoom."></canvas><div class="welcome" id="welcome"><div><h2 style="color:#eef3f8">Extract stickers, one selection at a time</h2><p>Choose a sheet and drag around one sticker. Drag inside the box to move it; drag a handle to resize. Use Space + drag to pan, wheel or +/? to zoom, arrow keys to nudge (Shift + arrows moves 10 px), then press Enter to extract.</p><div class="drop">Drop image files anywhere in this window<br><small>PNG · JPG · WebP</small></div></div></div></div></main><aside class="right"><div class="tray-head"><h2>Stickers</h2><b class="count" id="count">0</b></div><section class="output-settings"><label><input type="checkbox" id="customOutput"> Apply custom canvas to downloads</label><div class="output-dims"><input id="outputWidth" type="number" min="1" max="4096" value="750" aria-label="Output width"><span>x</span><input id="outputHeight" type="number" min="1" max="4096" value="750" aria-label="Output height"><span>px</span></div><div class="hint">Set a common export size here. Use Size beside a sticker to adjust that sticker separately.</div></section><div class="tray" id="tray"></div><div class="hint">Rename items inline. Click a thumbnail to download that PNG. JPG checkerboards are real pixels; PNG export does not remove them.</div></aside></div><div class="message" id="message"></div>
<script>
const $=id=>document.getElementById(id), canvas=$('canvas'),ctx=canvas.getContext('2d');let sheetList=[],active=null,img=null,zoom=1,offset={x:0,y:0},sel=null,drag=null,stickers=[],draftTimer=null;const DRAFT_KEY='stickercrop-editor-draft';
async function downloadFile(url,filename,button){let old=button&&button.textContent;if(button){button.disabled=true;button.textContent='Preparing...'}try{let response=await fetch(url);if(!response.ok){let data={};try{data=await response.json()}catch{}throw Error(data.error||'The download failed. Please try again.')}let blob=await response.blob(),objectUrl=URL.createObjectURL(blob),link=document.createElement('a');link.href=objectUrl;link.download=filename;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(objectUrl),60000);msg('Download started: '+filename)}catch(error){msg(error.message||'The download failed. Please try again.')}finally{if(button){button.disabled=false;button.textContent=old}}}function outputUrl(path){let enabled=$('customOutput')&&$('customOutput').checked;if(!enabled)return path;let w=Number($('outputWidth').value),h=Number($('outputHeight').value);if(!Number.isInteger(w)||!Number.isInteger(h)||w<1||h<1||w>4096||h>4096||w*h>16777216){msg('Output dimensions must be 1 to 4096 pixels, with at most 16 million pixels total.');return null}return path+'?width='+w+'&height='+h}function saveOutputPrefs(){localStorage.setItem('sticker-output',JSON.stringify({enabled:$('customOutput').checked,width:$('outputWidth').value,height:$('outputHeight').value}))}function msg(s){let m=$('message');m.textContent=s;m.style.display='block';clearTimeout(msg.t);msg.t=setTimeout(()=>m.style.display='none',3000)}
function fit(){if(!img)return;let v=$('view').getBoundingClientRect();zoom=Math.min((v.width-36)/img.width,(v.height-36)/img.height,1);offset={x:(v.width-img.width*zoom)/2,y:(v.height-img.height*zoom)/2};draw()}
function persistDraftNow(){try{let mode=editing?'crop':layoutEditing?'layout':'sheet';localStorage.setItem(DRAFT_KEY,JSON.stringify({version:1,mode,sheetId:active,selection:sel,zoom,offset,editId:editing,layoutId:layoutEditing,drawNewBounds,lockedRatio,layoutParams,layoutPan,layoutViewFactor,returnView:viewBeforeEdit?{active:viewBeforeEdit.active,zoom:viewBeforeEdit.zoom,offset:viewBeforeEdit.offset}:null,lockRatio:$('lockRatio').checked}))}catch{}}function persistDraft(){clearTimeout(draftTimer);draftTimer=setTimeout(persistDraftNow,80)}function readDraft(){try{let d=JSON.parse(localStorage.getItem(DRAFT_KEY)||'null');return d&&d.version===1?d:null}catch{return null}}window.addEventListener('pagehide',persistDraftNow);document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')persistDraftNow()});function resize(){let dpr=devicePixelRatio||1,v=$('view').getBoundingClientRect();canvas.width=v.width*dpr;canvas.height=v.height*dpr;canvas.style.width=v.width+'px';canvas.style.height=v.height+'px';ctx.setTransform(dpr,0,0,dpr,0,0);draw()}
function draw(){if(!ctx||!canvas.width)return;let v=$('view').getBoundingClientRect();ctx.clearRect(0,0,v.width,v.height);if(layoutEditing){drawLayout();persistDraft();return}if(!img){persistDraft();return}ctx.imageSmoothingEnabled=true;ctx.drawImage(img,offset.x,offset.y,img.width*zoom,img.height*zoom);if(sel){let{x,y,w,h}=sel;$('cropSizeControls').style.display=layoutEditing?'none':'inline-flex';if(document.activeElement!==$('cropWidth'))$('cropWidth').value=Math.round(w);if(document.activeElement!==$('cropHeight'))$('cropHeight').value=Math.round(h);ctx.save();ctx.fillStyle='rgba(0,0,0,.34)';ctx.fillRect(offset.x,offset.y,img.width*zoom,img.height*zoom);ctx.clearRect(offset.x+x*zoom,offset.y+y*zoom,w*zoom,h*zoom);ctx.drawImage(img,x,y,w,h,offset.x+x*zoom,offset.y+y*zoom,w*zoom,h*zoom);ctx.strokeStyle='#54e2c5';ctx.lineWidth=2;ctx.setLineDash([6,3]);ctx.strokeRect(offset.x+x*zoom,offset.y+y*zoom,w*zoom,h*zoom);ctx.setLineDash([]);let handles=[[x,y],[x+w/2,y],[x+w,y],[x,y+h/2],[x+w,y+h/2],[x,y+h],[x+w/2,y+h],[x+w,y+h]];for(let [px,py] of handles){ctx.fillStyle='#fff';ctx.strokeStyle='#008e78';ctx.lineWidth=1;ctx.shadowColor='#071016';ctx.shadowBlur=4;ctx.fillRect(offset.x+px*zoom-6,offset.y+py*zoom-6,12,12);ctx.shadowBlur=0;ctx.strokeRect(offset.x+px*zoom-6,offset.y+py*zoom-6,12,12)}ctx.restore();$('dimensions').textContent=`${Math.round(w)} × ${Math.round(h)} source pixels`;}else{$('cropSizeControls').style.display='none';$('dimensions').textContent='No selection'}persistDraft()}
function renderSheets(){let box=$('sheets');box.replaceChildren();sheetList.forEach(s=>{let d=document.createElement('div');d.className='sheet'+(active===s.id?' active':'');let im=document.createElement('img');im.src='/api/sheets/'+s.id+'/thumb';let name=document.createElement('span');name.textContent=s.name;d.append(im,name);d.onclick=()=>openSheet(s.id);box.append(d)})}
async function openSheet(id,view=null){let r=await fetch('/api/sheets/'+id);if(!r.ok)return msg('Could not load that image sheet.');try{let blob=await r.blob(),next=new Image();next.src=URL.createObjectURL(blob);await next.decode();img=next;active=id;$('welcome').style.display='none';sel=view&&view.selection?view.selection:null;resize();if(view&&Number.isFinite(view.zoom)&&view.offset){zoom=view.zoom;offset=view.offset;draw()}else fit();renderSheets()}catch{msg('Could not decode that image sheet.')}}
function renderTray(){let box=$('tray');box.replaceChildren();$('count').textContent=stickers.length;stickers.forEach((s,i)=>{let d=document.createElement('div');d.className='sticker';let im=document.createElement('img');im.src='/api/stickers/'+s.id+'/thumb';im.title='Download PNG';im.onclick=()=>{let url=outputUrl('/api/stickers/'+s.id+'/png');if(url)downloadFile(url,s.name)};let input=document.createElement('input');input.className='name';input.value=s.name;input.setAttribute('aria-label','Sticker filename');input.onchange=async()=>{let r=await fetch('/api/stickers/'+s.id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:input.value})});if(r.ok){stickers=await r.json();renderTray()}else msg('Could not rename sticker.')};let edit=document.createElement('button');edit.textContent='Crop';edit.title='Change the source crop bounds';edit.onclick=()=>beginEdit(s.id);let size=document.createElement('button');size.textContent='Size';size.title='Resize and position artwork on the output canvas';size.onclick=()=>beginLayout(s.id);let del=document.createElement('button');del.textContent='×';del.title='Remove sticker';del.onclick=async()=>{stickers=await(await fetch('/api/stickers/'+s.id,{method:'DELETE'})).json();renderTray()};d.append(im,input,edit,size,del);box.append(d)})}
async function upload(files){for(let f of files){if(!/^image\/(png|jpeg|webp)$/.test(f.type)){msg('Choose PNG, JPG or WebP images.');continue}let fd=new FormData();fd.append('file',f);let r=await fetch('/api/sheets',{method:'POST',body:fd});if(!r.ok){msg((await r.json()).error||'Could not open image.');continue}let s=await r.json();sheetList.push(s);renderSheets();await openSheet(s.id)}}
$('files').onchange=e=>upload(e.target.files);window.addEventListener('dragover',e=>e.preventDefault());window.addEventListener('drop',e=>{e.preventDefault();if(e.dataTransfer.files.length)upload(e.dataTransfer.files)});new ResizeObserver(resize).observe($('view'));
let editing=null,spaceDown=false,viewBeforeEdit=null,drawNewBounds=false,layoutEditing=null,layoutImage=null,layoutParams=null,layoutZoom=1,layoutBoard={x:0,y:0},layoutPan={x:0,y:0},layoutViewFactor=1,layoutDragging=null,lockedRatio=1;
function setEditorUi(){let crop=!!editing,size=!!layoutEditing,on=crop||size;$('cropSizeControls').style.display=(!size&&!!sel)?'inline-flex':'none';$('extract').style.display=on?'none':'';$('saveCrop').style.display=crop?'':'none';$('saveLayout').style.display=size?'':'none';$('cancelLayout').style.display=size?'':'none';$('scaleControl').style.display=size?'':'none';$('backEdit').style.display=crop?'':'none';$('redrawCrop').style.display=crop?'':'none';$('redrawCrop').textContent=drawNewBounds?'Adjust bounds':'Draw new bounds';$('clear').style.display=on?'none':'';$('editLabel').style.display=crop?'':'none';$('fit').textContent=size?'Fit canvas':crop?'Fit crop':'Fit sheet'}
async function beginEdit(id,resume=null){let s=stickers.find(x=>x.id===id);if(!s)return;viewBeforeEdit=resume&&resume.returnView?{...resume.returnView,img:null}:{active,img,zoom,offset:{...offset}};editing=id;drawNewBounds=!!(resume&&resume.drawNewBounds);if(active!==s.source){let r=await fetch('/api/sheets/'+s.source);if(!r.ok){editing=null;return msg('Original sheet is missing.');}img=new Image();img.src=URL.createObjectURL(await r.blob());await img.decode();active=s.source;}sel=resume&&resume.selection?resume.selection:{x:s.bounds[0],y:s.bounds[1],w:s.bounds[2]-s.bounds[0],h:s.bounds[3]-s.bounds[1]};resize();let v=$('view').getBoundingClientRect();if(resume&&Number.isFinite(resume.zoom)&&resume.offset){zoom=resume.zoom;offset=resume.offset;lockedRatio=resume.lockedRatio||sel.w/sel.h;$('lockRatio').checked=!!resume.lockRatio}else{zoom=Math.min(10,Math.max(.05,Math.min((v.width*.72)/sel.w,(v.height*.72)/sel.h)));offset={x:v.width/2-(sel.x+sel.w/2)*zoom,y:v.height/2-(sel.y+sel.h/2)*zoom}}$('welcome').style.display='none';setEditorUi();renderSheets();canvas.focus({preventScroll:true});draw()}
async function endEdit(){editing=null;sel=null;setEditorUi();if(viewBeforeEdit){let saved=viewBeforeEdit;viewBeforeEdit=null;if(saved.active&&saved.img){active=saved.active;img=saved.img;zoom=saved.zoom;offset=saved.offset;resize();renderSheets()}else if(saved.active){await openSheet(saved.active,saved)}else if(active){await openSheet(active)}}draw()}
async function saveCrop(){if(!editing||!sel||sel.w<2||sel.h<2)return msg('Draw a larger crop area first.');let r=await fetch('/api/stickers/'+editing+'/crop',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({x:Math.floor(sel.x),y:Math.floor(sel.y),w:Math.ceil(sel.w),h:Math.ceil(sel.h)})});if(!r.ok)return msg((await r.json()).error||'Could not update crop.');stickers=await r.json();renderTray();msg('Sticker crop updated.');await endEdit()}
function outputDims(){let width=Number($('outputWidth').value),height=Number($('outputHeight').value);if(!Number.isInteger(width)||!Number.isInteger(height)||width<1||height<1||width>4096||height>4096||width*height>16777216)throw Error('Set valid output canvas dimensions first.');return{width,height}}
async function beginLayout(id,resume=null){if(editing)await endEdit();let sticker=stickers.find(x=>x.id===id);if(!sticker)return;try{let dims=resume&&resume.layoutParams?resume.layoutParams:outputDims();$('outputWidth').value=dims.width;$('outputHeight').value=dims.height;viewBeforeEdit=resume&&resume.returnView?{...resume.returnView,img:null}:{active,img,zoom,offset:{...offset}};layoutPan=resume&&resume.layoutPan?resume.layoutPan:{x:0,y:0};layoutViewFactor=resume&&resume.layoutViewFactor?resume.layoutViewFactor:1;layoutEditing=id;layoutParams={...dims,scale:1,dx:0,dy:0};if(resume&&resume.layoutParams)Object.assign(layoutParams,resume.layoutParams);else if(sticker.layout&&sticker.layout.width===dims.width&&sticker.layout.height===dims.height)Object.assign(layoutParams,sticker.layout);let response=await fetch('/api/stickers/'+id+'/raw');if(!response.ok)throw Error('Could not load the extracted sticker.');layoutImage=new Image();layoutImage.src=URL.createObjectURL(await response.blob());await layoutImage.decode();$('layoutScale').value=Math.round(layoutParams.scale*100);$('scaleValue').textContent=$('layoutScale').value+'%';setEditorUi();resize();canvas.focus({preventScroll:true});draw()}catch(e){layoutEditing=null;setEditorUi();msg(e.message||'Could not open output size editor.')}}
function drawLayout(){if(!layoutEditing||!layoutImage||!layoutParams)return;let v=$('view').getBoundingClientRect(),W=layoutParams.width,H=layoutParams.height;layoutZoom=Math.min((v.width-60)/W,(v.height-60)/H,1)*layoutViewFactor;layoutBoard={x:(v.width-W*layoutZoom)/2+layoutPan.x,y:(v.height-H*layoutZoom)/2+layoutPan.y};ctx.save();ctx.fillStyle='#fff';ctx.fillRect(layoutBoard.x,layoutBoard.y,W*layoutZoom,H*layoutZoom);let tile=Math.max(6,12*layoutZoom);ctx.fillStyle='#d8d8d8';for(let yy=0;yy<H*layoutZoom;yy+=tile*2)for(let xx=0;xx<W*layoutZoom;xx+=tile*2){ctx.fillRect(layoutBoard.x+xx,layoutBoard.y+yy,tile,tile);ctx.fillRect(layoutBoard.x+xx+tile,layoutBoard.y+yy+tile,tile,tile)}ctx.strokeStyle='#54e2c5';ctx.lineWidth=1;ctx.strokeRect(layoutBoard.x,layoutBoard.y,W*layoutZoom,H*layoutZoom);ctx.beginPath();ctx.rect(layoutBoard.x,layoutBoard.y,W*layoutZoom,H*layoutZoom);ctx.clip();let fitScale=Math.min(W/layoutImage.width,H/layoutImage.height)*layoutParams.scale,aw=layoutImage.width*fitScale,ah=layoutImage.height*fitScale,x=layoutBoard.x+(W/2+layoutParams.dx-aw/2)*layoutZoom,y=layoutBoard.y+(H/2+layoutParams.dy-ah/2)*layoutZoom;ctx.imageSmoothingEnabled=true;ctx.drawImage(layoutImage,x,y,aw*layoutZoom,ah*layoutZoom);ctx.strokeStyle='#fff';ctx.setLineDash([5,4]);ctx.strokeRect(x,y,aw*layoutZoom,ah*layoutZoom);ctx.setLineDash([]);ctx.restore();$('dimensions').textContent=W+' x '+H+' output canvas; artwork '+Math.round(layoutParams.scale*100)+'%'}
async function saveLayout(){if(!layoutEditing||!layoutParams)return;let r=await fetch('/api/stickers/'+layoutEditing+'/layout',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(layoutParams)});if(!r.ok)return msg((await r.json()).error||'Could not save output size.');stickers=await r.json();renderTray();msg('Sticker output size saved.');await endLayout()}
async function endLayout(){layoutEditing=null;layoutImage=null;layoutParams=null;layoutDragging=null;setEditorUi();if(viewBeforeEdit){let saved=viewBeforeEdit;viewBeforeEdit=null;if(saved.active&&saved.img){active=saved.active;img=saved.img;zoom=saved.zoom;offset=saved.offset;resize();renderSheets()}else if(saved.active)await openSheet(saved.active,saved);else if(active)await openSheet(active)}draw()}
function point(e){let r=canvas.getBoundingClientRect();return{x:(e.clientX-r.left-offset.x)/zoom,y:(e.clientY-r.top-offset.y)/zoom}}
function clamp(v,max){return Math.max(0,Math.min(max,v))}
function hitHandle(p){if(!sel)return null;let sx=p.x*zoom,sy=p.y*zoom,x=sel.x*zoom,y=sel.y*zoom,w=sel.w*zoom,h=sel.h*zoom,t=13;let nearL=Math.abs(sx-x)<t,nearR=Math.abs(sx-x-w)<t,nearT=Math.abs(sy-y)<t,nearB=Math.abs(sy-y-h)<t;if(nearT&&nearL)return 'nw';if(nearT&&nearR)return 'ne';if(nearB&&nearL)return 'sw';if(nearB&&nearR)return 'se';if(nearT&&sx>x&&sx<x+w)return 'n';if(nearB&&sx>x&&sx<x+w)return 's';if(nearL&&sy>y&&sy<y+h)return 'w';if(nearR&&sy>y&&sy<y+h)return 'e';return null}
canvas.onpointerdown=e=>{if(!img&&!layoutEditing)return;canvas.setPointerCapture(e.pointerId);canvas.focus({preventScroll:true});let p=point(e);if(spaceDown||e.button===1){drag={type:'pan',px:e.clientX,py:e.clientY,ox:layoutEditing?layoutPan.x:offset.x,oy:layoutEditing?layoutPan.y:offset.y,layout:!!layoutEditing};return}if(layoutEditing){layoutDragging={x:e.clientX,y:e.clientY,dx:layoutParams.dx,dy:layoutParams.dy};return}p.x=clamp(p.x,img.width);p.y=clamp(p.y,img.height);let handle=drawNewBounds?null:hitHandle(p);if(handle){drag={type:'resize',handle,start:p,orig:{...sel},ratio:sel.w/sel.h}}else if(!drawNewBounds&&sel&&p.x>=sel.x&&p.x<=sel.x+sel.w&&p.y>=sel.y&&p.y<=sel.y+sel.h){drag={type:'move',start:p,orig:{...sel}}}else{drag={type:'new',start:p};sel={x:p.x,y:p.y,w:0,h:0}}draw()};canvas.onpointermove=e=>{if(layoutDragging){layoutParams.dx=layoutDragging.dx+(e.clientX-layoutDragging.x)/layoutZoom;layoutParams.dy=layoutDragging.dy+(e.clientY-layoutDragging.y)/layoutZoom;draw();return}if(!drag)return;if(drag.type==='pan'){if(drag.layout)layoutPan={x:drag.ox+e.clientX-drag.px,y:drag.oy+e.clientY-drag.py};else offset={x:drag.ox+e.clientX-drag.px,y:drag.oy+e.clientY-drag.py};draw();return}let p=point(e);p.x=clamp(p.x,img.width);p.y=clamp(p.y,img.height);if(drag.type==='new'){let dx=p.x-drag.start.x,dy=p.y-drag.start.y,w=Math.abs(dx),h=Math.abs(dy),ratio=1;if($('lockRatio').checked&&(w||h)){let wantedW=Math.max(w,h*ratio),factor=Math.min(1,(dx<0?drag.start.x:img.width-drag.start.x)/Math.max(wantedW,1),(dy<0?drag.start.y:img.height-drag.start.y)/Math.max(wantedW/ratio,1));w=wantedW*factor;h=w/ratio}sel={x:dx<0?drag.start.x-w:drag.start.x,y:dy<0?drag.start.y-h:drag.start.y,w,h}}else if(drag.type==='move'){let x=clamp(drag.orig.x+p.x-drag.start.x,img.width-drag.orig.w),y=clamp(drag.orig.y+p.y-drag.start.y,img.height-drag.orig.h);sel={...drag.orig,x,y}}else{let o=drag.orig,h=drag.handle,l=o.x,t=o.y,r=o.x+o.w,b=o.y+o.h;if(h.includes('w'))l=clamp(p.x,r-2);if(h.includes('e'))r=clamp(p.x,img.width);if(h.includes('n'))t=clamp(p.y,b-2);if(h.includes('s'))b=clamp(p.y,img.height);if($('lockRatio').checked){let ratio=drag.ratio;if(h.length===2){let ww=r-l,hh=b-t;if(ww/hh>ratio)hh=ww/ratio;else ww=hh*ratio;if(h.includes('w'))l=r-ww;else r=l+ww;if(h.includes('n'))t=b-hh;else b=t+hh}else if(h==='e'||h==='w'){let ww=r-l,hh=ww/ratio,cy=o.y+o.h/2;t=cy-hh/2;b=cy+hh/2}else{let hh=b-t,ww=hh*ratio,cx=o.x+o.w/2;l=cx-ww/2;r=cx+ww/2}l=clamp(l,img.width);t=clamp(t,img.height);r=clamp(r,img.width);b=clamp(b,img.height)}sel={x:l,y:t,w:r-l,h:b-t}}draw()};canvas.onpointerup=e=>{if(layoutDragging){layoutDragging=null;return}drag=null;if(sel&&$('lockRatio').checked)lockedRatio=sel.w/sel.h;if(sel&&(sel.w<2||sel.h<2)&&!editing){sel=null;draw()}};canvas.onpointercancel=()=>drag=null;
canvas.onwheel=e=>{if(layoutEditing){e.preventDefault();layoutViewFactor=Math.max(.25,Math.min(4,layoutViewFactor*(e.deltaY<0?1.12:1/1.12)));draw();return}if(!img)return;e.preventDefault();let r=canvas.getBoundingClientRect(),cx=e.clientX-r.left,cy=e.clientY-r.top,worldX=(cx-offset.x)/zoom,worldY=(cy-offset.y)/zoom,next=Math.max(.05,Math.min(10,zoom*(e.deltaY<0?1.15:1/1.15)));offset={x:cx-worldX*next,y:cy-worldY*next};zoom=next;draw()};
async function extract(){if(!active||!sel)return msg('Select an area of the sheet first.');let r=await fetch('/api/extract',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sheet_id:active,x:Math.floor(sel.x),y:Math.floor(sel.y),w:Math.ceil(sel.w),h:Math.ceil(sel.h)})});if(!r.ok)return msg((await r.json()).error||'Extraction failed.');stickers=await r.json();sel=null;draw();renderTray()}
$('lockRatio').onchange=()=>{if(sel)lockedRatio=sel.w/sel.h;persistDraft()};$('cropWidth').oninput=()=>changeCropSize('w');$('cropHeight').oninput=()=>changeCropSize('h');function changeCropSize(axis){if(!sel||!img)return;let val=Number(axis==='w'?$('cropWidth').value:$('cropHeight').value);if(!Number.isFinite(val)||val<2)return;let ratio=lockedRatio||sel.w/sel.h;if(axis==='w'){sel.w=Math.min(img.width-sel.x,Math.round(val));if($('lockRatio').checked)sel.h=Math.min(img.height-sel.y,Math.max(2,Math.round(sel.w/ratio)))}else{sel.h=Math.min(img.height-sel.y,Math.round(val));if($('lockRatio').checked)sel.w=Math.min(img.width-sel.x,Math.max(2,Math.round(sel.h*ratio)))}lockedRatio=sel.w/sel.h;draw()}$('extract').onclick=extract;$('saveCrop').onclick=saveCrop;$('saveLayout').onclick=saveLayout;$('cancelLayout').onclick=endLayout;$('layoutScale').oninput=e=>{if(layoutParams){layoutParams.scale=Number(e.target.value)/100;$('scaleValue').textContent=e.target.value+'%';draw()}};$('backEdit').onclick=endEdit;$('redrawCrop').onclick=()=>{drawNewBounds=!drawNewBounds;setEditorUi();persistDraft();msg(drawNewBounds?'Drag a new rectangle around the sticker.':'Drag inside to move or use the handles to adjust.')};$('clear').onclick=()=>{sel=null;draw()};$('fit').onclick=()=>{if(layoutEditing){layoutViewFactor=1;layoutPan={x:0,y:0};draw();return}if(editing&&sel){let v=$('view').getBoundingClientRect();zoom=Math.min(10,Math.max(.05,Math.min((v.width*.72)/sel.w,(v.height*.72)/sel.h)));offset={x:v.width/2-(sel.x+sel.w/2)*zoom,y:v.height/2-(sel.y+sel.h/2)*zoom};draw()}else fit()};$('zoomIn').onclick=()=>zoomCanvas(1.2);$('zoomOut').onclick=()=>zoomCanvas(1/1.2);$('zip').onclick=()=>{if(!stickers.length)return msg('Extract at least one sticker first.');let url=outputUrl('/api/export.zip');if(url)downloadFile(url,'stickers.zip',$('zip'))};
function zoomCanvas(factor){if(layoutEditing){layoutViewFactor=Math.max(.25,Math.min(4,layoutViewFactor*factor));draw();return}if(!img)return;let v=$('view').getBoundingClientRect(),cx=v.width/2,cy=v.height/2,wx=(cx-offset.x)/zoom,wy=(cy-offset.y)/zoom,next=Math.max(.05,Math.min(10,zoom*factor));offset={x:cx-wx*next,y:cy-wy*next};zoom=next;draw()}window.onkeydown=e=>{if(e.target.matches('input,textarea,select,[contenteditable=true]'))return;if(e.code==='Space'){if(document.activeElement===canvas||canvas.matches(':hover')){spaceDown=true;e.preventDefault()}return}if(document.activeElement!==canvas)return;if((e.ctrlKey||e.metaKey)&&(e.key==='+'||e.key==='=')){e.preventDefault();zoomCanvas(1.2);return}if((e.ctrlKey||e.metaKey)&&e.key==='-'){e.preventDefault();zoomCanvas(1/1.2);return}if(e.key==='+'||e.key==='='){e.preventDefault();zoomCanvas(1.2);return}if(e.key==='-'){e.preventDefault();zoomCanvas(1/1.2);return}if(e.key.toLowerCase()==='f'){e.preventDefault();$('fit').click();return}if(e.key.startsWith('Arrow')){if(!sel&&!layoutEditing)return;e.preventDefault();let step=e.shiftKey?10:1,dx=e.key==='ArrowLeft'?-step:e.key==='ArrowRight'?step:0,dy=e.key==='ArrowUp'?-step:e.key==='ArrowDown'?step:0;if(layoutEditing){layoutParams.dx+=dx;layoutParams.dy+=dy}else if(sel&&img){sel.x=clamp(sel.x+dx,img.width-sel.w);sel.y=clamp(sel.y+dy,img.height-sel.h)}draw();return}if(e.key==='Enter'){e.preventDefault();layoutEditing?saveLayout():editing?saveCrop():extract()}if(e.key==='Escape'){if(layoutEditing)endLayout();else if(editing)endEdit();else{sel=null;draw()}}};window.onkeyup=e=>{if(e.code==='Space')spaceDown=false};window.onblur=()=>{spaceDown=false;drag=null;layoutDragging=null};
async function init(){try{let pref=JSON.parse(localStorage.getItem('sticker-output')||'{}');$('customOutput').checked=!!pref.enabled;if(pref.width)$('outputWidth').value=pref.width;if(pref.height)$('outputHeight').value=pref.height}catch{}$('customOutput').onchange=saveOutputPrefs;function outputDimensionChanged(){saveOutputPrefs();if(layoutEditing)try{let d=outputDims();layoutParams.width=d.width;layoutParams.height=d.height;layoutParams.dx=0;layoutParams.dy=0;draw()}catch(e){msg(e.message)}}$('outputWidth').oninput=outputDimensionChanged;$('outputHeight').oninput=outputDimensionChanged;let d=await(await fetch('/api/state')).json();sheetList=d.sheets;stickers=d.stickers;renderSheets();renderTray();let draft=readDraft();if(draft&&draft.mode==='crop'&&stickers.some(s=>s.id===draft.editId)){await beginEdit(draft.editId,draft);msg('Restored your crop editing session.');return}if(draft&&draft.mode==='layout'&&stickers.some(s=>s.id===draft.layoutId)){await beginLayout(draft.layoutId,draft);msg('Restored your size editing session.');return}if(draft&&sheetList.some(s=>s.id===draft.sheetId)){await openSheet(draft.sheetId,draft);return}if(sheetList.length)await openSheet(sheetList[0].id)}init();
</script></body></html>'''


def load_sheet(sid: str) -> Image.Image:
    item = sheets.get(sid)
    if not item:
        raise KeyError("Image sheet not found")
    with Image.open(item["path"]) as im:
        return im.convert("RGBA")


def safe_name(name: str) -> str:
    name = re.sub(r"[^\w.-]+", "-", name.strip(), flags=re.UNICODE).strip(".-")
    if not name:
        name = "sticker"
    return name[:80]


def public_stickers() -> list[dict]:
    return [{k: v for k, v in s.items() if k != "data"} for s in stickers]


def export_image(sticker: dict, width: int | None, height: int | None) -> bytes:
    """Return the original crop, or fit it centered on a transparent custom canvas."""
    layout = sticker.get("layout")
    use_layout = bool(layout and ((width is None and height is None) or (width == layout["width"] and height == layout["height"])))
    if width is None and height is None and not use_layout:
        return sticker["data"]
    if use_layout:
        width, height = int(layout["width"]), int(layout["height"])
    if width is None or height is None or width < 1 or height < 1 or width > 4096 or height > 4096 or width * height > 16_777_216:
        raise ValueError("Output dimensions must be 1–4096 pixels with at most 16 million pixels total.")
    with Image.open(io.BytesIO(sticker["data"])) as original:
        artwork = original.convert("RGBA")
    ratio = min(width / artwork.width, height / artwork.height)
    scale = float(layout["scale"]) if use_layout else 1.0
    ratio *= scale
    size = (max(1, round(artwork.width * ratio)), max(1, round(artwork.height * ratio)))
    artwork = artwork.resize(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    left = round((width - size[0]) / 2 + (float(layout["dx"]) if use_layout else 0))
    top = round((height - size[1]) / 2 + (float(layout["dy"]) if use_layout else 0))
    # Clip artwork dragged partly beyond the output canvas.
    dst_left, dst_top = max(0, left), max(0, top)
    dst_right, dst_bottom = min(width, left + size[0]), min(height, top + size[1])
    if dst_right > dst_left and dst_bottom > dst_top:
        source_part = artwork.crop((dst_left - left, dst_top - top, dst_right - left, dst_bottom - top))
        canvas.alpha_composite(source_part, (dst_left, dst_top))
    output = io.BytesIO()
    canvas.save(output, "PNG")
    return output.getvalue()


def requested_output_size() -> tuple[int | None, int | None]:
    if "width" not in request.args and "height" not in request.args:
        return None, None
    if "width" not in request.args or "height" not in request.args:
        raise ValueError("Provide both output width and height.")
    try:
        return int(request.args["width"]), int(request.args["height"])
    except (ValueError, TypeError):
        raise ValueError("Output width and height must be whole numbers.")


@app.get("/")
def index():
    return render_template_string(PAGE)


@app.get("/api/state")
def state():
    return jsonify(sheets=[{"id": s["id"], "name": s["name"]} for s in sheets.values()], stickers=public_stickers())


@app.post("/api/sheets")
def add_sheet():
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify(error="Choose an image file to upload."), 400
    sid = uuid4().hex
    path = UPLOADS / f"{sid}.image"
    try:
        raw = upload.read()
        with Image.open(io.BytesIO(raw)) as im:
            if im.width * im.height > 80_000_000:
                return jsonify(error="Image is too large (over 80 million pixels). Try a smaller image."), 400
            im.verify()
        path.write_bytes(raw)
        with Image.open(path) as im:
            w, h = im.size
        item = {"id": sid, "name": Path(upload.filename).name, "path": path, "width": w, "height": h}
        sheets[sid] = item
        save_state()
        return jsonify(id=sid, name=item["name"])
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        path.unlink(missing_ok=True)
        return jsonify(error="This image could not be decoded. Try exporting it as PNG, JPG or WebP."), 400


@app.get("/api/sheets/<sid>")
def sheet_image(sid):
    item = sheets.get(sid)
    return send_file(item["path"]) if item else ("Not found", 404)


@app.get("/api/sheets/<sid>/thumb")
def sheet_thumb(sid):
    try:
        im = load_sheet(sid)
    except KeyError:
        return "Not found", 404
    im.thumbnail((160, 120))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.post("/api/extract")
def extract():
    data = request.get_json(force=True)
    try:
        im = load_sheet(str(data["sheet_id"]))
        x, y, w, h = (int(data[k]) for k in ("x", "y", "w", "h"))
    except (KeyError, ValueError, TypeError):
        return jsonify(error="Selection or source sheet is invalid."), 400
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(im.width, x + w), min(im.height, y + h)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return jsonify(error="Selection is too small. Drag a larger rectangle."), 400
    crop = im.crop((x0, y0, x1, y1))
    buf = io.BytesIO()
    crop.save(buf, "PNG")
    seq = len(stickers) + 1
    stickers.append({"id": uuid4().hex, "name": f"sticker-{seq:03d}.png", "data": buf.getvalue(), "width": crop.width, "height": crop.height, "source": data["sheet_id"], "bounds": [x0, y0, x1, y1]})
    save_state()
    return jsonify(public_stickers())


@app.get("/api/stickers/<sid>/thumb")
def sticker_thumb(sid):
    sticker = next((s for s in stickers if s["id"] == sid), None)
    if not sticker:
        return "Not found", 404
    with Image.open(io.BytesIO(sticker["data"])) as im:
        im.thumbnail((150, 110))
        buf = io.BytesIO()
        im.save(buf, "PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.get("/api/stickers/<sid>/raw")
def sticker_raw(sid):
    sticker = next((s for s in stickers if s["id"] == sid), None)
    if not sticker:
        return "Not found", 404
    return send_file(io.BytesIO(sticker["data"]), mimetype="image/png")


@app.get("/api/stickers/<sid>/png")
def sticker_png(sid):
    sticker = next((s for s in stickers if s["id"] == sid), None)
    if not sticker:
        return "Not found", 404
    try:
        data = export_image(sticker, *requested_output_size())
    except ValueError as error:
        return jsonify(error=str(error)), 400
    return send_file(io.BytesIO(data), mimetype="image/png", as_attachment=True, download_name=safe_name(sticker["name"]))


@app.patch("/api/stickers/<sid>/crop")
def recrop_sticker(sid):
    sticker = next((s for s in stickers if s["id"] == sid), None)
    if not sticker:
        return jsonify(error="Sticker not found."), 404
    try:
        source = load_sheet(sticker["source"])
        data = request.get_json(force=True)
        x, y, w, h = (int(data[k]) for k in ("x", "y", "w", "h"))
    except (KeyError, ValueError, TypeError, UnidentifiedImageError, OSError):
        return jsonify(error="The original sheet or crop bounds are invalid."), 400
    x0, y0, x1, y1 = max(0, x), max(0, y), min(source.width, x + w), min(source.height, y + h)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return jsonify(error="Crop must be at least 2 × 2 pixels."), 400
    crop = source.crop((x0, y0, x1, y1))
    buf = io.BytesIO()
    crop.save(buf, "PNG")
    sticker.update(data=buf.getvalue(), width=crop.width, height=crop.height, bounds=[x0, y0, x1, y1])
    save_state()
    return jsonify(public_stickers())


@app.patch("/api/stickers/<sid>/layout")
def save_sticker_layout(sid):
    sticker = next((s for s in stickers if s["id"] == sid), None)
    if not sticker:
        return jsonify(error="Sticker not found."), 404
    try:
        data = request.get_json(force=True)
        width, height = int(data["width"]), int(data["height"])
        scale, dx, dy = float(data["scale"]), float(data["dx"]), float(data["dy"])
        if width < 1 or height < 1 or width > 4096 or height > 4096 or width * height > 16_777_216:
            raise ValueError("Canvas dimensions must be 1 to 4096 pixels, with at most 16 million pixels total.")
        if not all(math.isfinite(v) for v in (scale, dx, dy)) or not (0.1 <= scale <= 4.0) or abs(dx) > width * 3 or abs(dy) > height * 3:
            raise ValueError("Scale or position is outside the supported range.")
    except (KeyError, TypeError, ValueError) as error:
        return jsonify(error=str(error) or "Canvas size, scale, and position must be valid numbers."), 400
    sticker["layout"] = {"width": width, "height": height, "scale": scale, "dx": dx, "dy": dy}
    save_state()
    return jsonify(public_stickers())


@app.route("/api/stickers/<sid>", methods=["PATCH", "DELETE"])
def sticker_item(sid):
    idx = next((i for i, s in enumerate(stickers) if s["id"] == sid), None)
    if idx is None:
        return jsonify(error="Sticker not found."), 404
    if request.method == "DELETE":
        stickers.pop(idx)
    else:
        stickers[idx]["name"] = safe_name(str((request.get_json() or {}).get("name", "sticker")))
        if not stickers[idx]["name"].lower().endswith(".png"):
            stickers[idx]["name"] += ".png"
    save_state()
    return jsonify(public_stickers())


@app.get("/api/export.zip")
def export_zip():
    buf = io.BytesIO()
    used = set()
    try:
        output_size = requested_output_size()
    except ValueError as error:
        return jsonify(error=str(error)), 400
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        for sticker in stickers:
            base = safe_name(sticker["name"])
            stem = base[:-4] if base.lower().endswith(".png") else base
            name, n = stem + ".png", 2
            while name.casefold() in used:
                name = f"{stem}-{n}.png"
                n += 1
            used.add(name.casefold())
            try:
                archive.writestr(name, export_image(sticker, *output_size))
            except ValueError as error:
                return jsonify(error=str(error)), 400
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name="stickers.zip")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
