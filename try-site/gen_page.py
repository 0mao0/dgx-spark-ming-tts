# -*- coding: utf-8 -*-
"""生成 Ming TTS 公网试听站单文件页面（内嵌音色，无 ASR，鉴权由 VPS 注入）。"""
import base64, json, io, wave

VOICE_DIR = "voices"
VOICES = [
    ("q-serena",   "Serena · 女声"),
    ("q-aiden",    "Aiden · 男声"),
    ("q-vivian",   "Vivian · 女声"),
    ("q-uncle_fu", "Uncle Fu · 男声"),
]

def wav_info(path):
    with wave.open(path, "rb") as w:
        return {"sr": w.getframerate(), "dur": w.getnframes() / w.getframerate()}

voices_json = []
for vid, label in VOICES:
    raw = open(f"{VOICE_DIR}/{vid}.wav", "rb").read()
    txt = open(f"{VOICE_DIR}/{vid}.txt", encoding="utf-8").read().strip()
    info = wav_info(f"{VOICE_DIR}/{vid}.wav")
    voices_json.append({
        "id": vid, "label": label,
        "b64": base64.b64encode(raw).decode(),
        "ref_text": txt,
        "ref_dur": round(info["dur"], 1),
    })

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ming-3.0-TTS 试听站 · DGX Spark GB10</title>
<style>
  :root { --bg:#0f1115; --card:#171a21; --line:#252a35; --fg:#e8eaf0; --mut:#8b93a5;
          --acc:#5aa2ff; --ok:#4cc38a; --warn:#e8b04b; --hot:#e06c75; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--fg);
         font:14px/1.6 "PingFang SC","Microsoft YaHei",system-ui,sans-serif; }
  .wrap { max-width:860px; margin:0 auto; padding:28px 20px 60px; }
  h1 { font-size:22px; margin:0 0 4px; }
  h1 .tag { font-size:11px; color:var(--bg); background:var(--acc); border-radius:4px;
            padding:2px 7px; vertical-align:middle; margin-left:8px; }
  .sub { color:var(--mut); font-size:12.5px; margin-bottom:22px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:10px;
          padding:18px; margin-bottom:16px; }
  label { color:var(--mut); font-size:12px; display:block; margin-bottom:6px; }
  textarea { width:100%; min-height:92px; background:#10131a; color:var(--fg);
             border:1px solid var(--line); border-radius:8px; padding:10px 12px;
             font:14px/1.6 inherit; resize:vertical; }
  select { background:#10131a; color:var(--fg); border:1px solid var(--line);
           border-radius:8px; padding:8px 10px; font:inherit; }
  .row { display:flex; gap:12px; flex-wrap:wrap; align-items:end; margin-top:12px; }
  button { background:var(--acc); color:#0b1524; border:0; border-radius:8px;
           padding:9px 20px; font:600 14px inherit; cursor:pointer; }
  button.ghost { background:transparent; color:var(--acc); border:1px solid var(--acc); }
  button.stop { background:var(--hot); color:#fff; }
  button:disabled { opacity:.45; cursor:not-allowed; }
  .chips { display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }
  .chip { border:1px solid var(--line); color:var(--mut); border-radius:999px;
          padding:4px 12px; font-size:12px; cursor:pointer; }
  .chip:hover { color:var(--acc); border-color:var(--acc); }
  .m { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-top:14px; }
  .m .b { background:#10131a; border:1px solid var(--line); border-radius:8px; padding:10px; }
  .m .k { color:var(--mut); font-size:11px; }
  .m .v { font-size:19px; font-variant-numeric:tabular-nums; margin-top:2px; }
  .status { margin-top:12px; font-size:12.5px; color:var(--mut); min-height:18px; }
  .status .ok{color:var(--ok)} .status .warn{color:var(--warn)} .status .hot{color:var(--hot)}
  table { width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums; }
  th,td { text-align:left; padding:7px 10px; border-bottom:1px solid var(--line); font-size:12.5px; }
  th { color:var(--mut); font-weight:500; }
  .bar { height:5px; background:#10131a; border-radius:3px; overflow:hidden; margin-top:12px; }
  .bar i { display:block; height:100%; width:0; background:var(--acc); transition:width .2s; }
  .foot { color:var(--mut); font-size:11.5px; margin-top:26px; line-height:1.8; }
  .foot code { color:var(--fg); background:#10131a; padding:1px 6px; border-radius:4px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Ming-3.0-TTS 试听站<span class="tag">GB10 单机</span></h1>
  <div class="sub">inclusionAI Ming-3.0-tts-tiny（8.98B MoE）· vLLM-Omni #9119+#9198 · 44.1kHz 流式 · 无质检直出（本页不含任何 ASR 验证环节）</div>

  <div class="card">
    <label>文本</label>
    <textarea id="txt">欢迎来到 Ming 语音合成试听。你听到的每一个字，都是这台巴掌大的机器现场生成的——没有云端，没有质检，直接从模型流向你的耳朵。</textarea>
    <div class="chips" id="chips"></div>
    <div class="row">
      <div><label>音色</label><select id="voice"></select></div>
      <button id="go">▶ 朗读</button>
      <button id="stop" class="stop" disabled>■ 停止</button>
      <button id="rp" disabled>↻ 整段重播</button>
      <span class="status" id="st"></span>
    </div>
    <div class="bar"><i id="bar"></i></div>
    <div id="dlbox" style="display:none;gap:12px;align-items:center;margin:10px 0">
      <audio id="au" controls style="height:34px;max-width:340px"></audio>
      <a id="wavdl" download>⬇ 下载完整 WAV</a>
    </div>
    <div class="m">
      <div class="b"><div class="k">首包 TTFT</div><div class="v" id="m_ttft">–</div></div>
      <div class="b"><div class="k">总耗时</div><div class="v" id="m_wall">–</div></div>
      <div class="b"><div class="k">音频时长</div><div class="v" id="m_dur">–</div></div>
      <div class="b"><div class="k">实时率 RTF</div><div class="v" id="m_rtf">–</div></div>
    </div>
  </div>

  <div class="card">
    <label style="font-size:13px;color:var(--fg)">并发演示 —— 四路齐读（不同文本同时请求，感受单机并发）</label>
    <div class="row"><button id="go4" class="ghost">⇉ 四路齐读</button><span class="status" id="st4"></span></div>
    <div style="margin-top:12px"><table>
      <thead><tr><th>#</th><th>音色</th><th>TTFT</th><th>总耗时</th><th>音频</th><th>RTF</th><th>状态</th></tr></thead>
      <tbody id="t4"></tbody>
    </table></div>
  </div>

  <div class="foot">
    口径：公网链路 <code>浏览器 → tts.angineer.cn(VPS) → Tailscale → dgx2:8101</code>，TTFT 含公网两跳。<br>
    鉴权由 VPS 在 <code>/api/ming-try/</code> 转发层注入，页面源码不含任何密钥；限频 8 r/s/IP。<br>
    服务：dgx2 omni 容器 · vllm 0.32 + PR#9198 覆盖层 · 10 路档 30G · 输出 PCM 44.1kHz（浏览器端封装播放）。
  </div>
</div>

<script>
const VOICES = __VOICES__;
const API = "/api/ming-try/v1/audio/speech";
const SR = 44100;
const sel = document.getElementById("voice");
for (const v of VOICES) {
  const o = document.createElement("option");
  o.value = v.id; o.textContent = v.label + "（参考音 " + v.ref_dur + "s）";
  sel.appendChild(o);
}
const SAMPLES = [
  ["自我介绍", "大家好，我是这台服务器合成的声音。同一套权重，既能克隆参考音里的这个人，也能用一句文字描述从零造一个新音色。"],
  ["数字与英文", "今天的报告有三组数字：首包延迟 0.53 秒，十路并发墙钟 16.8 秒，聚合吞吐每秒 18 个字。Note that it also handles English numbers like 44.1 kHz."],
  ["长文压力", "语音合成真正的难点从来不是把一句话读清楚，而是把一分钟不间断的长文读稳：气息要连贯，音色不能飘，遇到数字、英文和标点停顿还要处理得自然。下面这段就是专门用来考验长文稳定性的。大模型把文字变成波形，就像把一幅画逐像素地画出来，任何一个像素出错，耳朵都能听出来。所以当我们说这台机器每秒能生成十八个字的语音，而且十路同时开火也不掉速，真正的含义是：它的显存、算力和调度，全部扛住了这条长链路。"]
];
const chips = document.getElementById("chips");
for (const [name, t] of SAMPLES) {
  const c = document.createElement("span");
  c.className = "chip"; c.textContent = name;
  c.onclick = () => { document.getElementById("txt").value = t; };
  chips.appendChild(c);
}

let ctx = null;
function ac() { return ctx || (ctx = new (window.AudioContext || window.webkitAudioContext)()); }

const BASE_SEED = 7;
function bodyFor(text, voice, seed) {
  const v = VOICES.find(x => x.id === voice);
  return JSON.stringify({ model: "ming3", input: text, response_format: "pcm",
    stream: true, language: "zh", seed: seed,
    ref_audio: "data:audio/wav;base64," + v.b64, ref_text: v.ref_text, voice: v.id });
}

function b64ToFloat(b64) {
  const bin = atob(b64), u = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
  const i16 = new Int16Array(u.buffer), f = new Float32Array(i16.length);
  for (let i = 0; i < i16.length; i++) f[i] = i16[i] / 32768;
  return f;
}

let curSources = [], curChunks = [], ticker = null, playhead = 0;
function stopAll() {
  for (const s of curSources) { try { s.stop(); } catch (e) {} }
  curSources = [];
  if (ticker) { clearInterval(ticker); ticker = null; }
  playhead = 0;
}

async function speakOnce(text, voice, ui, t0, seed) {
  const r = await fetch(API, { method: "POST", headers: { "Content-Type": "application/json" },
                               body: bodyFor(text, voice, seed), signal: ui.signal });
  if (!r.ok) throw new Error("HTTP " + r.status + " " + (await r.text()).slice(0, 120));
  const rd = r.body.getReader(), dec = new TextDecoder();
  let buf = "", ttft = null, bytes = 0, done = false;
  const actx = ac();
  if (actx.state === "suspended") await actx.resume();
  let nextT = Math.max(playhead, actx.currentTime + 0.1);
  ui.onOpen && ui.onOpen();
  while (!done) {
    const { value, done: rf } = await rd.read();
    if (rf) break;
    buf += dec.decode(value, { stream: true });
    let k;
    while ((k = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, k); buf = buf.slice(k + 2);
      for (const line of frame.split("\n")) {
        if (!line.startsWith("data:")) continue;
        let obj; try { obj = JSON.parse(line.slice(5)); } catch { continue; }
        if (obj.error || obj.type === "error") {
          throw new Error("生成出错：" + (obj.error && obj.error.message || obj.message || "服务端返回错误帧"));
        }
        if (!obj.audio) continue;
        const f = b64ToFloat(obj.audio);
        if (!f.length) continue;
        if (ttft === null) { ttft = (performance.now() - t0) / 1000; ui.onTTFT(ttft); }
        const b = actx.createBuffer(1, f.length, SR);
        b.copyToChannel(f, 0);
        const s = actx.createBufferSource(); s.buffer = b; s.connect(actx.destination);
        const st = Math.max(nextT, actx.currentTime + 0.02);
        s.start(st); nextT = st + b.duration; playhead = nextT;
        if (ui.collect !== false) {
          curSources.push(s);
          if (curChunks.length < 100) curChunks.push(f);
        }
        bytes += f.length * 2;
        ui.onBytes(bytes, nextT - actx.currentTime);
      }
      if (/speech\.audio\.done/.test(frame)) done = true;
    }
  }
  const wall = (performance.now() - t0) / 1000;
  const dur = bytes / (2 * SR);
  const rem = () => playhead - actx.currentTime;
  if (!done) {
    const err = new Error(dur > 0.3
      ? "连接中断：音频在约 " + dur.toFixed(1) + " 秒处断流，未收完（可点“朗读”重试）"
      : "连接中断：没收到任何音频（自动重试也没成功，请稍后再试）");
    err.partial = { ttft, wall, dur, rtf: wall / (dur || 1) };
    throw err;
  }
  return { ttft, wall, dur, rtf: wall / (dur || 1), rem };
}


function splitText(text, maxChars) {
  const units = text.match(/[^。！？；
]+[。！？；
]?/g) || [text];
  const out = [];
  let cur = "";
  for (const u of units) {
    if (cur && (cur + u).length > maxChars) { out.push(cur); cur = ""; }
    if (u.length > maxChars) {
      for (let i = 0; i < u.length; i += maxChars) out.push(u.slice(i, i + maxChars));
    } else {
      cur += u;
    }
  }
  if (cur) out.push(cur);
  return out.length ? out : [text];
}

async function speak(text, voice, ui) {
  const t0 = performance.now();
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const m = await speakOnce(text, voice, ui, t0, BASE_SEED + attempt);
      // 模型偶发退化：个别 seed 会在十几步就出结束符，只出 1 秒空音。换 seed 重来。
      if (m.dur < 2 && attempt < 2) {
        stopAll(); curChunks = [];
        ui.onRetry && ui.onRetry(true);
        continue;
      }
      return m;
    } catch (e) {
      if (e.name === "AbortError" || (e.partial && e.partial.dur > 0.3)) throw e;
      ui.onRetry && ui.onRetry(false);
    }
  }
  throw new Error("连续 3 次未能生成完整音频，请稍后重试");
}

let curAbort = null;
const $ = id => document.getElementById(id);
function setM(m) {
  $("m_ttft").textContent = m.ttft == null ? "–" : m.ttft.toFixed(2) + " s";
  $("m_wall").textContent = m.wall.toFixed(2) + " s";
  $("m_dur").textContent  = m.dur.toFixed(2) + " s";
  $("m_rtf").textContent  = m.rtf.toFixed(3);
  $("m_rtf").style.color  = m.rtf < 1 ? "var(--ok)" : "var(--warn)";
}

$("go").onclick = async () => {
  const btn = $("go"), st = $("st");
  stopAll(); $("rp").disabled = true;
  curChunks = [];
  curAbort = new AbortController();
  btn.disabled = true; $("stop").disabled = false;
  $("bar").style.width = "0"; setM({ ttft: null, wall: 0, dur: 0, rtf: 0 });
  st.innerHTML = "请求中…";
  try {
    const fullText = $("txt").value.trim();
    const segs = splitText(fullText, 200);
    let m = null, ttft = null, wall = 0, dur = 0;
    for (let i = 0; i < segs.length; i++) {
      const label = segs.length > 1 ? "第 " + (i + 1) + "/" + segs.length + " 段 · " : "";
      const part = await speak(segs[i], sel.value, {
        signal: curAbort.signal,
        onOpen: () => st.innerHTML = label + "已连接，等待首包…",
        onTTFT: () => st.innerHTML = label + "<span class=ok>出声了</span>，边生成边播",
        onRetry: degen => st.innerHTML = label + (degen ? "声音退化（过短），换 seed 自动重试…" : "连接断了，自动重试 1 次…"),
        onBytes: (b, rem) => {
          $("bar").style.width = Math.min(100, rem / 8 * 100) + "%";
          st.innerHTML = label + "<span class=ok>出声了</span> · 缓冲 " + rem.toFixed(1) + "s";
        }
      });
      if (ttft === null) ttft = part.ttft;
      wall += part.wall; dur += part.dur;
      m = { ttft, wall, dur, rtf: wall / (dur || 1), rem: part.rem };
    }
    setM(m);
    if (curChunks.length) {
      const total = curChunks.reduce((n, f) => n + f.length, 0);
      const ab = new ArrayBuffer(44 + total * 2), dv = new DataView(ab);
      const wr = (o, s) => { for (let i = 0; i < s.length; i++) dv.setUint8(o + i, s.charCodeAt(i)); };
      wr(0, "RIFF"); dv.setUint32(4, 36 + total * 2, true); wr(8, "WAVEfmt ");
      dv.setUint32(16, 16, true); dv.setUint16(20, 1, true); dv.setUint16(22, 1, true);
      dv.setUint32(24, SR, true); dv.setUint32(28, SR * 2, true); dv.setUint16(32, 2, true); dv.setUint16(34, 16, true);
      wr(36, "data"); dv.setUint32(40, total * 2, true);
      let off = 44;
      for (const f of curChunks) for (let i = 0; i < f.length; i++, off += 2)
        dv.setInt16(off, Math.max(-32768, Math.min(32767, Math.round(f[i] * 32768))), true);
      const url = URL.createObjectURL(new Blob([ab], { type: "audio/wav" }));
      $("au").src = url; $("wavdl").href = url;
      $("wavdl").download = "ming3-" + new Date().toISOString().slice(0, 19).replace(/[:T]/g, "") + ".wav";
      $("dlbox").style.display = "flex";
    }
    $("rp").disabled = curChunks.length === 0;
    $("stop").disabled = false;
    const actx = ac();
    clearInterval(ticker);
    ticker = setInterval(() => {
      const rem = Math.max(0, m.rem());
      if (m.dur > 0) $("bar").style.width = Math.min(100, (1 - rem / m.dur) * 100) + "%";
      st.innerHTML = rem > 0.1
        ? "<span class=ok>完成</span> · 播放中，剩余约 " + rem.toFixed(1) + "s"
        : "<span class=ok>播放完毕</span>";
      if (rem <= 0.1) { clearInterval(ticker); ticker = null; $("stop").disabled = true; }
    }, 250);
  } catch (e) {
    $("stop").disabled = true;
    if (e.partial) setM(e.partial);
    st.innerHTML = "<span class=hot>" + (e.name === "AbortError" ? "已停止" : "失败：" + e.message) + "</span>";
  } finally { btn.disabled = false; }
};
$("stop").onclick = () => {
  if (curAbort) curAbort.abort();
  stopAll();
  $("bar").style.width = "0";
  $("st").innerHTML = "<span class=hot>已停止</span>";
  $("stop").disabled = true;
};
$("rp").onclick = () => {
  if (!curChunks.length) return;
  stopAll();
  $("stop").disabled = false;
  const actx = ac();
  if (actx.state === "suspended") actx.resume();
  const total = curChunks.reduce((n, f) => n + f.length, 0);
  const b = actx.createBuffer(1, total, SR);
  let off = 0;
  for (const f of curChunks) { b.copyToChannel(f, 0, off); off += f.length; }
  const s = actx.createBufferSource(); s.buffer = b; s.connect(actx.destination);
  curSources.push(s); s.start();
  const t0 = actx.currentTime;
  const st = $("st");
  $("bar").style.width = "0";
  clearInterval(ticker);
  ticker = setInterval(() => {
    const el = actx.currentTime - t0;
    $("bar").style.width = Math.min(100, el / b.duration * 100) + "%";
    if (el >= b.duration - 0.1) { clearInterval(ticker); ticker = null; st.innerHTML = "<span class=ok>播放完毕</span>"; $("stop").disabled = true; }
  }, 250);
  st.innerHTML = "<span class=ok>整段重播</span>（单条连续音频流）";
};

const FOUR = [
  ["q-serena", "一号机位就绪，这是一段稍长的开场白，用来观察四路声音是否互相抢带宽。"],
  ["q-aiden", "第二路，男声。单机十路并发是这个模型的本事，现在只开四路，应该毫无压力。"],
  ["q-vivian", "第三路。如果这一路的第一个字比前两条晚很久才响，说明请求在排队。"],
  ["q-uncle_fu", "第四路，大叔音收尾。四个表格里，TTFT 应该都在四秒附近，墙钟不会翻倍。"],
];
$("go4").onclick = async () => {
  const btn = $("go4"), st4 = $("st4"), tb = $("t4");
  btn.disabled = true; st4.textContent = "四路同时发射…"; tb.innerHTML = "";
  const rows = FOUR.map(([v]) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>–</td><td>${v}</td><td>–</td><td>–</td><td>–</td><td>–</td><td>排队…</td>`;
    tb.appendChild(tr); return tr;
  });
  const t0 = performance.now();
  await Promise.all(FOUR.map(([v, t], i) => {
    let tr = null;
    return speak(t, v, {
      signal: null, collect: false,
      onTTFT: ttft => { rows[i].children[2].textContent = ttft.toFixed(2) + " s";
                        rows[i].children[6].innerHTML = "<span class=ok>出声</span>"; },
      onBytes: () => {}, onOpen: () => { rows[i].children[6].textContent = "已连接"; }
    }).then(m => {
      rows[i].children[0].textContent = i + 1;
      rows[i].children[3].textContent = m.wall.toFixed(2) + " s";
      rows[i].children[4].textContent = m.dur.toFixed(2) + " s";
      rows[i].children[5].textContent = m.rtf.toFixed(3);
      rows[i].children[6].innerHTML = "<span class=ok>完成</span>";
    }).catch(e => { rows[i].children[6].innerHTML = "<span class=hot>" + e.message.slice(0,30) + "</span>"; });
  }));
  st4.innerHTML = "整组墙钟 <span class=ok>" + ((performance.now() - t0) / 1000).toFixed(2) + " s</span>（四路并行，含播放等待）";
  btn.disabled = false;
};
</script>
</body>
</html>"""

html = HTML.replace("__VOICES__", json.dumps(voices_json, ensure_ascii=False))
open("ming-try.html", "w", encoding="utf-8").write(html)
import os
print("page bytes:", os.path.getsize("ming-try.html"))
