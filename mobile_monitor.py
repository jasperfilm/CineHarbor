"""Opt-in, strictly read-only LAN / Tailscale mobile progress monitor with local SVG QR generator.

Security invariants:
- Disabled by default; only binds when explicitly enabled by the local user.
- Fresh random capability token generated in memory on every enable; invalidated immediately on stop.
- Strictly GET/HEAD only (405 on any POST/PUT/DELETE). Zero mutation capability.
- Never reads, stores, or displays OAuth tokens, authorization codes, or unmasked emails.
- QR code SVG is generated 100% locally in pure Python (ISO/IEC 18004 Byte Mode, ECC-L) — URL never sent to third-party QR APIs.
"""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import html, json, secrets, socket, subprocess, threading, time

# Minimal, self-contained ISO/IEC 18004 QR Code SVG encoder (Versions 1..6, Byte mode, ECC Level L)
_CAP_L = {1: (19, 7), 2: (34, 10), 3: (55, 15), 4: (80, 20), 5: (108, 26), 6: (136, 36)}
_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34]}
_GF_EXP = [0] * 512
_GF_LOG = [0] * 256
_x = 1
for _i in range(255):
    _GF_EXP[_i] = _x
    _GF_LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _GF_EXP[_i] = _GF_EXP[_i - 255]


def _gf_mul(a, b):
    return 0 if a == 0 or b == 0 else _GF_EXP[_GF_LOG[a] + _GF_LOG[b]]


def _rs_encode(data_bytes, nsym):
    gen = [1]
    for i in range(nsym):
        nxt = [0] * (len(gen) + 1)
        for j, g in enumerate(gen):
            nxt[j] ^= g
            nxt[j + 1] ^= _gf_mul(g, _GF_EXP[i])
        gen = nxt
    res = list(data_bytes) + [0] * nsym
    for i in range(len(data_bytes)):
        coef = res[i]
        if coef != 0:
            for j in range(1, len(gen)):
                res[i + j] ^= _gf_mul(gen[j], coef)
    return res[len(data_bytes):]


def make_qr_svg(text: str) -> str:
    payload = text.encode('utf-8')
    ver = next((v for v, (dcw, _) in _CAP_L.items() if len(payload) + 3 <= dcw), None)
    if ver is None:
        return ''
    dcw, ecw = _CAP_L[ver]
    bits = [0, 1, 0, 0]  # Byte mode (0100)
    for b in range(7, -1, -1):
        bits.append((len(payload) >> b) & 1)
    for byte in payload:
        for b in range(7, -1, -1):
            bits.append((byte >> b) & 1)
    bits.extend([0] * min(4, dcw * 8 - len(bits)))
    while len(bits) % 8:
        bits.append(0)
    codewords = [int(''.join(str(x) for x in bits[i:i + 8]), 2) for i in range(0, len(bits), 8)]
    pad = [0xEC, 0x11]
    while len(codewords) < dcw:
        codewords.append(pad[len(codewords) % 2])
    # Version 6-L uses 2 blocks of (68 data, 18 ec); Versions 1..5-L use 1 block
    if ver == 6:
        b1, b2 = codewords[:68], codewords[68:]
        e1, e2 = _rs_encode(b1, 18), _rs_encode(b2, 18)
        final_cw = [x for pair in zip(b1, b2) for x in pair] + [x for pair in zip(e1, e2) for x in pair]
    else:
        final_cw = codewords + _rs_encode(codewords, ecw)

    stream = [((cw >> b) & 1) for cw in final_cw for b in range(7, -1, -1)] + [0] * 7
    size = 17 + 4 * ver
    grid = [[None] * size for _ in range(size)]
    reserved = [[False] * size for _ in range(size)]

    def set_mod(r, c, val):
        if 0 <= r < size and 0 <= c < size:
            grid[r][c] = bool(val)
            reserved[r][c] = True

    def finder(tr, tc):
        for r in range(-1, 8):
            for c in range(-1, 8):
                on = (0 <= r <= 6 and 0 <= c <= 6) and (r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4))
                set_mod(tr + r, tc + c, on)

    finder(0, 0)
    finder(0, size - 7)
    finder(size - 7, 0)

    pts = _ALIGN[ver]
    for ar in pts:
        for ac in pts:
            if (ar == 6 and ac == 6) or (ar == 6 and ac == size - 7) or (ar == size - 7 and ac == 6):
                continue
            for r in range(-2, 3):
                for c in range(-2, 3):
                    set_mod(ar + r, ac + c, max(abs(r), abs(c)) != 1)

    for i in range(8, size - 8):
        if not reserved[6][i]:
            set_mod(6, i, i % 2 == 0)
        if not reserved[i][6]:
            set_mod(i, 6, i % 2 == 0)
    set_mod(size - 8, 8, True)

    for i in range(9):
        if i != 6:
            reserved[8][i] = True
            reserved[i][8] = True
    for i in range(8):
        reserved[8][size - 1 - i] = True
        reserved[size - 1 - i][8] = True

    idx = 0
    up = True
    col = size - 1
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if up else range(size)
        for r in rows:
            for dc in (0, -1):
                c = col + dc
                if not reserved[r][c]:
                    bit = stream[idx] if idx < len(stream) else 0
                    idx += 1
                    if (r + c) % 2 == 0:  # Mask 0
                        bit ^= 1
                    grid[r][c] = bool(bit)
        up = not up
        col -= 2

    # Format bits for ECC Level L (01) + Mask 0 (000) -> BCH masked with 101010000010010 = 0x77C4 -> 111011111000100
    fmt = [int(ch) for ch in '111011111000100']
    f_coords_a = [(8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8), (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8)]
    f_coords_b = [(size - 1 - i, 8) for i in range(7)] + [(8, size - 8 + i) for i in range(8)]
    for i, bit in enumerate(fmt):
        r1, c1 = f_coords_a[i]
        r2, c2 = f_coords_b[i]
        grid[r1][c1] = bool(bit)
        grid[r2][c2] = bool(bit)

    rects = [f'<rect x="{c + 3}" y="{r + 3}" width="1" height="1"/>' for r in range(size) for c in range(size) if grid[r][c]]
    box = size + 6
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {box} {box}" width="156" height="156" shape-rendering="crispEdges"><rect width="{box}" height="{box}" fill="#fff" rx="2"/><g fill="#101114">{"".join(rects)}</g></svg>'


def _detect_lan_ips():
    ips = []
    try:
        out = subprocess.check_output(['ifconfig'], text=True, timeout=3)
        for line in out.splitlines():
            line = line.strip()
            if line.startswith('inet '):
                ip = line.split()[1]
                if ip != '127.0.0.1' and not ip.startswith('169.254.'):
                    ips.append(ip)
    except Exception:
        pass
    if not ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
            s.close()
            if ip and ip != '127.0.0.1':
                ips.append(ip)
        except Exception:
            pass
    # Prefer Tailscale (100.x) and standard private LAN (192.168.x / 10.x)
    ips.sort(key=lambda x: (0 if x.startswith('100.') else 1 if x.startswith('192.168.') else 2))
    seen = []
    for ip in ips:
        if ip not in seen:
            seen.append(ip)
    return seen or ['127.0.0.1']


def _mask_email(email: str) -> str:
    if not email or '@' not in email:
        return '未读取'
    user, dom = email.split('@', 1)
    return (user[:2] + '***@' + dom) if len(user) > 2 else ('***@' + dom)


class MobileMonitor:
    def __init__(self, server):
        self.s = server
        self.lock = threading.Lock()
        self.httpd = None
        self.token = None
        self.port = None
        self.started_at = None

    def snapshot(self):
        live_p = self.s.DATA / 'live_status.json'
        live = json.loads(live_p.read_text()) if live_p.exists() else {}
        ws = self.s.load()
        ops = self.s.CONSOLE.all() if self.s.CONSOLE else []
        active_ops = [o for o in ops if o.get('state') in ('queued', 'running')]
        running = next((o for o in active_ops if o.get('state') == 'running'), None)
        queued_cnt = sum(1 for o in active_ops if o.get('state') == 'queued')

        lease_p = self.s.DATA / 'lease.json'
        lease = json.loads(lease_p.read_text()) if lease_p.exists() else None
        start_bal = lease.get('start_balance') if lease else None
        cur_bal = live.get('balance')
        spent = round(max(0.0, float(start_bal) - float(cur_bal)), 2) if (start_bal is not None and cur_bal is not None) else None
        budget = ws.get('policy', {}).get('max_cu_budget', 0) or 0

        return {
            'project': ws.get('project', {}).get('name', 'GC Labs'),
            'account': _mask_email(live.get('email', '')),
            'balance': cur_bal,
            'rate': live.get('rate'),
            'active_vms': live.get('active'),
            'runtime_state': live.get('runtime_state', 'idle'),
            'checked_at': live.get('checked_at', '—'),
            'session_spent_cu': spent,
            'max_cu_budget': budget,
            'budget_paused': bool(ws.get('policy', {}).get('budget_paused')),
            'queued_count': queued_cnt,
            'running_op': {
                'label': running.get('label'),
                'message': running.get('message'),
                'step_done': running.get('step_done'),
                'step_total': running.get('step_total'),
                'eta_seconds': running.get('eta_seconds'),
                'bytes_done': running.get('bytes_done'),
                'bytes_total': running.get('bytes_total'),
            } if running else None,
            'shots_done': sum(1 for s in ws.get('shots', []) if s.get('output')),
            'shots_total': len(ws.get('shots', [])),
        }

    def render_html(self, token):
        return f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GC Labs · 手机只读监看</title>
<style>
body{{margin:0;background:#101114;color:#eeeef1;font:15px -apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;padding:18px}}
.card{{background:#191a20;border:1px solid #303139;border-radius:14px;padding:16px;margin-bottom:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
small{{color:#91939f;font-size:12px;display:block;margin-bottom:4px}}
strong{{font-size:24px;font-weight:600}}
.badge{{display:inline-block;padding:4px 10px;border-radius:16px;font-size:12px;background:#1e2c24;color:#9ce5bf;border:1px solid #38433d}}
.badge.warn{{background:#342f20;color:#ebd39a;border-color:#53482c}}
progress{{width:100%;height:10px;accent-color:#9ce5bf;margin:8px 0}}
</style>
<body>
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
  <b>GC LABS · 只读监看</b><span class="badge">零控制权限 · 安全只读</span>
</div>
<div id="root"><div class="card">正在读取本机工作站状态…</div></div>
<script>
const TOKEN={json.dumps(token)};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
async function tick(){{
  try{{
    const r=await fetch('/m/'+TOKEN+'/data');
    if(!r.ok)throw Error('监看通道已关闭或令牌已失效');
    const d=await r.json();
    const op=d.running_op;
    const pct=op&&op.step_total?Math.min(100,100*(op.step_done||0)/op.step_total):op&&op.bytes_total?Math.min(100,100*(op.bytes_done||0)/op.bytes_total):null;
    document.getElementById('root').innerHTML=`
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div><small>当前项目</small><b>${{esc(d.project)}}</b></div>
          <span class="badge ${{d.runtime_state==='owned'?'':'warn'}}">${{d.runtime_state==='owned'?'● G4 已连接':d.runtime_state==='idle'?'○ GPU 未启动':'● 外部会话'}}</span>
        </div>
        <small style="margin-top:8px">账号 ${{esc(d.account)}} · 最近核对 ${{esc(d.checked_at)}}</small>
      </div>
      <div class="grid" style="margin-bottom:14px">
        <div class="card" style="margin:0"><small>剩余算力</small><strong>${{d.balance!=null?d.balance.toFixed(2):'—'}} <small style="display:inline">CU</small></strong></div>
        <div class="card" style="margin:0"><small>消耗速率</small><strong>${{d.rate!=null?d.rate.toFixed(2):'—'}} <small style="display:inline">CU/h</small></strong></div>
        <div class="card" style="margin:0"><small>本轮已用 / 预算护栏</small><strong>${{d.session_spent_cu!=null?d.session_spent_cu.toFixed(2):'0.00'}} <small style="display:inline">/ ${{d.max_cu_budget>0?d.max_cu_budget+' CU':'不限'}}</small></strong></div>
        <div class="card" style="margin:0"><small>分镜完成度</small><strong>${{d.shots_done}} / ${{d.shots_total}}</strong></div>
      </div>
      ${{d.budget_paused?'<div class="card" style="border-color:#ebd39a"><b style="color:#ebd39a">⚠ 已触发 CU 预算护栏</b><small style="margin-top:6px">后续等待队列已自动暂停；当前采样与 GPU 会话保留，请回电脑端验收释放。</small></div>':''}}
      <div class="card">
        <small>当前执行与批次队列（等待中 ${{d.queued_count}} 项）</small>
        ${{op?`<p style="margin:8px 0"><b>${{esc(op.label)}}</b><br>${{esc(op.message||'')}}</p>${{pct!==null?`<progress value="${{pct}}" max="100"></progress><small>${{pct.toFixed(1)}}%${{op.eta_seconds!=null?' · 预计剩余 '+op.eta_seconds+' 秒':''}}</small>`:''}}`:'<p style="color:#91939f;margin:8px 0">当前没有运行中的任务</p>'}}
      </div>`;
  }}catch(e){{document.getElementById('root').innerHTML='<div class="card">'+esc(e.message)+'</div>'}}
}}
tick();setInterval(tick,4000);
</script></body></html>"""

    def start(self, preferred_port=8769):
        with self.lock:
            if self.httpd:
                return self.status()
            token = secrets.token_urlsafe(16)
            monitor = self

            class ROHandler(BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass

                def do_HEAD(self):
                    self.do_GET()

                def do_GET(self):
                    prefix = f'/m/{token}'
                    if self.path == prefix or self.path == prefix + '/':
                        body = monitor.render_html(token).encode('utf-8')
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/html; charset=utf-8')
                        self.send_header('Cache-Control', 'no-store')
                        self.send_header('Content-Length', str(len(body)))
                        self.end_headers()
                        if self.command != 'HEAD':
                            self.wfile.write(body)
                    elif self.path.startswith(prefix + '/data'):
                        body = json.dumps(monitor.snapshot(), ensure_ascii=False).encode('utf-8')
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json; charset=utf-8')
                        self.send_header('Cache-Control', 'no-store')
                        self.send_header('Content-Length', str(len(body)))
                        self.end_headers()
                        if self.command != 'HEAD':
                            self.wfile.write(body)
                    else:
                        self.send_error(404)

            try:
                srv = ThreadingHTTPServer(('0.0.0.0', preferred_port), ROHandler)
            except OSError:
                srv = ThreadingHTTPServer(('0.0.0.0', 0), ROHandler)
            self.httpd = srv
            self.token = token
            self.port = srv.server_port
            self.started_at = time.time()
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return self.status()

    def stop(self):
        with self.lock:
            if self.httpd:
                self.httpd.shutdown()
                self.httpd.server_close()
            self.httpd = None
            self.token = None
            self.port = None
            self.started_at = None
            return self.status()

    def status(self):
        if not self.httpd or not self.token:
            return {'enabled': False, 'urls': [], 'qr_svg': ''}
        ips = _detect_lan_ips()
        urls = [f'http://{ip}:{self.port}/m/{self.token}' for ip in ips]
        primary = urls[0]
        return {
            'enabled': True,
            'port': self.port,
            'primary_url': primary,
            'urls': urls,
            'qr_svg': make_qr_svg(primary),
            'started_at': self.started_at
        }
