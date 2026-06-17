"""Browser UI for the Email Generation Assistant.

A person enters Intent + Key Facts + Tone, picks a model, and gets a finished email.
Wired to the same generator (src/generate.py) used by the evaluation harness.

Run:
    python -m src.app
    # then open http://127.0.0.1:5000
"""
from flask import Flask, render_template_string, request

from . import config, generate

app = Flask(__name__)

PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Email Generation Assistant</title>
  <style>
    :root { --bg:#0f172a; --card:#ffffff; --ink:#0f172a; --muted:#64748b; --accent:#2563eb; --line:#e2e8f0; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
           background: linear-gradient(160deg,#0f172a,#1e293b); color: var(--ink); min-height:100vh; padding:32px 16px; }
    .wrap { max-width: 880px; margin: 0 auto; }
    h1 { color:#fff; font-size: 26px; margin:0 0 4px; }
    .sub { color:#94a3b8; margin:0 0 24px; font-size:14px; }
    .grid { display:grid; grid-template-columns: 1fr 1fr; gap:20px; }
    @media (max-width: 760px){ .grid { grid-template-columns: 1fr; } }
    .card { background: var(--card); border-radius:14px; padding:22px; box-shadow:0 10px 30px rgba(0,0,0,.25); }
    label { display:block; font-weight:600; font-size:13px; margin:14px 0 6px; }
    label:first-of-type { margin-top:0; }
    .hint { font-weight:400; color:var(--muted); font-size:12px; }
    input[type=text], textarea, select {
      width:100%; padding:10px 12px; border:1px solid var(--line); border-radius:9px; font-size:14px; font-family:inherit; }
    textarea { resize:vertical; min-height:120px; }
    .row { display:flex; gap:12px; }
    .row > div { flex:1; }
    button { margin-top:18px; width:100%; background:var(--accent); color:#fff; border:0; padding:12px;
             border-radius:9px; font-size:15px; font-weight:600; cursor:pointer; }
    button:hover { background:#1d4ed8; }
    .error { background:#fef2f2; color:#b91c1c; border:1px solid #fecaca; padding:10px 12px; border-radius:9px; font-size:13px; margin-bottom:8px; }
    .result h2 { font-size:15px; margin:0 0 10px; color:var(--ink); }
    .email { white-space:pre-wrap; background:#f8fafc; border:1px solid var(--line); border-radius:9px;
             padding:16px; font-size:14px; line-height:1.5; min-height:200px; }
    .empty { color:var(--muted); font-style:italic; }
    .foot { color:#64748b; font-size:12px; margin-top:14px; }
    code { background:#1e293b; color:#cbd5e1; padding:1px 6px; border-radius:5px; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>✉️ Email Generation Assistant</h1>
    <p class="sub">Give the intent, key facts, and tone — get a professional email. Role-play + few-shot + chain-of-thought prompting, on Groq.</p>
    <form method="post" class="grid">
      <div class="card">
        <label>Intent <span class="hint">— the purpose of the email</span></label>
        <input type="text" name="intent" value="{{ form.intent }}" placeholder="Follow up after a sales meeting and propose next steps" required>

        <label>Key facts <span class="hint">— one per line; each must appear in the email</span></label>
        <textarea name="key_facts" placeholder="We met on Tuesday, June 9&#10;Discussed the Enterprise plan at $2,400/year&#10;Propose a call next Thursday at 2pm" required>{{ form.key_facts }}</textarea>

        <div class="row">
          <div>
            <label>Tone</label>
            <input type="text" name="tone" value="{{ form.tone }}" placeholder="professional and friendly" required>
          </div>
          <div>
            <label>Model</label>
            <select name="model">
              {% for m in models %}
                <option value="{{ m }}" {{ 'selected' if m == form.model else '' }}>{{ m }}</option>
              {% endfor %}
            </select>
          </div>
        </div>

        <button type="submit">Generate email</button>
        <p class="foot">Default model <code>gpt-oss-120b</code> won the evaluation. See <code>report/REPORT.pdf</code>.</p>
      </div>

      <div class="card result">
        <h2>Generated email</h2>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        {% if email %}
          <div class="email">{{ email }}</div>
        {% else %}
          <div class="email empty">Your generated email will appear here.</div>
        {% endif %}
      </div>
    </form>
  </div>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    form = {"intent": "", "key_facts": "", "tone": "", "model": "gpt-oss-120b"}
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
                email = generate.generate_email(scenario, config.MODELS[form["model"]])
            except Exception as e:  # surface API/key errors in the UI rather than a 500
                error = f"Generation failed: {e}"

    return render_template_string(PAGE, email=email, error=error, form=form,
                                  models=list(config.MODELS.keys()))


def main():
    print("Email Generation Assistant -> http://127.0.0.1:5000  (Ctrl+C to stop)")
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
