"""Ctrl+C / 复制 不再弹 Clear caches —— 全 UI 生效

Streamlit 裸键 `c` 会劫持 Ctrl+C 复制。防护：
1. capture 截停 Ctrl/Cmd+C/X
2. 主题 CSS 常驻隐藏弹窗
3. 低频轮询（非 MutationObserver）自动关弹窗

注意：脚本只注入一次。全页 MutationObserver + 每轮 st.html 重插
会在输入时反复扰动 DOM，导致**输入法候选框闪烁**。
"""

import streamlit as st

_SHIELD_JS = r"""
<script>
(function () {
  if (window.__ctrlCShieldBound) return;
  window.__ctrlCShieldBound = true;

  function isCopyShortcut(e) {
    if (!e) return false;
    if (e.isComposing || e.keyCode === 229) return false; // IME 组字中不拦
    if (!(e.ctrlKey || e.metaKey)) return false;
    if (e.altKey) return false;
    var k = (e.key || "").toLowerCase();
    if (k === "c" || k === "x" || k === "keyc" || k === "keyx") return true;
    if (e.keyCode === 67 || e.keyCode === 88) return true;
    if (e.code === "KeyC" || e.code === "KeyX") return true;
    return false;
  }

  function onKey(e) {
    if (!isCopyShortcut(e)) return;
    try { e.stopImmediatePropagation(); } catch (err) {}
    try { e.stopPropagation(); } catch (err) {}
  }

  window.addEventListener("keydown", onKey, true);
  document.addEventListener("keydown", onKey, true);

  /* 低频轮询关弹窗（避免全页 DOM 监听在每次抖动时跑查询） */
  function killClearCacheDialog() {
    var nodes = document.querySelectorAll('[data-testid="stClearCacheDialog"]');
    for (var n = 0; n < nodes.length; n++) {
      var node = nodes[n];
      var buttons = node.querySelectorAll("button");
      for (var i = 0; i < buttons.length; i++) {
        var label = (buttons[i].textContent || "").trim().toLowerCase();
        if (label === "cancel" || label === "取消" || label === "close") {
          buttons[i].click();
          break;
        }
      }
      node.style.setProperty("display", "none", "important");
    }
  }
  setInterval(killClearCacheDialog, 400);

  window.__shieldActive = true;
})();
</script>
"""

_SHIELD_CSS = """
[data-testid="stClearCacheDialog"] { display: none !important; }
[data-testid="stClearCacheDialog"] * { display: none !important; }
/* 输入法：减少输入框所在层的重排闪烁 */
[data-testid="stChatInput"] { contain: layout style; }
"""


def get_shield_css() -> str:
    return _SHIELD_CSS


def render_ctrl_c_shield() -> None:
    """每会话只注入一次脚本（监听器挂在 window/document，节点移除后仍有效）。"""
    if st.session_state.get("_ctrl_c_shield_injected"):
        return
    st.html(_SHIELD_JS, unsafe_allow_javascript=True)
    st.session_state["_ctrl_c_shield_injected"] = True
