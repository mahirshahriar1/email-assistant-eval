"""Browser UI for the Email Generation Assistant.

A person enters Intent + Key Facts + Tone, picks a model, and gets a finished email.
Wired to the same generator (src/generate.py) used by the evaluation harness.

Features:
  * polished, responsive UI (Plus Jakarta Sans, teal/orange design system)
  * per-IP rate limiting (Flask-Limiter) to protect the shared Groq quota
  * client-side loading state + copy-to-clipboard

Run:
    python -m src.app
    # then open http://127.0.0.1:5000
"""
from flask import Flask, render_template_string, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from . import config, generate

app = Flask(__name__)

# --- Rate limiting --------------------------------------------------------------------
# Protects the shared Groq free-tier quota from a public endpoint. In-memory storage is
# fine for a single always-on process; point storage_uri at Redis for multi-instance.
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    storage_uri="memory://",
    default_limits=[],
)
GENERATE_LIMITS = "6 per minute;60 per day"

PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Email Generation Assistant</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --primary:#0D9488; --primary-dark:#0F766E; --cta:#F97316; --cta-dark:#EA580C;
      --bg:#F0FDFA; --bg2:#CCFBF1; --card:#ffffff; --ink:#134E4A; --muted:#5B7B77;
      --line:#D7E9E6; --ring:rgba(13,148,136,.30);
      --radius:16px; --shadow:0 12px 32px rgba(15,118,110,.12);
    }
    * { box-sizing:border-box; }
    html { font-size:18px; }
    body {
      margin:0; min-height:100vh; color:var(--ink);
      font-family:'Plus Jakarta Sans', system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background:linear-gradient(165deg,var(--bg) 0%, var(--bg2) 100%);
      padding:40px 24px; line-height:1.6;
    }
    .wrap { max-width:1180px; margin:0 auto; }
    header { display:flex; align-items:center; gap:14px; margin-bottom:6px; }
    .logo { width:46px; height:46px; border-radius:13px; background:var(--primary);
            display:grid; place-items:center; box-shadow:var(--shadow); flex:none; }
    .logo svg { width:26px; height:26px; stroke:#fff; }
    h1 { font-size:1.85rem; font-weight:800; margin:0; letter-spacing:-.02em; }
    .sub { color:var(--muted); margin:6px 0 28px; font-size:1rem; max-width:62ch; }
    .grid { display:grid; grid-template-columns:1fr 1fr; gap:26px; align-items:start; }
    @media (max-width:860px){ html{font-size:17px;} body{padding:24px 16px;} .grid{grid-template-columns:1fr;} }
    .card { background:var(--card); border:1px solid var(--line); border-radius:var(--radius);
            padding:30px; box-shadow:var(--shadow); }
    .card h2 { font-size:1.15rem; font-weight:700; margin:0 0 18px; display:flex; align-items:center; gap:9px; }
    label { display:block; font-weight:600; font-size:.92rem; margin:18px 0 7px; }
    label:first-of-type { margin-top:0; }
    .hint { font-weight:400; color:var(--muted); font-size:.82rem; }
    input[type=text], textarea, select {
      width:100%; padding:13px 15px; border:1.5px solid var(--line); border-radius:11px;
      font-size:1rem; font-family:inherit; color:var(--ink); background:#fff; transition:border-color .15s, box-shadow .15s;
    }
    input::placeholder, textarea::placeholder { color:#9DB6B2; }
    input:focus, textarea:focus, select:focus { outline:none; border-color:var(--primary); box-shadow:0 0 0 4px var(--ring); }
    textarea { resize:vertical; min-height:138px; line-height:1.55; }
    .row { display:flex; gap:16px; }
    .row > div { flex:1; }
    button { margin-top:24px; width:100%; background:var(--cta); color:#fff; border:0;
      padding:15px; border-radius:12px; font-size:1.05rem; font-weight:700; cursor:pointer;
      font-family:inherit; transition:background .18s; display:flex; align-items:center; justify-content:center; gap:10px; }
    button:hover { background:var(--cta-dark); }
    button:disabled { opacity:.75; cursor:progress; }
    .spinner { width:19px; height:19px; border:2.5px solid rgba(255,255,255,.45);
      border-top-color:#fff; border-radius:50%; animation:spin .7s linear infinite; display:none; }
    @keyframes spin { to { transform:rotate(360deg); } }
    .foot { color:var(--muted); font-size:.82rem; margin-top:16px; }
    code { background:var(--bg2); color:var(--primary-dark); padding:2px 7px; border-radius:6px; font-size:.85em; }
    .error { background:#FEF2F2; color:#B91C1C; border:1px solid #FECACA; padding:13px 15px;
      border-radius:11px; font-size:.92rem; margin-bottom:14px; }
    .result-head { display:flex; align-items:center; justify-content:space-between; margin-bottom:18px; }
    .result-head h2 { margin:0; }
    .copy { width:auto; margin:0; padding:8px 14px; font-size:.85rem; background:var(--primary);
      border-radius:9px; gap:7px; }
    .copy:hover { background:var(--primary-dark); }
    .copy svg { width:15px; height:15px; stroke:#fff; }
    .email { white-space:pre-wrap; background:#F7FCFB; border:1px solid var(--line); border-radius:12px;
      padding:22px; font-size:1rem; line-height:1.65; min-height:280px; color:var(--ink); }
    .empty { color:var(--muted); font-style:italic; display:flex; align-items:center; min-height:280px; }
    @media (prefers-reduced-motion:reduce){ .spinner{animation:none;} * {transition:none!important;} }
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <span class="logo" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>
        </svg>
      </span>
      <h1>Email Generation Assistant</h1>
    </header>
    <p class="sub">Give the intent, key facts, and tone &mdash; get a polished, professional email.
       Powered by role-play + few-shot + chain-of-thought prompting on Groq.</p>

    <form method="post" class="grid" id="genForm">
      <div class="card">
        <h2>Brief</h2>

        <label for="intent">Intent <span class="hint">&mdash; the purpose of the email</span></label>
        <input id="intent" type="text" name="intent" value="{{ form.intent }}"
               placeholder="Follow up after a sales meeting and propose next steps" required>

        <label for="key_facts">Key facts <span class="hint">&mdash; one per line; each must appear in the email</span></label>
        <textarea id="key_facts" name="key_facts" required
          placeholder="We met on Tuesday, June 9&#10;Discussed the Enterprise plan at $2,400/year&#10;Propose a call next Thursday at 2pm">{{ form.key_facts }}</textarea>

        <div class="row">
          <div>
            <label for="tone">Tone</label>
            <input id="tone" type="text" name="tone" value="{{ form.tone }}" placeholder="professional and friendly" required>
          </div>
          <div>
            <label for="model">Model</label>
            <select id="model" name="model">
              {% for m in models %}
                <option value="{{ m }}" {{ 'selected' if m == form.model else '' }}>{{ m }}</option>
              {% endfor %}
            </select>
          </div>
        </div>

        <button type="submit" id="genBtn">
          <span class="spinner" id="spin"></span>
          <span id="btnLabel">Generate email</span>
        </button>
        <p class="foot">Default <code>gpt-oss-120b</code> won the evaluation &mdash; see <code>report/REPORT.pdf</code>. Limit: 6/min.</p>
      </div>

      <div class="card">
        <div class="result-head">
          <h2>Generated email</h2>
          {% if email %}
          <button type="button" class="copy" id="copyBtn" onclick="copyEmail()">
            <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
            <span id="copyLabel">Copy</span>
          </button>
          {% endif %}
        </div>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        {% if email %}
          <div class="email" id="emailBox">{{ email }}</div>
        {% else %}
          <div class="empty">Your generated email will appear here.</div>
        {% endif %}
      </div>
    </form>
  </div>

  <script>
    // Loading state on submit (reserves no layout; just swaps button content).
    document.getElementById('genForm').addEventListener('submit', function () {
      document.getElementById('genBtn').disabled = true;
      document.getElementById('spin').style.display = 'inline-block';
      document.getElementById('btnLabel').textContent = 'Generating…';
    });
    function copyEmail() {
      const text = document.getElementById('emailBox').innerText;
      navigator.clipboard.writeText(text).then(function () {
        const l = document.getElementById('copyLabel');
        l.textContent = 'Copied!';
        setTimeout(function () { l.textContent = 'Copy'; }, 1600);
      });
    }
  </script>
</body>
</html>
"""

_DEFAULT_FORM = {"intent": "", "key_facts": "", "tone": "", "model": "gpt-oss-120b"}


@app.route("/", methods=["GET", "POST"])
@limiter.limit(GENERATE_LIMITS, exempt_when=lambda: request.method != "POST")
def index():
    form = dict(_DEFAULT_FORM)
    email = None
    error = None

    if request.method == "POST":
        form["intent"] = request.form.get("intent", "").strip()
        form["key_facts"] = request.form.get("key_facts", "").strip()
        form["tone"] = request.form.get("tone", "").strip()
        form["model"] = request.form.get("model", "gpt-oss-120b")
        facts = [ln.strip() for ln in form["key_facts"].splitlines() if ln.strip()]

        if not (form["intent"] and facts and form["tone"]):
            error = "Please provide an intent, at least one key fact, and a tone."
        elif form["model"] not in config.MODELS:
            error = "Unknown model selected."
        else:
            try:
                scenario = {"intent": form["intent"], "key_facts": facts, "tone": form["tone"]}
                # throttle=False: skip the batch rate-limit sleep for snappy interactive UX.
                email = generate.generate_email(scenario, config.MODELS[form["model"]], throttle=False)
            except Exception as e:  # surface API/key errors in the UI instead of a 500
                error = f"Generation failed: {e}"

    return render_template_string(PAGE, email=email, error=error, form=form,
                                  models=list(config.MODELS.keys()))


@app.errorhandler(429)
def rate_limited(_e):
    error = "You're going a bit fast - the limit is 6 generations per minute. Please wait a moment and try again."
    return render_template_string(PAGE, email=None, error=error, form=dict(_DEFAULT_FORM),
                                  models=list(config.MODELS.keys())), 429


def main():
    print("Email Generation Assistant -> http://127.0.0.1:5000  (Ctrl+C to stop)")
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
