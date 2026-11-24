"""Stream staged original media into an existing runtime. Never executes a graph."""
import asyncio
import base64
import json
import re
import threading
import time
from pathlib import Path
from aiohttp import web
from comfy_project_store import digest


def read_handoff(cache, token):
    if not re.fullmatch('[a-f0-9]{32}', token):
        raise ValueError('Invalid handoff ID')
    record=Path(cache)/'comfy-handoffs'/(token+'.json')
    if not record.is_file() or record.is_symlink() or time.time()-record.stat().st_mtime>24*3600:
        raise ValueError('This handoff expired. Prepare it again in CineHarbor.')
    return json.loads(record.read_text()),record


class AssetTransfer:
    def __init__(self, remote, cache, endpoint):
        self.remote=remote;self.cache=Path(cache);self.endpoint=endpoint
        self.lock=threading.Lock()

    def rpc(self, code):
        return self.remote.run(code+"\nprint('JASPER_RPC: '+json.dumps(__asset_result))")

    def transfer(self, token):
        payload,record=read_handoff(self.cache,token)
        if payload.get('schema')!='cineharbor.comfy-handoff.v2':
            raise ValueError('Unsupported asset handoff')
        assets={a['file']:a for a in payload['assets']}
        directory=record.with_suffix('')
        # Validate all sources before sending any media. No private path enters
        # the response or the remote manifest.
        for name,asset in assets.items():
            if not re.fullmatch(r'cineharbor_[a-f0-9]{24}\.[a-z0-9]+',name):
                raise ValueError('Invalid staged media name')
            p=directory/name
            if p.is_symlink() or not p.is_file() or p.stat().st_size!=asset['bytes'] or digest(p)!=asset['sha256']:
                raise ValueError('Staged media changed or is incomplete. Prepare the handoff again.')
        total=sum(a['bytes'] for a in assets.values())
        self.rpc("import pathlib,hashlib,shutil,base64,json,os\n"
                 "__asset_root=pathlib.Path('/content/ComfyUI/input')\n"
                 "__asset_root.mkdir(parents=True,exist_ok=True)\n"
                 "assert not __asset_root.is_symlink(), 'Unsafe media directory'\n"
                 "assert shutil.disk_usage(__asset_root).free>="+str(total+1024**2)+", 'Not enough runtime disk space'\n"
                 "def __asset_digest(p):\n h=hashlib.sha256()\n with p.open('rb') as f:\n  for b in iter(lambda:f.read(1048576),b''):h.update(b)\n return h.hexdigest()\n"
                 "__asset_result=True")
        mapping={}
        for name,asset in assets.items():
            # Pinned ComfyUI video/audio loaders enumerate input's top level.
            # Content-addressed names preserve bytes without filename collisions.
            relative=name
            expected=asset['sha256']
            ready=self.rpc("__asset_target=__asset_root/"+repr(name)+"\n"
                           "__asset_result=__asset_target.is_file() and __asset_digest(__asset_target)=="+repr(expected))
            if not ready:
                self.rpc("assert not __asset_target.exists(), 'A transferred asset was changed; prepare a new handoff'\n"
                         "__asset_part=__asset_target.with_suffix(__asset_target.suffix+'.partial')\n"
                         "__asset_part.write_bytes(b'')\n__asset_result=True")
                with (directory/name).open('rb') as f:
                    for block in iter(lambda:f.read(4*1024**2),b''):
                        encoded=base64.b64encode(block).decode()
                        self.rpc("with __asset_part.open('ab') as f:f.write(base64.b64decode("+repr(encoded)+"))\n__asset_result=True")
                self.rpc("assert __asset_part.stat().st_size=="+str(asset['bytes'])+", 'Transferred media size mismatch'\n"
                         "assert __asset_digest(__asset_part)=="+repr(expected)+", 'Transferred media checksum mismatch'\n"
                         "__asset_part.replace(__asset_target)\n__asset_result=True")
            mapping[name]=relative
        manifest=json.dumps({'schema':'cineharbor.project-assets.v1','project':payload['project'],
                             'shots':payload['shots'],'assets':payload['assets'],
                             'project_context':payload.get('project_context',{}),
                             'generation_graph':payload['graph'],'positions':payload['positions'],
                             'files':mapping,'warnings':payload.get('warnings',[])},ensure_ascii=False)
        self.rpc("__asset_manifest=__asset_root/"+repr('cineharbor_project_'+token+'.json')+"\n"
                 "__asset_manifest.write_text("+repr(manifest)+",encoding='utf-8')\n__asset_result=True")
        if hasattr(self.remote,'meta_cache'):
            with self.remote.meta_lock:self.remote.meta_cache.clear()
        result={'files':mapping,'verified_files':len(mapping),'assets':len(payload['assets']),
                'bytes':total,'hash_verified':True,'generation_started':False}
        receipt=record.with_suffix('.transfer.json')
        receipt.write_text(json.dumps(dict(result,endpoint=self.endpoint)))
        receipt.chmod(0o600)
        # Avoid official preview timeouts and serial SDK Range requests. These
        # are the same original bytes just verified on this exact runtime.
        from comfy_verified_media import publish
        for name,asset in assets.items():
            publish(self.cache,self.endpoint,name,directory/name,asset['sha256'])
        return result

    async def handle(self, request, token):
        if not self.lock.acquire(blocking=False):
            return web.json_response({'error':'Another asset transfer is in progress.'},status=409)
        try:
            return web.json_response(await asyncio.to_thread(self.transfer,token))
        except Exception:
            # SDK exceptions may contain runtime details. Keep paths out of UI.
            return web.json_response({'error':'Asset transfer was not completed. The current canvas is kept and no generation started. Check runtime connection and disk space, then retry.'},status=400)
        finally:
            self.lock.release()
