"""会话右键菜单 —— DeepSeek 式

关键坑：
1. Streamlit widget 与 markdown 标记是**兄弟节点**，且曾错误地每行闭合
   ds-sess-col，导致拦截失效、弹出浏览器菜单。
2. st.html 脚本必须同时绑 document / parent / top。
"""

import html as _html

import streamlit as st
import streamlit.components.v1 as components

_CTX_JS = r"""
(function () {
  if (window.__dsCtxV3) return;
  window.__dsCtxV3 = true;

  function ensureMenu(doc) {
    if (doc.getElementById("ds-ctx-menu")) return doc.getElementById("ds-ctx-menu");
    var menu = doc.createElement("div");
    menu.id = "ds-ctx-menu";
    menu.style.cssText = "display:none;position:fixed;z-index:2147483000;min-width:172px;padding:6px;background:var(--panel);border:1px solid var(--border);border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,.18);font-size:13px;color:var(--text);";
    [
      { act: "rename", label: "重命名", icon: "✏️" },
      { act: "pin", label: "置顶", icon: "📌" },
      { act: "share", label: "分享", icon: "↗" },
      { act: "multi", label: "多选", icon: "☑" },
      { act: "delete", label: "删除", icon: "🗑", danger: true }
    ].forEach(function (it) {
      var b = doc.createElement("button");
      b.type = "button";
      b.dataset.act = it.act;
      b.textContent = it.icon + "  " + it.label;
      b.style.cssText = "display:block;width:100%;text-align:left;padding:8px 10px;border:none;border-radius:8px;background:transparent;cursor:pointer;color:" + (it.danger ? "var(--danger)" : "var(--text)");
      b.addEventListener("mouseenter", function () { b.style.background = "var(--panel-2)"; });
      b.addEventListener("mouseleave", function () { b.style.background = "transparent"; });
      b.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        var sid = menu.dataset.sid || "";
        menu.style.display = "none";
        menu.dataset.sid = "";
        var prefix = "__ctx_" + it.act + "__" + sid;
        var btns = doc.querySelectorAll("button");
        for (var i = 0; i < btns.length; i++) {
          var t = (btns[i].textContent || "").replace(/\s+/g, " ").trim();
          if (t === prefix || t.indexOf(prefix) === 0) {
            btns[i].click();
            return;
          }
        }
      });
      menu.appendChild(b);
    });
    doc.documentElement.appendChild(menu);
    return menu;
  }

  function findSessId(target) {
    var el = target;
    for (var d = 0; el && el !== document.documentElement && d < 14; d++) {
      if (el.getAttribute && el.getAttribute("data-sess-id")) {
        return el.getAttribute("data-sess-id");
      }
      if (el.dataset && el.dataset.sessId) return el.dataset.sessId;
      var prev = el.previousElementSibling;
      var back = 0;
      while (prev && back < 10) {
        if (prev.getAttribute && prev.getAttribute("data-sess-id")) {
          return prev.getAttribute("data-sess-id");
        }
        if (prev.querySelector) {
          var m = prev.querySelector("[data-sess-id]");
          if (m) return m.getAttribute("data-sess-id");
        }
        prev = prev.previousElementSibling;
        back++;
      }
      el = el.parentElement;
    }
    return null;
  }

  function hideCtxButtons(doc) {
    var btns = doc.querySelectorAll("button");
    for (var i = 0; i < btns.length; i++) {
      var t = (btns[i].textContent || "").replace(/\s+/g, " ").trim();
      if (t.indexOf("__ctx_") !== 0) continue;
      var b = btns[i];
      b.setAttribute("aria-hidden", "true");
      b.tabIndex = -1;
      b.style.setProperty("display", "none", "important");
      b.style.setProperty("visibility", "hidden", "important");
      b.style.setProperty("height", "0", "important");
      b.style.setProperty("width", "0", "important");
      b.style.setProperty("padding", "0", "important");
      b.style.setProperty("overflow", "hidden", "important");
      b.style.setProperty("position", "absolute", "important");
      b.style.setProperty("pointer-events", "none", "important");
      var p = b.parentElement, hops = 0;
      while (p && hops < 10) {
        var tid = p.getAttribute && p.getAttribute("data-testid");
        if (tid === "stElementContainer" || tid === "stHorizontalBlock") {
          p.style.setProperty("display", "none", "important");
          p.style.setProperty("height", "0", "important");
          p.style.setProperty("overflow", "hidden", "important");
          p.style.setProperty("margin", "0", "important");
          break;
        }
        p = p.parentElement;
        hops++;
      }
    }
  }

  function annotate(doc) {
    var marks = doc.querySelectorAll("[data-sess-id]");
    for (var i = 0; i < marks.length; i++) {
      var sid = marks[i].getAttribute("data-sess-id");
      var n = marks[i].nextElementSibling, hops = 0;
      while (n && hops < 8) {
        var btn = n.tagName === "BUTTON" ? n : (n.querySelector ? n.querySelector("button") : null);
        if (btn && btn.textContent && btn.textContent.indexOf("__ctx_") !== 0) {
          btn.setAttribute("data-sess-id", sid);
          btn.dataset.sessId = sid;
          break;
        }
        n = n.nextElementSibling;
        hops++;
      }
    }
  }

  function bindDoc(doc) {
    if (!doc || doc.__dsCtxBoundV3) return;
    doc.__dsCtxBoundV3 = true;
    var menu = ensureMenu(doc);

    doc.addEventListener("contextmenu", function (e) {
      if (e.isComposing) return;
      var t = e.target;
      var btn = t && t.closest ? t.closest("button") : null;
      if (btn && btn.dataset && btn.dataset.sessId) {
        e.preventDefault();
        e.stopPropagation();
        menu.dataset.sid = btn.dataset.sessId;
        menu.style.display = "block";
        menu.style.left = Math.max(8, Math.min(e.clientX, window.innerWidth - 180)) + "px";
        menu.style.top = Math.max(8, Math.min(e.clientY, window.innerHeight - 220)) + "px";
        return;
      }
      var sid = findSessId(t);
      if (sid) {
        e.preventDefault();
        e.stopPropagation();
        menu.dataset.sid = sid;
        menu.style.display = "block";
        menu.style.left = Math.max(8, Math.min(e.clientX, window.innerWidth - 180)) + "px";
        menu.style.top = Math.max(8, Math.min(e.clientY, window.innerHeight - 220)) + "px";
        return;
      }
      menu.style.display = "none";
    }, true);

    doc.addEventListener("click", function () {
      menu.style.display = "none";
      menu.dataset.sid = "";
    }, true);
  }

  try { bindDoc(document); } catch (e) {}
  try { if (window.parent && window.parent.document) bindDoc(window.parent.document); } catch (e) {}
  try { if (window.top && window.top !== window.parent && window.top.document) bindDoc(window.top.document); } catch (e) {}

  function tick() {
    try { hideCtxButtons(document); annotate(document); } catch (e) {}
    try {
      if (window.parent && window.parent.document) {
        hideCtxButtons(window.parent.document);
        annotate(window.parent.document);
      }
    } catch (e) {}
  }
  tick();
  setInterval(tick, 350);
})();
"""


def render_ctx_menu_runtime() -> None:
    """注入右键菜单：st.html + 组件 iframe（parent.document 双保险）"""
    key = "_ds_ctx_v3"
    if st.session_state.get(key):
        return
    st.markdown(
        "<style>#ds-ctx-menu button:focus{outline:1px solid var(--accent1)}"
        ".ds-sess-col [data-sess-id]{display:none;height:0;overflow:hidden}</style>",
        unsafe_allow_html=True,
    )
    st.html(f"<script>{_CTX_JS}</script>", unsafe_allow_javascript=True)
    # 同源 iframe 里再绑 parent.document（主文档脚本若被净化时的备份）
    components.html(
        f"<script>try{{{_CTX_JS}}}catch(e){{}}</script>",
        height=0,
    )
    st.session_state[key] = True


def _hidden_action_buttons(sid: str, title: str) -> None:
    """隐藏的 Streamlit 按钮：右键菜单通过文本标签点击它们"""
    safe_title = _html.escape(title[:40])
    if st.button(f"__ctx_rename__{sid}", key=f"ctx_rename_{sid}", help="菜单占位"):
        st.toast(f"重命名「{safe_title}」即将上线", icon="✏️")
    if st.button(f"__ctx_pin__{sid}", key=f"ctx_pin_{sid}", help="菜单占位"):
        st.toast("置顶即将上线", icon="📌")
    if st.button(f"__ctx_share__{sid}", key=f"ctx_share_{sid}", help="菜单占位"):
        st.toast("分享即将上线", icon="↗")
    if st.button(f"__ctx_multi__{sid}", key=f"ctx_multi_{sid}", help="菜单占位"):
        st.toast("多选即将上线", icon="☑")
    if st.button(f"__ctx_delete__{sid}", key=f"ctx_delete_{sid}", help="菜单占位"):
        sessions = st.session_state.get("chat_sessions") or {}
        if sid in sessions:
            del sessions[sid]
            if st.session_state.get("active_session_id") == sid:
                st.session_state["active_session_id"] = None
            st.rerun()


def session_row_attrs(sid: str) -> str:
    return f'<div data-sess-id="{sid}" class="ds-sess-mark"></div>'
