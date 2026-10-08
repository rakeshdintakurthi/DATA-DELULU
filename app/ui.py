"""Data Delulu visual layer: CSS, 3D hero, gauges, cards, and architecture components.
Light 'frosted glass' theme with enterprise privacy styling.
"""
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

INK, SLATE, LAGOON, IRIS, EMBER = "#172036", "#5B6478", "#0E8C8C", "#6B5BD6", "#C2513A"
EMERALD, NAVY = "#0F9D58", "#1E2A4A"


def h(html: str) -> None:
    """Render HTML without Markdown turning indented lines into code blocks."""
    st.markdown("".join(line.strip() for line in html.splitlines()), unsafe_allow_html=True)


def inject_css() -> None:
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700;800&family=Manrope:wght@400;500;600;700&display=swap');
:root{
  --ink:#172036;--slate:#5B6478;--lagoon:#0E8C8C;--iris:#6B5BD6;--ember:#C2513A;--porcelain:#EEF2F7;
  --emerald:#0F9D58;--navy:#1E2A4A;
  --glass:rgba(255,255,255,.76);--edge:rgba(255,255,255,.92);
  --depth:0 1px 0 rgba(255,255,255,.9) inset,0 1px 2px rgba(23,32,54,.06),0 10px 30px -12px rgba(23,32,54,.16),0 30px 60px -30px rgba(52,66,140,.20);
}
html,body,[class*="css"],.stApp{font-family:'Manrope','Segoe UI',system-ui,sans-serif;color:var(--ink);}
.stApp{background:
 radial-gradient(1200px 600px at 85% -10%,rgba(107,91,214,.12),transparent 60%),
 radial-gradient(900px 500px at -10% 10%,rgba(14,140,140,.12),transparent 60%),var(--porcelain);}
h1,h2,h3,.dd-title{font-family:'Sora','Segoe UI',system-ui,sans-serif!important;font-weight:700!important;letter-spacing:-.02em;color:var(--ink);}
header[data-testid="stHeader"]{background:transparent;}
[data-testid="stToolbar"],footer,#MainMenu,[data-testid="stSidebar"],[data-testid="collapsedControl"]{display:none!important;}
.block-container{padding-top:1.2rem;max-width:1200px;}
/* frosted cards = st.container(border=True) */
[class*="st-key-card"]{padding:20px 22px!important;
 background:var(--glass);backdrop-filter:blur(14px) saturate(140%);-webkit-backdrop-filter:blur(14px) saturate(140%);
 border:1px solid var(--edge)!important;border-radius:20px!important;box-shadow:var(--depth);}
/* buttons */
.stButton>button,.stDownloadButton>button,.stFormSubmitButton>button{border-radius:12px;font-weight:600;
 border:1px solid rgba(23,32,54,.12);background:#fff;color:var(--ink);
 box-shadow:0 1px 0 #fff inset,0 2px 0 rgba(23,32,54,.08),0 6px 14px -8px rgba(23,32,54,.25);
 transition:transform .12s ease,box-shadow .12s ease;}
.stButton>button:hover,.stDownloadButton>button:hover,.stFormSubmitButton>button:hover{transform:translateY(-1px);border-color:rgba(14,140,140,.45);color:var(--ink);}
.stButton>button:active,.stDownloadButton>button:active{transform:translateY(1px);box-shadow:0 1px 0 rgba(23,32,54,.08);}
button[kind="primary"],[data-testid="stBaseButton-primary"]{background:linear-gradient(180deg,#14A3A3 0%,#0E8C8C 55%,#0B7474 100%)!important;
 color:#fff!important;border:1px solid #0B6B6B!important;
 box-shadow:0 1px 0 rgba(255,255,255,.35) inset,0 3px 0 #095C5C,0 10px 20px -8px rgba(14,140,140,.55)!important;}
button[kind="primary"]:hover,[data-testid="stBaseButton-primary"]:hover{color:#fff!important;filter:brightness(1.05);}
button:focus-visible{outline:3px solid rgba(107,91,214,.45)!important;outline-offset:2px;}
/* inputs */
[data-baseweb="select"]>div,[data-baseweb="input"]>div,.stNumberInput input,[data-testid="stFileUploaderDropzone"]{
 border-radius:12px!important;background:#fff!important;border-color:rgba(23,32,54,.12)!important;}
[data-testid="stFileUploaderDropzone"]{border:1.5px dashed rgba(14,140,140,.45)!important;background:rgba(255,255,255,.6)!important;}
/* tabs as pills */
[data-baseweb="tab-list"]{gap:6px;background:rgba(255,255,255,.55);padding:6px;border-radius:14px;border:1px solid var(--edge);box-shadow:var(--depth);}
[data-baseweb="tab"]{border-radius:10px!important;padding:6px 14px!important;font-weight:600;}
[data-baseweb="tab"][aria-selected="true"]{background:#fff;box-shadow:0 2px 8px -2px rgba(23,32,54,.2);}
[data-baseweb="tab-highlight"],[data-baseweb="tab-border"]{display:none;}
[role="tablist"]{gap:6px;background:rgba(255,255,255,.6);padding:6px;border-radius:14px;border:1px solid var(--edge);box-shadow:var(--depth);width:fit-content;}
[data-testid="stTab"]{border-radius:10px!important;padding:6px 14px!important;font-weight:600;}
[data-testid="stTab"][aria-selected="true"]{background:#fff;color:var(--ink)!important;box-shadow:0 2px 8px -2px rgba(23,32,54,.22);}
[data-testid="stSegmentedControl"] button{border-radius:10px!important;font-weight:600;}
[data-testid="stMetricValue"]{font-family:'Sora','Segoe UI',system-ui,sans-serif;}
.stAlert{border-radius:14px;}

/* custom header & brand */
.dd-bar{display:flex;align-items:center;justify-content:space-between;margin:0 0 .6rem;flex-wrap:wrap;gap:.8rem;padding-bottom:.4rem;border-bottom:1px solid rgba(23,32,54,.06);}
.dd-brand{display:flex;align-items:center;gap:.65rem;font-family:'Sora','Segoe UI',system-ui,sans-serif;font-weight:800;font-size:1.35rem;letter-spacing:-.01em;}
.dd-logo{width:36px;height:36px;border-radius:12px;background:conic-gradient(from 210deg,#0E8C8C,#6B5BD6,#14A3A3);
 box-shadow:0 1px 0 rgba(255,255,255,.6) inset,0 6px 14px -6px rgba(107,91,214,.7);position:relative;display:grid;place-items:center;}
.dd-logo span{color:#fff;font-size:18px;font-weight:800;}
.dd-header-badges{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;}
.dd-mode-pill{background:#172036;color:#fff;border-radius:999px;padding:.32rem .85rem;font-size:.82rem;font-weight:700;letter-spacing:.02em;}
.dd-mode-pill.demo{background:linear-gradient(135deg,#0E8C8C,#0B7474);color:#fff;}
.dd-mode-pill.enterprise{background:linear-gradient(135deg,#6B5BD6,#483AAB);color:#fff;}
.dd-agent-status{background:rgba(15,157,88,.12);border:1px solid rgba(15,157,88,.3);color:#0B6F3E;
 border-radius:999px;padding:.32rem .85rem;font-size:.82rem;font-weight:600;display:flex;align-items:center;gap:6px;}
.dd-agent-status i{width:8px;height:8px;border-radius:50%;background:#0F9D58;display:inline-block;box-shadow:0 0 6px #0F9D58;}

/* Profile Identity Widget */
.dd-user-profile{display:flex;align-items:center;gap:.6rem;background:#fff;border:1px solid var(--edge);border-radius:999px;padding:.28rem .85rem .28rem .7rem;box-shadow:var(--depth);font-size:.84rem;color:var(--slate);}
.dd-user-profile b{color:var(--ink);}
.dd-role-badge{padding:.15rem .55rem;border-radius:999px;font-size:.72rem;font-weight:700;letter-spacing:.03em;text-transform:uppercase;}
.dd-role-badge.admin{background:rgba(107,91,214,.15);color:#5B4AC7;}
.dd-role-badge.analyst{background:rgba(14,140,140,.15);color:#0B7474;}
.dd-role-badge.viewer{background:rgba(91,100,120,.15);color:#4A5263;}

.dd-hero h1{font-size:3.1rem;line-height:1.02;margin:.2rem 0 1rem;font-weight:800;}
.dd-hero p{font-size:1.08rem;color:var(--slate);max-width:46ch;line-height:1.6;}
.dd-facts{display:flex;gap:1.6rem;margin-top:1.4rem;}
.dd-facts div{font-size:.86rem;color:var(--slate);max-width:15ch;line-height:1.4;}
.dd-facts b{display:block;font-family:'Sora','Segoe UI',system-ui,sans-serif;font-size:1.35rem;color:var(--ink);}
.dd-sub{color:var(--slate);margin:-.4rem 0 1rem;}

.dd-gauges{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin:.4rem 0 1rem;}
.dd-g{background:var(--glass);backdrop-filter:blur(14px);border:1px solid var(--edge);border-radius:20px;padding:16px 10px 14px;
 text-align:center;box-shadow:var(--depth);}
.dd-g svg{width:104px;height:104px;filter:drop-shadow(0 6px 8px rgba(23,32,54,.12));}
.dd-g .v{font-family:'Sora','Segoe UI',system-ui,sans-serif;font-weight:700;font-size:1.25rem;fill:var(--ink);}
.dd-g .l{font-weight:700;margin-top:6px;}
.dd-g .s{font-size:.78rem;color:var(--slate);margin-top:2px;line-height:1.3;}
.dd-big{font-family:'Sora','Segoe UI',system-ui,sans-serif;font-weight:700;font-size:2.5rem;line-height:104px;height:104px;}

.dd-tests{display:flex;flex-direction:column;gap:8px;}
.dd-t{display:grid;grid-template-columns:30px 1fr;gap:10px;align-items:center;background:#fff;border-radius:14px;
 padding:10px 12px;border:1px solid rgba(23,32,54,.06);box-shadow:0 1px 2px rgba(23,32,54,.05);}
.dd-t i{width:30px;height:30px;border-radius:10px;display:grid;place-items:center;font-style:normal;font-weight:700;color:#fff;}
.dd-t .ok{background:linear-gradient(180deg,#14A3A3,#0B7474);box-shadow:0 3px 0 #095C5C;}
.dd-t .no{background:linear-gradient(180deg,#D96A52,#A8402B);box-shadow:0 3px 0 #85301F;}
.dd-t b{display:block;font-size:.95rem;} .dd-t span{font-size:.82rem;color:var(--slate);}

.dd-banner{border-radius:16px;padding:12px 16px;margin:.2rem 0 1rem;font-weight:600;border:1px solid;}
.dd-banner.ok{background:rgba(14,140,140,.08);border-color:rgba(14,140,140,.3);color:#0B5F5F;}
.dd-banner.warn{background:rgba(194,81,58,.08);border-color:rgba(194,81,58,.3);color:#8E3624;}
.dd-banner.info{background:rgba(107,91,214,.08);border-color:rgba(107,91,214,.3);color:#483AAB;}

.dd-steps{display:flex;gap:10px;margin:.2rem 0 1.2rem;}
.dd-step{flex:1;display:flex;align-items:center;gap:10px;background:rgba(255,255,255,.6);border:1px solid var(--edge);
 border-radius:14px;padding:10px 12px;color:var(--slate);font-weight:600;font-size:.9rem;}
.dd-step b{width:26px;height:26px;border-radius:9px;display:grid;place-items:center;background:#E3E8F1;color:var(--slate);font-family:'Sora','Segoe UI',system-ui,sans-serif;}
.dd-step.on{background:#fff;color:var(--ink);box-shadow:var(--depth);} .dd-step.on b{background:var(--lagoon);color:#fff;box-shadow:0 2px 0 #095C5C;}

.dd-how{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;}
.dd-how div{background:var(--glass);border:1px solid var(--edge);border-radius:20px;padding:20px;box-shadow:var(--depth);}
.dd-how h3{font-size:1.05rem;margin:0 0 .4rem;} .dd-how p{color:var(--slate);font-size:.93rem;line-height:1.55;margin:0;}
.dd-note{color:var(--slate);font-size:.84rem;}

/* 3D Depth, Floating Cards & Modern AI/Privacy Visuals */
.dd-3d-card {
  perspective: 1000px;
  transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.22s ease;
}
.dd-3d-card:hover {
  transform: translateY(-3px) rotateX(1deg);
  box-shadow: 0 14px 34px -10px rgba(23,32,54,.16), 0 2px 8px rgba(14,140,140,.12);
}
.dd-core-glow {
  animation: corePulse 3.5s infinite ease-in-out;
}
@keyframes corePulse {
  0%, 100% { filter: drop-shadow(0 0 8px rgba(14,140,140,.45)) drop-shadow(0 0 20px rgba(107,91,214,.35)); }
  50% { filter: drop-shadow(0 0 16px rgba(14,140,140,.75)) drop-shadow(0 0 32px rgba(107,91,214,.55)); }
}

/* Data Sources Grid */
.dd-ds-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px; margin: 10px 0 16px; }
.dd-ds-card {
  background: #ffffff;
  border: 1px solid rgba(23,32,54,.10);
  border-radius: 16px;
  padding: 16px 18px;
  box-shadow: 0 1px 3px rgba(23,32,54,.05), 0 6px 16px -6px rgba(23,32,54,.08);
  transition: all 0.2s ease;
  position: relative;
  overflow: hidden;
}
.dd-ds-card:hover {
  transform: translateY(-2px);
  border-color: rgba(14,140,140,.5);
  box-shadow: 0 8px 24px -6px rgba(14,140,140,.15);
}
.dd-ds-card.connected {
  border: 1.5px solid #0E8C8C;
  background: linear-gradient(180deg, #FFFFFF 0%, rgba(14,140,140,.04) 100%);
  box-shadow: 0 4px 18px -4px rgba(14,140,140,.2);
}
.dd-ds-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.dd-ds-title { font-weight: 700; font-size: 1rem; display: flex; align-items: center; gap: 8px; }
.dd-ds-status {
  font-size: .74rem;
  font-weight: 700;
  padding: 2px 10px;
  border-radius: 999px;
  letter-spacing: .02em;
  text-transform: uppercase;
}
.dd-ds-status.connected { background: rgba(15,157,88,.15); color: #0B6F3E; }
.dd-ds-status.available { background: rgba(107,91,214,.12); color: #5B4AC7; }
.dd-ds-status.demo { background: rgba(91,100,120,.12); color: #5B6478; }
.dd-ds-meta { font-size: .82rem; color: var(--slate); line-height: 1.4; }

@media (max-width:900px){.dd-gauges{grid-template-columns:repeat(2,1fr);}.dd-how{grid-template-columns:1fr;}.dd-hero h1{font-size:2.3rem;}.arch-grid{grid-template-columns:1fr;}.dd-ds-grid{grid-template-columns:1fr;}}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important;}}
</style>""", unsafe_allow_html=True)


def top_bar(org=None, user=None, mode: str = "Demo") -> None:
    mode_class = "demo" if mode == "Demo" else "enterprise"
    mode_label = "DEMO MODE" if mode == "Demo" else "ENTERPRISE MODE"
    
    agent_status_html = (
        '<div class="dd-agent-status"><i></i><span>Data Delulu Agent: <b>Connected (0 Egress)</b></span></div>'
    )
    
    user_profile_html = ""
    if user and org:
        role = user.get("role", "VIEWER").upper()
        role_class = role.lower()
        user_profile_html = f"""
        <div class="dd-user-profile">
          <span>Org: <b>{org["name"]}</b></span>
          <span>User: <b>{user["email"]}</b></span>
          <span class="dd-role-badge {role_class}">{role}</span>
        </div>
        """
    
    h(f"""
    <div class="dd-bar">
      <div class="dd-brand"><div class="dd-logo"><span>🔒</span></div>DATA DELULU</div>
      <div class="dd-header-badges">
        <div class="dd-mode-pill {mode_class}">{mode_label}</div>
        {agent_status_html}
        {user_profile_html}
      </div>
    </div>
    """)


@st.cache_resource
def _three_js() -> str:
    """three.js r128 bundled locally so the 3D hero works without internet."""
    return (Path(__file__).parent / "static" / "three.min.js").read_text(encoding="utf-8")


def card(key: str):
    """Frosted 3D card (a bordered container styled by CSS via its key)."""
    return st.container(border=True, key=f"card_{key}")


def hero_sphere(height: int = 430) -> None:
    """Interactive 3D point cloud: real points (ink) jitter with privacy noise into synthetic points."""
    components.html(f"""
<div id="wrap" style="width:100%;height:{height}px;position:relative;">
<div id="fallback" style="position:absolute;inset:40px;border-radius:50%;
 background:radial-gradient(circle at 35% 30%,#fff,#cfe9ea 35%,#b9b2ef 75%,#9b90e6);
 box-shadow:0 40px 60px -30px rgba(52,66,140,.45),inset -20px -30px 60px rgba(107,91,214,.35);"></div>
</div>
<script>__THREE__</script>
<script>
(function(){{
 if(!window.THREE) return;
 document.getElementById('fallback').remove();
 const wrap=document.getElementById('wrap'), W=wrap.clientWidth, H={height};
 const renderer=new THREE.WebGLRenderer({{antialias:true,alpha:true}});
 renderer.setPixelRatio(Math.min(2,window.devicePixelRatio)); renderer.setSize(W,H); wrap.appendChild(renderer.domElement);
 const scene=new THREE.Scene(), cam=new THREE.PerspectiveCamera(42,W/H,.1,100); cam.position.z=6.2;
 const N=1400, base=new Float32Array(N*3), pos=new Float32Array(N*3), col=new Float32Array(N*3), phase=new Float32Array(N);
 const ink=new THREE.Color('{INK}'), lag=new THREE.Color('{LAGOON}'), iris=new THREE.Color('{IRIS}');
 for(let i=0;i<N;i++){{ const y=1-(i/(N-1))*2, r=Math.sqrt(1-y*y), t=i*2.399963;
  base[i*3]=Math.cos(t)*r*1.9; base[i*3+1]=y*1.9; base[i*3+2]=Math.sin(t)*r*1.9; phase[i]=Math.random()*6.28;
  const c=(i%3===0)?ink:(i%3===1?lag:iris); col[i*3]=c.r; col[i*3+1]=c.g; col[i*3+2]=c.b; }}
 const g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.BufferAttribute(pos,3)); g.setAttribute('color',new THREE.BufferAttribute(col,3));
 const pts=new THREE.Points(g,new THREE.PointsMaterial({{size:.045,vertexColors:true,transparent:true,opacity:.9}}));
 const core=new THREE.Mesh(new THREE.IcosahedronGeometry(1.25,1),new THREE.MeshStandardMaterial({{color:0xffffff,roughness:.25,metalness:.1,transparent:true,opacity:.55,flatShading:true}}));
 const wire=new THREE.Mesh(new THREE.IcosahedronGeometry(1.27,1),new THREE.MeshBasicMaterial({{color:0x6B5BD6,wireframe:true,transparent:true,opacity:.25}}));
 const ring=new THREE.Mesh(new THREE.TorusGeometry(2.45,.012,8,160),new THREE.MeshBasicMaterial({{color:0x0E8C8C,transparent:true,opacity:.5}}));
 ring.rotation.x=1.2;
 const grp=new THREE.Group(); grp.add(pts,core,wire,ring); scene.add(grp);
 scene.add(new THREE.AmbientLight(0xffffff,.75)); const dl=new THREE.DirectionalLight(0xffffff,.9); dl.position.set(3,4,5); scene.add(dl);
 const pl=new THREE.PointLight(0x6B5BD6,.8,20); pl.position.set(-4,-2,3); scene.add(pl);
 let mx=0,my=0; wrap.addEventListener('mousemove',e=>{{const b=wrap.getBoundingClientRect(); mx=(e.clientX-b.left)/b.width-.5; my=(e.clientY-b.top)/b.height-.5;}});
 const still=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
 function frame(t){{ t*=.001; const noise=.10+.08*Math.sin(t*.7);
  for(let i=0;i<N;i++){{ const k=1+noise*Math.sin(t*1.6+phase[i]);
   pos[i*3]=base[i*3]*k; pos[i*3+1]=base[i*3+1]*k; pos[i*3+2]=base[i*3+2]*k; }}
  g.attributes.position.needsUpdate=true;
  grp.rotation.y+=still?0:.0025; grp.rotation.x+=((my*.6)-grp.rotation.x)*.05; grp.rotation.z+=((-mx*.4)-grp.rotation.z)*.05;
  core.rotation.y-=still?0:.004; renderer.render(scene,cam); if(!still) requestAnimationFrame(frame); }}
 requestAnimationFrame(frame);
}})();
</script>""".replace("__THREE__", _three_js()), height=height)


def _ring(pct: float, color: str) -> str:
    c = 2 * 3.14159 * 44
    filled = max(0.0, min(100.0, pct)) / 100 * c
    return (f'<svg viewBox="0 0 120 120"><defs><linearGradient id="g{color[1:]}" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0" stop-color="{color}" stop-opacity=".75"/><stop offset="1" stop-color="{color}"/></linearGradient></defs>'
            f'<circle cx="60" cy="60" r="52" fill="#fff"/>'
            f'<circle cx="60" cy="60" r="44" fill="none" stroke="#E6EAF2" stroke-width="12"/>'
            f'<circle cx="60" cy="60" r="44" fill="none" stroke="url(#g{color[1:]})" stroke-width="12" stroke-linecap="round" '
            f'stroke-dasharray="{filled:.1f} {c:.1f}" transform="rotate(-90 60 60)"/>'
            f'<text x="60" y="66" text-anchor="middle" class="v">{pct:.0f}%</text></svg>')


def gauges(job: dict) -> None:
    ok = job["tests_passed"] == job["tests_total"]
    h(f"""<div class="dd-gauges">
<div class="dd-g">{_ring(job['guaranteed_privacy_pct'], IRIS)}<div class="l">Privacy</div><div class="s">Guaranteed against any attacker</div></div>
<div class="dd-g">{_ring(job['utility_pct'], LAGOON)}<div class="l">Utility</div><div class="s">Model accuracy kept vs real data</div></div>
<div class="dd-g">{_ring(job['similarity_pct'], '#3A7BD5')}<div class="l">Similarity</div><div class="s">Columns match the real shape</div></div>
<div class="dd-g"><div class="dd-big" style="color:{LAGOON if ok else EMBER}">{job['tests_passed']}/{job['tests_total']}</div><div class="l">Tests passed</div><div class="s">Automatic checks on this dataset</div></div>
<div class="dd-g"><div class="dd-big">ε {job['epsilon']:g}</div><div class="l">Privacy budget</div><div class="s">Smaller means stronger privacy</div></div>
</div>""")


def banner(ok: bool, text: str) -> None:
    h(f'<div class="dd-banner {"ok" if ok else "warn"}">{text}</div>')


def info_banner(text: str) -> None:
    h(f'<div class="dd-banner info">{text}</div>')


def test_list(tests) -> None:
    rows = "".join(f'<div class="dd-t"><i class="{"ok" if t["passed"] else "no"}">{"✓" if t["passed"] else "✕"}</i>'
                   f'<div><b>{t["name"]}</b><span>{t["detail"]}</span></div></div>' for t in tests)
    h(f'<div class="dd-tests">{rows}</div>')


def steps(active: int) -> None:
    names = ["Connect data source", "Set privacy level", "Generate & evaluate", "Share securely"]
    items = "".join(f'<div class="dd-step {"on" if i <= active else ""}"><b>{i + 1}</b>{n}</div>' for i, n in enumerate(names))
    h(f'<div class="dd-steps">{items}</div>')


def chart_theme(chart):
    return (chart.configure_view(strokeWidth=0)
            .configure_axis(labelFont="Manrope, Segoe UI, sans-serif", titleFont="Manrope, Segoe UI, sans-serif", labelColor=SLATE, titleColor=SLATE,
                            gridColor="#E3E8F1", domainColor="#D5DBE6", tickColor="#D5DBE6")
            .configure_legend(labelFont="Manrope, Segoe UI, sans-serif", labelColor=INK, orient="bottom")
            .properties(background="transparent"))


def render_3d_pipeline_core(org_name: str, db_provider: str, record_count: int = 5000) -> None:
    """Renders a modern, subtle 3D/depth architecture visualization:
    Customer Database (3D Cylinder) -> Data Delulu Privacy Core (Glowing Polyhedron) -> Synthetic Data (Certified 3D Block).
    """
    h(f"""
    <div style="background: linear-gradient(135deg, rgba(255,255,255,0.92) 0%, rgba(240,244,248,0.85) 100%);
                border: 1px solid rgba(255,255,255,0.9);
                border-radius: 20px;
                padding: 22px 24px;
                box-shadow: 0 1px 0 #fff inset, 0 10px 30px -12px rgba(23,32,54,.14), 0 20px 40px -20px rgba(107,91,214,.18);
                margin: 10px 0 20px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
        <span style="font-family:'Sora',sans-serif; font-weight:700; font-size:1.02rem; color:#172036; display:flex; align-items:center; gap:8px;">
          ✨ <b>In-Enclave 3D Privacy Pipeline Core</b>
        </span>
        <span style="background:rgba(15,157,88,.12); color:#0B6F3E; font-size:.78rem; font-weight:700; padding:3px 12px; border-radius:999px; border:1px solid rgba(15,157,88,.25);">
          ● LOCAL DATA PLANE VERIFIED
        </span>
      </div>

      <div style="display:grid; grid-template-columns: 1fr 40px 1.2fr 40px 1fr; align-items:center; gap:10px; text-align:center;">
        
        <!-- 1. 3D Database Cylinder Node -->
        <div class="dd-3d-card" style="background:#ffffff; border:1px solid rgba(23,32,54,.1); border-radius:16px; padding:16px 12px; box-shadow:0 6px 18px -4px rgba(23,32,54,.1);">
          <div style="width:48px; height:48px; margin:0 auto 8px; border-radius:12px; background:linear-gradient(135deg,#0E8C8C,#0B7474); box-shadow:0 6px 14px -3px rgba(14,140,140,.5); display:grid; place-items:center; font-size:24px;">
            🏦
          </div>
          <div style="font-weight:700; font-size:.94rem; color:#172036;">{db_provider}</div>
          <div style="font-size:.78rem; color:#5B6478; margin-top:2px;">{org_name}</div>
          <div style="margin-top:6px; font-size:.75rem; font-weight:700; color:#0E8C8C; background:rgba(14,140,140,.08); padding:2px 8px; border-radius:999px; display:inline-block;">
            {record_count:,} Local Records
          </div>
        </div>

        <!-- Connector Arrow 1 -->
        <div style="color:#0E8C8C; font-size:1.4rem; font-weight:800;">➔</div>

        <!-- 2. Glowing 3D Privacy Core Node -->
        <div class="dd-3d-card dd-core-glow" style="background: linear-gradient(145deg, #1E2A4A, #172036); border:1.5px solid rgba(107,91,214,.5); border-radius:18px; padding:18px 14px; color:#ffffff; box-shadow:0 12px 30px -6px rgba(107,91,214,.4);">
          <div style="width:52px; height:52px; margin:0 auto 8px; border-radius:14px; background:linear-gradient(135deg,#6B5BD6,#9B90E6); box-shadow:0 0 20px rgba(107,91,214,.8); display:grid; place-items:center; font-size:26px;">
            🔒
          </div>
          <div style="font-weight:800; font-size:1.02rem; letter-spacing:-.01em; color:#ffffff;">Data Delulu Privacy Core</div>
          <div style="font-size:.8rem; color:#CFE9EA; margin-top:2px;">Local ε-DP Laplace Engine</div>
          <div style="margin-top:6px; font-size:.72rem; font-weight:700; background:rgba(255,255,255,.15); padding:3px 10px; border-radius:999px; display:inline-block; letter-spacing:.02em;">
            🛡️ 0 RAW DATA EGRESS
          </div>
        </div>

        <!-- Connector Arrow 2 -->
        <div style="color:#6B5BD6; font-size:1.4rem; font-weight:800;">➔</div>

        <!-- 3. Certified Synthetic Dataset Node -->
        <div class="dd-3d-card" style="background:#ffffff; border:1px solid rgba(23,32,54,.1); border-radius:16px; padding:16px 12px; box-shadow:0 6px 18px -4px rgba(23,32,54,.1);">
          <div style="width:48px; height:48px; margin:0 auto 8px; border-radius:12px; background:linear-gradient(135deg,#0F9D58,#0B6F3E); box-shadow:0 6px 14px -3px rgba(15,157,88,.5); display:grid; place-items:center; font-size:24px;">
            ⚡
          </div>
          <div style="font-weight:700; font-size:.94rem; color:#172036;">Synthetic Dataset</div>
          <div style="font-size:.78rem; color:#5B6478; margin-top:2px;">Certified Safe for AI/ML</div>
          <div style="margin-top:6px; font-size:.75rem; font-weight:700; color:#0F9D58; background:rgba(15,157,88,.08); padding:2px 8px; border-radius:999px; display:inline-block;">
            {record_count:,} Synthetic Rows
          </div>
        </div>

      </div>
    </div>
    """)
