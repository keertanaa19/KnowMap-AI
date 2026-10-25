"""
SemanticApp - Standalone Knowledge Mapping & Semantic Search Demo
Refactored and bug-fixed version of Knowledge_mapping_using_ai.py
"""

import csv
import io
import time
import os
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import numpy as np

app = Flask(__name__)
CORS(app)

# -------------------------
# Models & In-memory stores
# -------------------------
_nlp = None
_embed_model = None

def get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm")
        except Exception:
            _nlp = False
    return _nlp if _nlp is not False else None

def get_embed_model():
    global _embed_model
    if _embed_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            _embed_model = False
    return _embed_model if _embed_model is not False else None

semantic_search_data = []

STATS = {
    "files_uploaded": 0,
    "triples_total": 0,
    "unique_nodes": 0,
    "graphs_processed": 0,
    "processing_jobs": 0,
    "last_graph_time_ms": 0,
    "last_uploaded_file": None
}
FEEDBACK = {"ratings": []}

def recalc_node_counts():
    nodes = set()
    for t in semantic_search_data:
        if t.get("subject"):
            nodes.add(t.get("subject"))
        if t.get("object"):
            nodes.add(t.get("object"))
    STATS["unique_nodes"] = len(nodes)
    STATS["triples_total"] = len(semantic_search_data)

# processing daily counts (0=Mon .. 6=Sun)
PROCESSING_DAILY = {i: 0 for i in range(7)}
def bump_processing_count(n=1):
    wd = datetime.now(timezone.utc).weekday()
    PROCESSING_DAILY[wd] = PROCESSING_DAILY.get(wd, 0) + int(n)

# -------------------------
# Shared HTML snippets
# -------------------------
NAVBAR = """
<nav class="navbar navbar-expand-lg navbar-light bg-white shadow-sm mb-4">
  <div class="container-fluid">
    <a class="navbar-brand fw-bold text-primary" href="/upload_page">SemanticApp</a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navMenu">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse" id="navMenu">
      <ul class="navbar-nav me-auto mb-2 mb-lg-0">
        <li class="nav-item"><a class="nav-link" href="/upload_page">Upload / Manual</a></li>
        <li class="nav-item"><a class="nav-link" href="/">Semantic Search</a></li>
        <li class="nav-item"><a class="nav-link" href="/dashboard">Admin Dashboard</a></li>
      </ul>
      <span class="navbar-text small text-muted">Pipeline Monitor • Memory + AI</span>
    </div>
  </div>
</nav>
"""

BASE_HEAD = """
<!doctype html><html>
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SemanticApp</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<script src="https://unpkg.com/vis-network@9.1.2/dist/vis-network.min.js"></script>
<style>
body{background:#f6f7fb;font-family:Inter,system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
.card{border-radius:12px}
#graph{height:450px;background:#fff;border-radius:8px;padding:8px;border:1px solid #e6e9ef}
.progress{height:10px}
.star{cursor:pointer;font-size:20px;color:#ddd}
.star.selected{color:#ffbf00}
</style>
</head>
<body>
<div class="container my-3">
"""

BASE_FOOT = """
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body></html>
"""

SEMANTIC_HTML = BASE_HEAD + NAVBAR + r"""
<h4>Semantic Search & Graph</h4>
<div class="row g-3">
  <div class="col-lg-8">
    <div class="card p-3">
      <div class="d-flex gap-2 mb-2">
        <input id="query" class="form-control" placeholder="Search nodes or type a query...">
        <button id="searchBtn" class="btn btn-primary">Search</button>
      </div>
      <div id="graph"></div>
      <pre id="sentenceDisplay" class="mt-3" style="background:#fafafa;padding:10px;border-radius:6px"></pre>
    </div>
    <div class="card p-3 mt-3">
      <h6>Search Results</h6>
      <ul id="searchResults" class="list-group"></ul>
    </div>
  </div>

  <div class="col-lg-4">
    <div class="card p-3 mb-3">
      <h6>Reference</h6>
      <div class="mb-2">Last uploaded file: <strong id="lastUploadedFile">—</strong></div>
      <div class="mb-2">Files uploaded: <span id="filesUploaded">0</span></div>
      <div class="mb-2">Triples total: <span id="triplesTotal">0</span></div>
      <div class="mb-2">Unique nodes: <span id="uniqueNodes">0</span></div>
      <div class="mb-2">Graphs processed: <span id="graphsProcessed">0</span></div>
    </div>
  </div>
</div>

<script>
function drawGraph(triples){
  const container = document.getElementById('graph');
  if(!triples || triples.length===0){ container.innerHTML='<div class="text-muted p-3">No data</div>'; return; }
  const nodes=[], edges=[], ids=new Set();
  triples.forEach(t=>{
    const s=t.subject, o=t.object;
    if(!ids.has(s)){ nodes.push({id:s,label:s}); ids.add(s); }
    if(!ids.has(o)){ nodes.push({id:o,label:o}); ids.add(o); }
    edges.push({from:s,to:o,label:t.relation||''});
  });
  const data={nodes:new vis.DataSet(nodes), edges:new vis.DataSet(edges)};
  const options={nodes:{shape:'box',margin:8}, edges:{arrows:'to', smooth:true}, physics:{stabilization:true}};
  new vis.Network(container, data, options);
}

document.getElementById('searchBtn').addEventListener('click', async ()=>{
  const q = document.getElementById('query').value.trim(); if(!q) return;
  const res = await fetch('/search', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({query:q})});
  if(!res.ok){ alert('Search failed'); return; }
  const j = await res.json();
  drawGraph(j.triples || []);
  const list = document.getElementById('searchResults'); list.innerHTML='';
  (j.top_nodes||[]).forEach(n=>{
    const li = document.createElement('li'); li.className='list-group-item';
    li.textContent = n.name + ' (score: '+(n.score||0).toFixed(3)+')';
    li.addEventListener('click', async ()=>{
      const r = await fetch('/search_node', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({node:n.name})});
      const jj = await r.json();
      drawGraph(jj.triples || []);
    });
    list.appendChild(li);
  });
});

async function pollStats(){
  try{
    const r = await fetch('/stats'); const s = await r.json();
    document.getElementById('filesUploaded').textContent = s.files_uploaded;
    document.getElementById('triplesTotal').textContent = s.triples_total;
    document.getElementById('uniqueNodes').textContent = s.unique_nodes;
    document.getElementById('graphsProcessed').textContent = s.graphs_processed;
    document.getElementById('lastUploadedFile').textContent = s.last_uploaded_file || '—';
  }catch(e){}
}
pollStats();
</script>
""" + BASE_FOOT

DASHBOARD_HTML = BASE_HEAD + NAVBAR + r"""
<h4>Admin Dashboard</h4>
<div class="row g-3">
  <div class="col-lg-4">
    <div class="card p-3">
      <h6>Pipeline Metrics</h6>
      <div class="mb-1">Files uploaded: <span id="filesUploaded">0</span></div>
      <div class="mb-1">Triples total: <span id="triplesTotal">0</span></div>
      <div class="mb-1">Unique nodes: <span id="uniqueNodes">0</span></div>
      <div class="mb-1">Graphs processed: <span id="graphsProcessed">0</span></div>
      <div class="mb-1">Active jobs: <span id="processingJobs">0</span></div>
      <div class="mb-1">Last graph time: <span id="lastGraphTime">0</span> ms</div>
      <div class="mb-1">Last uploaded file: <strong id="lastUploadedFile">—</strong></div>
    </div>

    <div class="card p-3 mt-3">
      <h6>Feedback (rate relevance)</h6>
      <div id="stars" class="mb-2">
        <span class="star" data-val="1">&#9733;</span><span class="star" data-val="2">&#9733;</span><span class="star" data-val="3">&#9733;</span><span class="star" data-val="4">&#9733;</span><span class="star" data-val="5">&#9733;</span>
      </div>
      <button id="sendFeedback" class="btn btn-outline-primary w-100">Send Rating</button>
      <div class="mt-2 small text-muted">Average rating: <span id="avgRating">—</span></div>
    </div>
  </div>

  <div class="col-lg-8">
    <div class="card p-3 mb-3">
      <h6>Processing Pipeline Performance</h6>
      <canvas id="pipelineChart" height="140"></canvas>
    </div>

    <div class="card p-3 mt-3">
      <h6>Logs / Recent Triples (top 20)</h6>
      <pre id="triplesPreview" style="height:140px;overflow:auto;background:#fafafa;padding:10px;border-radius:6px"></pre>
    </div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
let selectedRating = 0;
document.querySelectorAll('.star').forEach(s=>{
  s.addEventListener('click', ()=> {
    selectedRating = parseInt(s.getAttribute('data-val'));
    document.querySelectorAll('.star').forEach(x=> x.classList.toggle('selected', parseInt(x.getAttribute('data-val')) <= selectedRating));
  });
});
document.getElementById('sendFeedback').addEventListener('click', async ()=>{
  if(selectedRating < 1) return alert('Pick 1-5');
  await fetch('/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rating:selectedRating})});
  selectedRating = 0; document.querySelectorAll('.star').forEach(x=> x.classList.remove('selected')); pollStats();
});

async function loadPreview(){
  try{
    const r = await fetch('/stats'); const s = await r.json();
    document.getElementById('filesUploaded').textContent = s.files_uploaded;
    document.getElementById('triplesTotal').textContent = s.triples_total;
    document.getElementById('uniqueNodes').textContent = s.unique_nodes;
    document.getElementById('graphsProcessed').textContent = s.graphs_processed;
    document.getElementById('processingJobs').textContent = s.processing_jobs;
    document.getElementById('lastGraphTime').textContent = s.last_graph_time_ms;
    document.getElementById('lastUploadedFile').textContent = s.last_uploaded_file || '—';
    document.getElementById('avgRating').textContent = s.avg_rating !== null ? s.avg_rating.toFixed(2) : '—';
  }catch(e){}
  try{
    const t = await fetch('/recent_triples'); const j = await t.json();
    document.getElementById('triplesPreview').textContent = (j.triples || []).map(x => `${x.subject} ${x.relation} ${x.object}`).join('\n');
  }catch(e){}
  loadMetricsAndDraw();
}

let pipelineChart = null;
async function loadMetricsAndDraw(){
  try{
    const r = await fetch('/metrics');
    if(!r.ok) return;
    const j = await r.json();
    const labels = j.labels || ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
    const counts = j.counts || [0,0,0,0,0,0,0];
    const canvas = document.getElementById('pipelineChart');
    const ctx = canvas.getContext('2d');

    const data = {
      labels: labels,
      datasets: [{
        label: 'Processed items',
        data: counts,
        fill: true,
        backgroundColor: 'rgba(136, 78, 255, 0.2)',
        borderColor: 'rgba(124,58,237,0.95)',
        tension: 0.35
      }]
    };

    if(pipelineChart){
      pipelineChart.data.datasets[0].data = counts;
      pipelineChart.update();
    } else {
      pipelineChart = new Chart(ctx, { type: 'line', data: data, options: { responsive: true, scales: { y: { beginAtZero: true } } } });
    }
  } catch(e){}
}
loadPreview();
setInterval(loadPreview, 10000);
</script>
""" + BASE_FOOT

UPLOAD_HTML = BASE_HEAD + NAVBAR + r"""
<h4>Upload CSV & Manual Graph</h4>
<div class="row g-3">
  <div class="col-lg-6">
    <div class="card p-3">
      <h6>Upload CSV (subject,relation,object)</h6>
      <input type="file" id="csvFile" class="form-control mb-2" accept=".csv">
      <div class="progress mb-2"><div id="uploadProgress" class="progress-bar" style="width:0%"></div></div>
      <button id="uploadBtn" class="btn btn-primary w-100">Upload CSV</button>
    </div>

    <div class="card p-3 mt-3">
      <h6>Manual Text → Graph</h6>
      <textarea id="sentence" rows="5" class="form-control">Albert Einstein developed the theory of relativity in 1905.</textarea>
      <button id="analyzeBtn" class="btn btn-success mt-2 w-100">Analyze</button>
    </div>
  </div>

  <div class="col-lg-6">
    <div class="card p-3">
      <h6>Graph Preview</h6>
      <div id="graph"></div>
    </div>

    <div class="card p-3 mt-3">
      <h6>Stats</h6>
      <div>Files uploaded: <span id="filesUploaded">0</span></div>
      <div>Triples total: <span id="triplesTotal">0</span></div>
      <div>Unique nodes: <span id="uniqueNodes">0</span></div>
      <div>Last uploaded file: <strong id="lastUploadedFile">—</strong></div>
    </div>
  </div>
</div>

<script>
document.getElementById('uploadBtn').addEventListener('click', ()=>{
  const fileInput = document.getElementById('csvFile');
  if(!fileInput.files[0]) return alert('Choose CSV');
  const file = fileInput.files[0];
  const xhr = new XMLHttpRequest();
  xhr.open('POST','/upload',true);
  xhr.upload.onprogress = (e)=> {
    if(e.lengthComputable) {
      const pct = Math.round((e.loaded / e.total) * 100);
      document.getElementById('uploadProgress').style.width = pct + '%';
    }
  };
  xhr.onload = async function(){
    document.getElementById('uploadProgress').style.width = '0%';
    if(xhr.status===200){
      alert('Uploaded and processed');
      const t = await fetch('/recent_triples'); const j = await t.json();
      drawGraph(j.triples || []);
    } else {
      alert('Upload failed: ' + xhr.responseText);
    }
  };
  const fd = new FormData(); fd.append('file', file); xhr.send(fd);
});

document.getElementById('analyzeBtn').addEventListener('click', async ()=>{
  const text = document.getElementById('sentence').value.trim(); if(!text) return;
  const res = await fetch('/analyze', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text})});
  if(!res.ok){ alert('Analyze failed'); return; }
  const j = await res.json();
  drawGraph(j.triples || []);
});

function drawGraph(triples){
  const container = document.getElementById('graph');
  if(!triples || triples.length===0){ container.innerHTML='<div class="text-muted p-3">No data</div>'; return; }
  const nodes=[], edges=[], ids=new Set();
  triples.forEach(t=>{
    const s=t.subject, o=t.object;
    if(!ids.has(s)){ nodes.push({id:s,label:s}); ids.add(s); }
    if(!ids.has(o)){ nodes.push({id:o,label:o}); ids.add(o); }
    edges.push({from:s,to:o,label:t.relation||''});
  });
  const data={nodes:new vis.DataSet(nodes), edges:new vis.DataSet(edges)};
  const options={nodes:{shape:'box',margin:8}, edges:{arrows:'to', smooth:true}, physics:{stabilization:true}};
  new vis.Network(container, data, options);
}
</script>
""" + BASE_FOOT


# -------------------------
# Routes
# -------------------------
@app.route("/")
def semantic_page():
    return render_template_string(SEMANTIC_HTML)

@app.route("/dashboard")
def dashboard_page():
    return render_template_string(DASHBOARD_HTML)

@app.route("/upload_page")
def upload_page():
    return render_template_string(UPLOAD_HTML)

@app.route("/stats", methods=["GET"])
def get_stats():
    avg = None
    if FEEDBACK["ratings"]:
        avg = sum(FEEDBACK["ratings"]) / len(FEEDBACK["ratings"])
    out = dict(STATS)
    out["avg_rating"] = avg
    return jsonify(out)

@app.route("/recent_triples", methods=["GET"])
def recent_triples():
    return jsonify({"triples": semantic_search_data[-50:]})

@app.route("/metrics", methods=["GET"])
def metrics():
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    counts = [PROCESSING_DAILY.get(i, 0) for i in range(7)]
    return jsonify({"labels": labels, "counts": counts})

@app.route("/feedback", methods=["POST"])
def feedback():
    data = request.json or {}
    try:
        rating = int(data.get("rating"))
    except Exception:
        return jsonify({"error":"invalid rating"}), 400
    if rating < 1 or rating > 5:
        return jsonify({"error":"rating must be 1..5"}), 400
    FEEDBACK["ratings"].append(rating)
    return jsonify({"status":"ok"})

@app.route("/analyze", methods=["POST"])
def analyze_text():
    data = request.json or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"triples": []}), 400
    STATS["processing_jobs"] += 1
    t0 = time.time()

    triples = []
    nlp = get_nlp()
    if nlp is not None:
        doc = nlp(text)
        for sent in doc.sents:
            subjects = [tok for tok in sent if tok.dep_ in ("nsubj", "nsubjpass")]
            objects = [tok for tok in sent if tok.dep_ in ("dobj", "pobj", "attr")]
            verb = sent.root.lemma_ if sent.root.pos_ in ("VERB", "AUX") else "relates_to"
            if subjects and objects:
                triples.append({"subject": subjects[0].text, "relation": verb, "object": objects[0].text})
            elif len(doc.noun_chunks) >= 2:
                chunks = list(doc.noun_chunks)
                triples.append({"subject": chunks[0].text, "relation": verb, "object": chunks[1].text})
    else:
        words = text.split()
        if len(words) >= 3:
            triples.append({"subject": words[0], "relation": "related_to", "object": " ".join(words[1:])})

    added = 0
    for t in triples:
        if not any((x["subject"], x["relation"], x["object"]) == (t["subject"], t["relation"], t["object"]) for x in semantic_search_data):
            semantic_search_data.append(t)
            added += 1

    recalc_node_counts()
    STATS["graphs_processed"] += 1
    bump_processing_count(max(1, added))
    t1 = time.time()
    STATS["last_graph_time_ms"] = int((t1 - t0) * 1000)
    STATS["processing_jobs"] = max(0, STATS["processing_jobs"] - 1)
    return jsonify({"triples": triples, "added": added})

@app.route("/upload", methods=["POST"])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error":"no file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error":"no selected file"}), 400
    STATS["processing_jobs"] += 1
    try:
        filename = file.filename
        stream = io.StringIO(file.stream.read().decode("utf8", errors="replace"), newline=None)
        reader = csv.reader(stream)
        header = next(reader, None)
        added = 0

        # Process first row if not header
        if header and len(header) >= 3 and header[0].strip().lower() != "subject":
            subj, rel, obj = header[0].strip(), header[1].strip(), header[2].strip()
            if not any((x["subject"], x["relation"], x["object"]) == (subj, rel, obj) for x in semantic_search_data):
                semantic_search_data.append({"subject": subj, "relation": rel, "object": obj})
                added += 1

        for row in reader:
            if len(row) < 3: continue
            subj, rel, obj = row[0].strip(), row[1].strip(), row[2].strip()
            if subj.lower() == "subject": continue
            triple = {"subject": subj, "relation": rel, "object": obj}
            if not any((x["subject"], x["relation"], x["object"]) == (subj, rel, obj) for x in semantic_search_data):
                semantic_search_data.append(triple)
                added += 1

        STATS["files_uploaded"] += 1
        STATS["last_uploaded_file"] = filename
        bump_processing_count(added)
        recalc_node_counts()
        STATS["processing_jobs"] = max(0, STATS["processing_jobs"] - 1)
        return jsonify({"triples_added": added, "triples_total": len(semantic_search_data)})
    except Exception as e:
        STATS["processing_jobs"] = max(0, STATS["processing_jobs"] - 1)
        return jsonify({"error": str(e)}), 500

@app.route("/search", methods=["POST"])
def semantic_search():
    data = request.json or {}
    query = (data.get("query") or "").strip()
    if not query: return jsonify({"triples": []}), 400
    nodes = list({t["subject"] for t in semantic_search_data} | {t["object"] for t in semantic_search_data})
    if not nodes: return jsonify({"triples": []}), 404

    model = get_embed_model()
    if model is not None:
        node_embs = model.encode(nodes, convert_to_numpy=True)
        query_emb = model.encode([query], convert_to_numpy=True)
        from sklearn.metrics.pairwise import cosine_similarity
        scores = cosine_similarity(query_emb, node_embs)[0]
        top_k = min(10, len(nodes))
        top_idx = np.argsort(scores)[::-1][:top_k]
        top_nodes = [nodes[i] for i in top_idx]
        top_scores = [float(scores[i]) for i in top_idx]
    else:
        top_nodes = [n for n in nodes if query.lower() in n.lower()][:10] or nodes[:10]
        top_scores = [1.0] * len(top_nodes)

    matched_triples = [t for t in semantic_search_data if t["subject"] in top_nodes or t["object"] in top_nodes]
    return jsonify({"top_nodes":[{"name":n,"score":s} for n,s in zip(top_nodes,top_scores)], "triples": matched_triples})

@app.route("/search_node", methods=["POST"])
def search_node():
    data = request.json or {}
    node = (data.get("node") or "").strip()
    if not node: return jsonify({"triples": [], "sentences": []}), 400
    matched_triples = [t for t in semantic_search_data if t['subject'] == node or t['object'] == node]
    sentences = [f"{t['subject']} {t['relation']} {t['object']}" for t in matched_triples]
    return jsonify({"triples": matched_triples, "sentences": sentences})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
