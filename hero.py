"""Login hero: a dark, spotlight-lit card with an interactive 3D Spline scene.

This is the Streamlit port of the React "SplineSceneBasic" demo. Streamlit has no
React/Tailwind, so instead of `@splinetool/react-spline` we embed Spline's
official `<spline-viewer>` web component inside an `st.components.v1.html` iframe,
and recreate the spotlight + gradient styling in plain CSS. The 3D scene is
interactive (it follows the cursor) and degrades gracefully to the styled hero if
the browser can't reach the Spline CDN.
"""

from __future__ import annotations

import streamlit.components.v1 as components

# The 3D scene from the demo (a robot that tracks the cursor).
SPLINE_SCENE = "https://prod.spline.design/kZDDjO5HuC9GJUM2/scene.splinecode"

_HERO_HTML = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<script type="module"
        src="https://unpkg.com/@splinetool/viewer/build/spline-viewer.js"></script>
<style>
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: transparent; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 Helvetica, Arial, sans-serif;
  }}

  .rh-hero {{
    position: relative;
    display: flex;
    width: 100%;
    height: 460px;
    border-radius: 18px;
    overflow: hidden;
    background: #050507;            /* black/0.96 like the demo */
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: 0 20px 60px rgba(0,0,0,0.35);
  }}

  /* ---- Animated spotlight (CSS port of the aceternity spotlight) ---- */
  .rh-spotlight {{
    position: absolute;
    top: -30%;
    left: -10%;
    width: 70%;
    height: 150%;
    background: radial-gradient(ellipse at center,
                rgba(255,255,255,0.22) 0%, rgba(255,255,255,0.0) 60%);
    filter: blur(40px);
    transform: translate(-25%, -10%) rotate(-18deg) scale(0.7);
    opacity: 0;
    animation: rh-spot 2.2s ease forwards 0.1s;
    pointer-events: none;
    z-index: 1;
  }}
  @keyframes rh-spot {{
    0%   {{ opacity: 0; transform: translate(-25%, -10%) rotate(-18deg) scale(0.7); }}
    100% {{ opacity: 1; transform: translate(0, 0) rotate(-18deg) scale(1); }}
  }}

  /* ---- Left: copy ---- */
  .rh-left {{
    flex: 1 1 0;
    position: relative;
    z-index: 10;
    padding: 40px 36px;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }}
  .rh-eyebrow {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    width: fit-content;
    font-size: 12px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: #cdd3c4;
    background: rgba(106,116,89,0.18);
    border: 1px solid rgba(106,116,89,0.5);
    padding: 6px 12px;
    border-radius: 999px;
    margin-bottom: 18px;
  }}
  .rh-dot {{
    width: 7px; height: 7px; border-radius: 50%;
    background: #9bd17a; box-shadow: 0 0 10px #9bd17a;
  }}
  .rh-title {{
    margin: 0;
    font-size: clamp(2.4rem, 5vw, 3.6rem);
    font-weight: 800;
    line-height: 1.0;
    letter-spacing: -0.02em;
    background: linear-gradient(to bottom, #fafafa 0%, #9b9b9b 100%);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }}
  .rh-sub {{
    margin: 16px 0 0 0;
    max-width: 30rem;
    color: #c9ccd2;
    font-size: 1.02rem;
    line-height: 1.55;
  }}
  .rh-pills {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 22px; }}
  .rh-pill {{
    font-size: 12.5px;
    color: #e7e9ec;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12);
    padding: 6px 12px;
    border-radius: 999px;
  }}

  /* ---- Right: 3D scene ---- */
  .rh-right {{ flex: 1 1 0; position: relative; }}
  .rh-right spline-viewer {{ width: 100%; height: 100%; display: block; }}

  /* fade the 3D in once it mounts */
  .rh-right {{ animation: rh-fade 1.2s ease forwards 0.2s; opacity: 0; }}
  @keyframes rh-fade {{ to {{ opacity: 1; }} }}

  @media (max-width: 640px) {{
    .rh-hero {{ flex-direction: column; height: 560px; }}
    .rh-left {{ padding: 28px 24px 8px 24px; flex: 0 0 auto; }}
    .rh-right {{ flex: 1 1 auto; min-height: 240px; }}
  }}
  @media (prefers-reduced-motion: reduce) {{
    .rh-spotlight, .rh-right {{ animation: none; opacity: 1; }}
    .rh-spotlight {{ transform: translate(0,0) rotate(-18deg) scale(1); }}
  }}
</style>
</head>
<body>
  <div class="rh-hero">
    <div class="rh-spotlight"></div>
    <div class="rh-left">
      <span class="rh-eyebrow"><span class="rh-dot"></span> Interactive&nbsp;3D</span>
      <h1 class="rh-title">RentHarbor</h1>
      <p class="rh-sub">
        One platform for managers and tenants. Pay rent, track maintenance, and
        run every property from a single place — now with a little life to it.
      </p>
      <div class="rh-pills">
        <span class="rh-pill">💳 Online rent</span>
        <span class="rh-pill">🛠️ Maintenance</span>
        <span class="rh-pill">🏢 Properties</span>
        <span class="rh-pill">📊 Reports</span>
      </div>
    </div>
    <div class="rh-right">
      <spline-viewer url="{SPLINE_SCENE}"
                     loading-anim-type="spinner-small-light"></spline-viewer>
    </div>
  </div>
</body>
</html>
"""


def render_login_hero() -> None:
    """Render the interactive 3D hero above the login form."""
    components.html(_HERO_HTML, height=480, scrolling=False)
