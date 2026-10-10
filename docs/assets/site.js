(() => {
  const supported = new Set(['en', 'zh-CN']);
  function setLanguage(language) {
    const lang = supported.has(language) ? language : 'en';
    document.documentElement.lang = lang;
    document.querySelectorAll('[data-lang]').forEach(node => { node.hidden = node.dataset.lang !== lang; });
    document.querySelectorAll('[data-set-lang]').forEach(button => { button.setAttribute('aria-pressed', String(button.dataset.setLang === lang)); });
    document.title = lang === 'zh-CN' ? 'Axiom Research · 模块化 LLM 辅助研究框架' : 'Axiom Research · Modular LLM-assisted research';
    document.querySelector('.topbar nav').setAttribute('aria-label', lang === 'zh-CN' ? '主导航' : 'Main navigation');
    document.querySelector('.workflow-notes').setAttribute('aria-label', lang === 'zh-CN' ? '研究工作流分工' : 'Workflow responsibilities');
    document.querySelectorAll('a[href="docs/pages/overview.html"], a[href="docs/pages/overview.zh-CN.html"]').forEach(link => {
      link.href = lang === 'zh-CN' ? 'docs/pages/overview.zh-CN.html' : 'docs/pages/overview.html';
    });
    try { localStorage.setItem('axiom-language', lang); } catch {}
  }
  document.querySelectorAll('[data-set-lang]').forEach(button => button.addEventListener('click', () => setLanguage(button.dataset.setLang)));
  let initial = 'en';
  try { initial = localStorage.getItem('axiom-language') || 'en'; } catch {}
  setLanguage(initial);
})();
