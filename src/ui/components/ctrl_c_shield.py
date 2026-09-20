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
    if (e.isComposing || e.keyCode === 229) return false;
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

  function looksLikeClearCache(node) {
    var t = (node.textContent || "").toLowerCase();
    return t.indexOf("clear caches") >= 0 || t.indexOf("clear the app") >= 0
        || t.indexOf("清除缓存") >= 0;
  }

  function killClearCacheDialog() {
    // Streamlit 版本间 testid 不稳定：兼容旧组件层 + 新 Dialog
    var selectors = [
      '[data-testid="stClearCacheDialog"]',
      '[data-testid="stDialog"]',
      '[role="dialog"]',
      '[class*="Dialog"]'
    ];
    var seen = [];
    for (var s = 0; s < selectors.length; s++) {
      var list = document.querySelectorAll(selectors[s]);
      for (var i = 0; i < list.length; i++) {
        var node = list[i];
        if (seen.indexOf(node) >= 0) continue;
        seen.push(node);
        if (!looksLikeClearCache(node)) continue;
        var buttons = node.querySelectorAll("button");
        for (var b = 0; b < buttons.length; b++) {
          var label = (buttons[b].textContent || "").trim().toLowerCase();
          if (label === "cancel" || label === "取消" || label === "close" || label === "×") {
            try { buttons[b].click(); } catch (e) {}
            break;
          }
        }
        node.style.setProperty("display", "none", "important");
        // 遮罩
        var parent = node.parentElement;
        if (parent && parent !== document.body) {
          try { parent.style.setProperty("display", "none", "important"); } catch (e) {}
        }
      }
    }
  }
  setInterval(killClearCacheDialog, 300);

  window.__shieldActive = true;
})();
</script>
"""

_SHIELD_CSS = """
[data-testid="stClearCacheDialog"] { display: none !important; }
[data-testid="stClearCacheDialog"] * { display: none !important; }
/* Streamlit 新版 Dialog：按标题隐藏可能误伤其它对话框，仅压 Clear caches 由 JS 处理 */
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
