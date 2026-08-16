"""Visual system for the executive Streamlit dashboard."""

CSS = """
<style>
:root { --ink:#101828; --muted:#667085; --line:#e8ecf2; --surface:#fff; --canvas:#f7f9fc;
  --navy:#071a2b; --blue:#3157ff; --red:#e54444; --green:#0b9f75; --amber:#e79b28; }
.stApp { background:var(--canvas); color:var(--ink); }
.block-container { max-width:1540px; padding:1.15rem 2.6rem 5rem; }
#MainMenu, footer, header[data-testid="stHeader"] { visibility:hidden; height:0; }
.brand-shell { display:grid; grid-template-columns:155px minmax(420px,1fr) 330px; align-items:center;
  min-height:104px; padding:20px 26px; overflow:visible; background:linear-gradient(105deg,#071a2b,#0c2940);
  border-radius:22px; box-shadow:0 16px 38px rgba(7,26,43,.16); margin:4px 0 18px; }
.brand-shell > div:first-child { width:132px; height:64px; overflow:hidden; display:flex; align-items:center; }
.brand-logo { width:132px; height:auto; display:block; filter:invert(1); mix-blend-mode:screen; transform:scale(1.12); }
.brand-title { color:#fff; font-size:31px; line-height:1.18; font-weight:780; letter-spacing:-.8px; }
.brand-subtitle { color:#a9bfd0; font-size:13px; margin-top:7px; }
.status-grid { display:grid; grid-template-columns:110px 1fr; gap:5px 12px; font-size:12px; line-height:1.45; }
.status-grid .key { color:#7893a8; text-transform:uppercase; letter-spacing:.6px; }
.status-grid .value { color:#f4f8fb; font-weight:650; text-align:right; }
.status-ready { display:inline-block; width:7px; height:7px; margin-right:6px; background:#35d39a;
  border-radius:50%; box-shadow:0 0 0 4px rgba(53,211,154,.12); }
div[data-testid="stForm"] { background:#fff; border:1px solid var(--line); border-radius:18px;
  padding:14px 19px 5px; box-shadow:0 8px 25px rgba(16,24,40,.055); }
div[data-testid="stForm"] label { color:#475467; font-size:12px; font-weight:680; }
div[data-testid="stFormSubmitButton"] button { min-height:42px; margin-top:28px; background:var(--blue);
  color:#fff; border:0; border-radius:10px; font-weight:750; box-shadow:0 8px 18px rgba(49,87,255,.22); }
div[data-testid="stFormSubmitButton"] button:hover { background:#2449e5; color:#fff; transform:translateY(-1px); border:0; }
.section-kicker { color:var(--blue); font-size:11px; font-weight:800; letter-spacing:1.2px;
  text-transform:uppercase; margin-top:32px; }
.section-title { color:var(--ink); font-size:24px; line-height:1.25; font-weight:780;
  letter-spacing:-.45px; margin:5px 0 3px; }
.section-subtitle { color:var(--muted); font-size:13px; margin-bottom:16px; }
.metric-card { position:relative; overflow:hidden; background:#fff; border:1px solid var(--line);
  border-radius:18px; padding:21px 22px; min-height:128px; box-shadow:0 8px 24px rgba(16,24,40,.055); }
.metric-card:before { content:""; position:absolute; left:0; top:0; bottom:0; width:4px;
  background:var(--metric-accent,var(--blue)); }
.metric-value { color:var(--ink); font-size:39px; line-height:1.05; font-weight:820; letter-spacing:-1.4px; margin-top:5px; }
.metric-label { color:#667085; font-size:11px; font-weight:750; text-transform:uppercase;
  letter-spacing:.85px; margin-top:13px; }
.metric-note { color:#98a2b3; font-size:11px; margin-top:4px; }
div[data-testid="stPlotlyChart"] { background:#fff; border:1px solid var(--line); border-radius:18px;
  padding:9px 10px 2px; box-shadow:0 7px 22px rgba(16,24,40,.045); }
.ai-zone { margin-top:34px; padding:25px 26px 22px; border-radius:24px 24px 0 0;
  background:linear-gradient(112deg,#071a2b,#103751); color:#fff; }
.ai-kicker { color:#69ddbb; font-size:11px; font-weight:800; letter-spacing:1.35px; }
.ai-title { font-size:29px; line-height:1.2; font-weight:790; letter-spacing:-.6px; margin:6px 0; }
.ai-subtitle { color:#a9bfd0; font-size:13px; }
.overall-card { background:linear-gradient(115deg,#eef2ff,#f7fbff); border:1px solid #dce4ff;
  border-radius:0 0 20px 20px; padding:25px 28px; margin-bottom:14px; }
.overall-card h4 { color:#3157ff; font-size:12px; text-transform:uppercase; letter-spacing:1px; margin:0 0 11px; }
.overall-card p { color:#1d2939; font-size:17px; line-height:1.72; margin:0; font-weight:520; }
.intel-card { background:#fff; border:1px solid var(--line); border-radius:18px; padding:20px 22px;
  min-height:205px; box-shadow:0 7px 22px rgba(16,24,40,.045); }
.intel-card h4 { color:#344054; font-size:12px; text-transform:uppercase; letter-spacing:.8px; margin:0 0 16px; }
.intel-card ul { list-style:none; padding:0; margin:0; }
.intel-card li { color:#344054; font-size:14px; line-height:1.55; padding:8px 0 8px 17px;
  border-bottom:1px solid #f0f2f5; position:relative; }
.intel-card li:before { content:""; position:absolute; left:0; top:15px; width:6px; height:6px;
  border-radius:50%; background:var(--card-accent,var(--blue)); }
.intel-card li:last-child { border-bottom:0; }
.intel-card p { color:#98a2b3; font-size:13px; line-height:1.6; }
.intel-positive { --card-accent:var(--green); border-top:3px solid var(--green); }
.intel-negative { --card-accent:var(--red); border-top:3px solid var(--red); }
.intel-barrier { --card-accent:var(--amber); border-top:3px solid var(--amber); }
.marketing-card { background:#0b2235; border-radius:18px; padding:23px 25px; min-height:205px;
  box-shadow:0 12px 28px rgba(7,26,43,.13); }
.marketing-card h4 { color:#69ddbb; font-size:12px; letter-spacing:.9px; text-transform:uppercase; margin:0 0 15px; }
.marketing-card ul { list-style:none; margin:0; padding:0; }
.marketing-card li { color:#f2f7fa; font-size:14px; line-height:1.55; padding:8px 0 8px 21px; position:relative; }
.marketing-card li:before { content:"→"; position:absolute; left:0; color:#69ddbb; font-weight:800; }
.marketing-card p { color:#a9bfd0; }
.voc-card { border:1px solid var(--line); border-left:4px solid var(--blue); background:#fff;
  padding:20px 22px; border-radius:6px 16px 16px 6px; margin-bottom:11px; box-shadow:0 5px 16px rgba(16,24,40,.04); }
.voc-quote { color:#1d2939; font-size:17px; line-height:1.65; font-weight:550; }
.voc-meta { color:#7b8794; font-size:12px; margin-top:10px; }
.empty-shell { background:#fff; border:1px solid var(--line); border-radius:22px; text-align:center;
  padding:76px 25px; margin-top:20px; box-shadow:0 9px 28px rgba(16,24,40,.04); }
.empty-shell:before { content:"JP"; display:inline-grid; place-items:center; width:52px; height:52px;
  border-radius:15px; color:#fff; background:var(--blue); font-size:14px; font-weight:800; }
.empty-shell h2 { color:var(--ink); margin:18px 0 9px; font-size:28px; }
.empty-shell p { color:var(--muted); }
.coming-soon { background:#fff; border:1px solid var(--line); border-radius:18px;
  padding:55px; text-align:center; color:#7b8794; }
@media(max-width:1000px) { .block-container { padding:1rem 1.2rem 3rem; }
  .brand-shell { grid-template-columns:110px 1fr; min-height:110px; }
  .brand-title { font-size:25px; } .status-grid { display:none; } }
</style>
"""
