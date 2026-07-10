"""Streamlit frontend for TradeOps AI."""

import json

import httpx
import streamlit as st

API_BASE = "http://localhost:8000"

# Wells Fargo brand colours
WF_RED    = "#D71E28"
WF_GOLD   = "#FFCD11"
WF_DARK   = "#1A1A1A"
WF_GRAY   = "#767676"
WF_BORDER = "#D4D4D4"
WF_BG     = "#F7F7F7"

st.set_page_config(
    page_title="TradeOps AI",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;600;700&display=swap');

html, body, [class*="css"] {{
    font-family: 'Source Sans 3', sans-serif;
}}

/* ── Hide default Streamlit header ── */
[data-testid="stHeader"] {{ display: none !important; }}

/* ── Fixed navbar ── */
.wf-navbar {{
    position: fixed;
    top: 0; left: 0; right: 0;
    height: 54px;
    background: {WF_RED};
    display: flex;
    align-items: center;
    padding: 0 28px;
    z-index: 999999;
    box-shadow: 0 2px 8px rgba(0,0,0,0.18);
    gap: 0;
}}
.wf-navbar-brand {{
    font-size: 1.1rem;
    font-weight: 700;
    color: #FFFFFF;
    letter-spacing: -0.01em;
    line-height: 1;
}}
.wf-navbar-divider {{
    width: 1px;
    height: 22px;
    background: rgba(255,255,255,0.3);
    margin: 0 16px;
}}
.wf-navbar-sub {{
    font-size: 0.78rem;
    color: rgba(255,255,255,0.75);
    font-weight: 400;
    letter-spacing: 0.02em;
}}
.wf-navbar-badge {{
    margin-left: auto;
    background: rgba(255,255,255,0.15);
    border: 1px solid rgba(255,255,255,0.3);
    color: #FFFFFF;
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    padding: 3px 10px;
    border-radius: 3px;
}}

/* ── Push all content below navbar ── */
[data-testid="stAppViewContainer"] {{
    padding-top: 54px !important;
    background: #FFFFFF;
}}
[data-testid="stMain"] {{ background: #FFFFFF; }}
[data-testid="stSidebar"] {{
    padding-top: 54px !important;
    background: #FFFFFF !important;
    border-right: 1px solid {WF_BORDER} !important;
}}

/* ── Dividers ── */
hr {{ border-color: {WF_BORDER} !important; margin: 0.6rem 0 !important; }}

/* ── Sidebar table ── */
[data-testid="stSidebar"] table {{ border-collapse: collapse; width: 100%; }}
[data-testid="stSidebar"] th {{
    color: {WF_GRAY} !important;
    font-size: 0.68rem !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 5px 8px !important;
    border-bottom: 2px solid {WF_RED} !important;
    background: transparent !important;
}}
[data-testid="stSidebar"] td {{
    color: {WF_DARK} !important;
    font-size: 0.83rem !important;
    padding: 5px 8px !important;
    border-bottom: 1px solid #EBEBEB !important;
    background: transparent !important;
}}

/* ── Headings ── */
h2 {{
    color: {WF_DARK} !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em;
    border-bottom: 3px solid {WF_RED};
    padding-bottom: 8px;
    margin-bottom: 16px !important;
}}
h3 {{ color: {WF_DARK} !important; font-weight: 600 !important; }}
h4 {{
    color: {WF_GRAY} !important;
    font-size: 0.68rem !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 6px !important;
}}

/* ── Primary button ── */
.stButton button[kind="primary"] {{
    background: {WF_RED} !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 3px !important;
    font-weight: 700 !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.04em;
    padding: 0.6rem 1rem !important;
    transition: background 0.15s;
}}
.stButton button[kind="primary"]:hover {{
    background: #B01820 !important;
}}
.stButton button:disabled {{
    background: #E8E8E8 !important;
    color: #AAAAAA !important;
}}

/* ── Selectbox label ── */
[data-testid="stSelectbox"] label {{
    color: {WF_GRAY} !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}}

/* ── Alert / info boxes ── */
[data-testid="stAlert"] {{
    border-radius: 3px !important;
    border-left-width: 4px !important;
}}

/* ── Caption ── */
.stCaption {{ color: {WF_GRAY} !important; }}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def fetch_trades() -> list[dict]:
    try:
        r = httpx.get(f"{API_BASE}/trades", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Could not reach the API server: {e}")
        return []


def _render_thought_log(thoughts: list[dict], done: bool = False) -> None:
    TOOL_ICONS = {
        "get_trade_details":  "📋",
        "get_execution_logs": "📜",
        "search_policies":    "🔍",
    }
    rows = ""
    i = 0
    while i < len(thoughts):
        t = thoughts[i]

        if t["type"] == "tool_call":
            icon = TOOL_ICONS.get(t["tool"], "🔧")
            arg_val = str(next(iter(t["args"].values()), "")) if t["args"] else ""
            arg_display = f'("{arg_val[:45]}{"…" if len(arg_val) > 45 else ""}")' if arg_val else "()"
            # look ahead: pair with the immediately following tool_result if present
            if i + 1 < len(thoughts) and thoughts[i + 1]["type"] == "tool_result":
                first = thoughts[i + 1]["preview"].split("\n")[0].strip()
                preview = first[:85] + ("…" if len(first) > 85 else "")
                result_row = (
                    f'<div style="margin:2px 0 9px 26px;color:#16A34A;font-size:0.75rem">'
                    f'✓ {preview}</div>'
                )
                i += 2
            else:
                result_row = (
                    f'<div style="margin:2px 0 9px 26px;color:#D97706;font-size:0.75rem">'
                    f'⟳ running…</div>'
                )
                i += 1
            rows += (
                f'<div style="display:flex;gap:8px;align-items:flex-start;margin-bottom:2px">'
                f'<span style="line-height:1.5">{icon}</span>'
                f'<span>'
                f'<code style="background:#E8E8E8;padding:1px 7px;border-radius:3px;'
                f'font-size:0.78rem;color:#1A1A1A">{t["tool"]}</code>'
                f'<span style="color:#767676;font-size:0.77rem"> {arg_display}</span>'
                f'</span></div>'
                + result_row
            )

        elif t["type"] == "tool_result":
            # only reached when not consumed by the lookahead above (parallel calls)
            first = t["preview"].split("\n")[0].strip()
            preview = first[:85] + ("…" if len(first) > 85 else "")
            rows += (
                f'<div style="margin:2px 0 9px 26px;color:#16A34A;font-size:0.75rem">'
                f'✓ {preview}</div>'
            )
            i += 1

        elif t["type"] == "writing_report":
            rows += (
                f'<div style="color:#767676;font-size:0.8rem;margin:4px 0">'
                f'📝 Writing investigation report…</div>'
            )
            i += 1

        else:
            i += 1

    footer = (
        '<div style="color:#16A34A;font-weight:600;font-size:0.8rem;margin-top:6px">'
        '✅ Investigation complete</div>'
        if done else
        '<div style="color:#D97706;font-size:0.75rem;margin-top:6px">⟳  Processing…</div>'
    )

    st.markdown(
        f'<div style="background:#F7F7F7;border:1px solid {WF_BORDER};border-radius:4px;'
        f'padding:14px 18px;font-family:monospace">'
        f'<div style="font-size:0.65rem;font-weight:700;color:{WF_GRAY};letter-spacing:0.1em;'
        f'text-transform:uppercase;margin-bottom:12px;padding-bottom:8px;'
        f'border-bottom:1px solid #E8E8E8">⚡ Agent Reasoning</div>'
        f'{rows}{footer}</div>',
        unsafe_allow_html=True,
    )


def status_badge(status: str) -> str:
    styles = {
        "FAILED":  (f"background:#FEE2E2;color:#991B1B;border:1px solid #FECACA", "FAILED"),
        "SETTLED": (f"background:#DCFCE7;color:#166534;border:1px solid #BBF7D0", "SETTLED"),
        "PENDING": (f"background:#FEF3C7;color:#92400E;border:1px solid #FDE68A", "PENDING"),
    }
    style, label = styles.get(status, (f"background:#F3F4F6;color:#374151;border:1px solid #D1D5DB", status))
    return (
        f'<span style="{style};padding:2px 10px;border-radius:3px;'
        f'font-size:0.68rem;font-weight:700;letter-spacing:0.07em">{label}</span>'
    )


def confidence_bar(score: float) -> None:
    pct = int(score * 100)
    if score >= 0.8:
        colour, label = "#16A34A", "HIGH CONFIDENCE"
    elif score >= 0.6:
        colour, label = "#D97706", "MEDIUM CONFIDENCE"
    else:
        colour, label = WF_RED,   "LOW CONFIDENCE"

    st.markdown(
        f"""
        <div style="margin:6px 0 20px 0">
          <div style="display:flex;align-items:center;gap:16px">
            <div style="flex:1;background:#F0F0F0;border:1px solid {WF_BORDER};
                        border-radius:2px;height:12px;overflow:hidden">
              <div style="width:{pct}%;background:{colour};height:100%"></div>
            </div>
            <div style="display:flex;align-items:baseline;gap:8px;min-width:180px">
              <span style="font-size:1.6rem;font-weight:700;color:{colour};
                           font-family:monospace;letter-spacing:-0.02em">{pct}%</span>
              <span style="font-size:0.65rem;font-weight:700;color:{WF_GRAY};
                           letter-spacing:0.08em">{label}</span>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def info_card(text: str, accent: str, index: int) -> str:
    return f"""
    <div style="background:#FFFFFF;color:{WF_DARK};border:1px solid {WF_BORDER};
                border-left:4px solid {accent};padding:12px 16px;margin-bottom:8px;
                border-radius:0 3px 3px 0;font-size:0.87rem;line-height:1.55;
                box-shadow:0 1px 3px rgba(0,0,0,0.06)">
      <span style="color:{accent};font-weight:700;font-size:0.7rem;
                   letter-spacing:0.08em;margin-right:10px">{str(index).zfill(2)}</span>{text}
    </div>
    """


# ── Navbar (rendered once, fixed position) ────────────────────────────────────

st.markdown(
    f'<div class="wf-navbar">'
    f'<span class="wf-navbar-brand">TradeOps AI</span>'
    f'<div class="wf-navbar-divider"></div>'
    f'<span class="wf-navbar-sub">Failed Trade Investigation System</span>'
    f'<span class="wf-navbar-badge">INTERNAL USE ONLY</span>'
    f'</div>',
    unsafe_allow_html=True,
)

# ── Sidebar — trade browser ───────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        f'<div style="padding:4px 0 8px 0">'
        f'<span style="font-size:0.75rem;color:{WF_GRAY};font-weight:600;'
        f'text-transform:uppercase;letter-spacing:0.06em">Trade Browser</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    trades = fetch_trades()
    if not trades:
        st.stop()

    status_filter = st.selectbox("Filter by status", ["All", "FAILED", "SETTLED", "PENDING"])
    filtered = trades if status_filter == "All" else [t for t in trades if t["status"] == status_filter]

    if not filtered:
        st.info("No trades match this filter.")
        st.stop()

    options = [f"{t['trade_id']}  ·  {t['instrument']}  ·  {t['status']}" for t in filtered]
    choice = st.selectbox("Select a trade", options, label_visibility="collapsed")
    selected_id = choice.split("  ·  ")[0].strip()
    trade = next(t for t in filtered if t["trade_id"] == selected_id)

    st.divider()

    st.markdown(
        f'<div style="margin-bottom:10px">'
        f'<span style="font-size:0.95rem;font-weight:700;color:{WF_DARK};'
        f'font-family:monospace;letter-spacing:0.03em">{trade["trade_id"]}</span>'
        f'&nbsp;&nbsp;{status_badge(trade["status"])}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        | Field | Value |
        |---|---|
        | Instrument | {trade['instrument']} ({trade['instrument_type']}) |
        | Notional | {trade['notional_value']:,.0f} {trade['currency']} |
        | Counterparty | {trade['counterparty']} |
        | Trade Date | {trade['trade_date']} |
        | Failure Reason | {trade['failure_reason'] or '—'} |
        """
    )

    st.divider()

    investigate_btn = st.button(
        "Run Investigation",
        type="primary",
        use_container_width=True,
        disabled=(trade["status"] != "FAILED"),
        help="Only available for FAILED trades" if trade["status"] != "FAILED" else "",
    )
    if trade["status"] != "FAILED":
        st.caption(f"Status is {trade['status']} — no investigation required.")


# ── Main area ─────────────────────────────────────────────────────────────────

st.markdown('<h2>Investigation Report</h2>', unsafe_allow_html=True)

if investigate_btn:
    st.session_state.pop("result", None)
    tid = trade["trade_id"]

    st.markdown(
        f'<div style="font-size:0.8rem;color:{WF_GRAY};margin-bottom:10px">'
        f'Investigating <strong style="color:{WF_DARK};font-family:monospace">{tid}</strong>'
        f'&nbsp;— watch the agent gather evidence in real time</div>',
        unsafe_allow_html=True,
    )
    log_placeholder = st.empty()
    thoughts: list[dict] = []
    final_report = None

    try:
        with httpx.Client() as client:
            with client.stream(
                "POST",
                f"{API_BASE}/investigate/{tid}/stream",
                timeout=180,
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line.strip():
                        continue
                    event = json.loads(line)

                    if event["type"] in ("tool_call", "tool_result", "writing_report"):
                        thoughts.append(event)
                        with log_placeholder.container():
                            _render_thought_log(thoughts, done=False)

                    elif event["type"] == "report":
                        final_report = event["data"]
                        with log_placeholder.container():
                            _render_thought_log(thoughts, done=True)

                    elif event["type"] == "error":
                        st.error(f"Agent error: {event['message']}")
                        break

    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        st.error(detail)
    except Exception as e:
        st.error(f"Streaming failed: {e}")

    if final_report:
        st.session_state["result"] = {"trade_id": tid, "report": final_report}
        st.session_state["result_trade"] = trade
        st.rerun()
    st.stop()

result     = st.session_state.get("result")
result_trade = st.session_state.get("result_trade")

if not result:
    st.markdown(
        f'<div style="padding:18px 22px;background:{WF_BG};border:1px solid {WF_BORDER};'
        f'border-left:4px solid {WF_RED};border-radius:0 4px 4px 0;'
        f'color:{WF_GRAY};font-size:0.9rem">'
        f'Select a <strong style="color:{WF_RED}">FAILED</strong> trade from the sidebar '
        f'and click <strong style="color:{WF_RED}">Run Investigation</strong> to begin.</div>',
        unsafe_allow_html=True,
    )
    st.stop()

report = result["report"]
tid    = result["trade_id"]

# ── Report header ─────────────────────────────────────────────────────────────

st.markdown(
    f'<div style="display:flex;align-items:center;gap:14px;margin:4px 0 2px 0">'
    f'<span style="font-size:1.6rem;font-weight:700;color:{WF_DARK};'
    f'font-family:monospace;letter-spacing:0.03em">{tid}</span>'
    f'{status_badge("FAILED")}</div>',
    unsafe_allow_html=True,
)
if result_trade:
    st.markdown(
        f'<div style="color:{WF_GRAY};font-size:0.8rem;margin-bottom:14px">'
        f'{result_trade["instrument"]} ({result_trade["instrument_type"]})'
        f'&nbsp;&nbsp;·&nbsp;&nbsp;{result_trade["notional_value"]:,.0f} {result_trade["currency"]}'
        f'&nbsp;&nbsp;·&nbsp;&nbsp;{result_trade["counterparty"]}'
        f'&nbsp;&nbsp;·&nbsp;&nbsp;{result_trade["failure_reason"]}</div>',
        unsafe_allow_html=True,
    )

st.divider()

# ── Root cause ────────────────────────────────────────────────────────────────

st.markdown("#### Root Cause")
st.markdown(
    f'<div style="background:#FFF5F5;border:1px solid #FECACA;border-left:4px solid {WF_RED};'
    f'padding:14px 18px;border-radius:0 4px 4px 0;margin-bottom:20px">'
    f'<span style="color:{WF_RED};font-weight:700;font-size:0.68rem;'
    f'letter-spacing:0.1em;text-transform:uppercase;display:block;margin-bottom:6px">'
    f'Root Cause Finding</span>'
    f'<span style="color:{WF_DARK};font-size:0.95rem;line-height:1.6">'
    f'{report["root_cause"]}</span></div>',
    unsafe_allow_html=True,
)

# ── Confidence score ──────────────────────────────────────────────────────────

st.markdown("#### Confidence Score")
confidence_bar(report["confidence_score"])

# ── Evidence + Next steps ─────────────────────────────────────────────────────

col_ev, col_ns = st.columns(2, gap="large")

with col_ev:
    st.markdown("#### Supporting Evidence")
    for i, point in enumerate(report["evidence"], 1):
        st.markdown(info_card(point, WF_RED, i), unsafe_allow_html=True)

with col_ns:
    st.markdown("#### Recommended Next Steps")
    for i, step in enumerate(report["recommended_next_steps"], 1):
        st.markdown(info_card(step, "#16A34A", i), unsafe_allow_html=True)
