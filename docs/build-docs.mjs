#!/usr/bin/env node
/**
 * Documentation-only HTML exports and consistency checks.
 * Requires Node.js 22+ and marked 17.0.5, resolved from local dependencies or NODE_PATH.
 * Install the renderer outside the repository if desired:
 *   npm install --prefix <docs-tools-directory> marked@17.0.5
 *   NODE_PATH=<docs-tools-directory>/node_modules node docs/build-docs.mjs
 * No web server, runtime registry changes or scientific calculations are involved.
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { Marked } = require('marked');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const github = 'https://github.com/yuerway983-create/axiom-research-skill';
const pages = new Map([
  ['README.md', 'overview.html'],
  ['README.zh-CN.md', 'overview.zh-CN.html'],
  ['START_HERE.md', 'start.html'],
  ['HOST_START.md', 'host.html'],
  ['PACKAGE_GUIDE.md', 'package.html'],
  ['LEGACY_VPP_DIW.md', 'vpp-diw.html'],
  ['docs/RELEASE_DRAFT.md', 'release-draft.html'],
  ['docs/DOCS_VERIFICATION.md', 'verification.html'],
  ['docs/assets/README.md', 'diagram-assets.html'],
]);
const read = file => fs.readFileSync(path.join(root, file), 'utf8').replace(/\r\n/g, '\n');
const sha256 = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const escape = value => String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const plain = value => value.replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').replace(/&[a-z]+;/g, '');
const slug = value => plain(value).toLowerCase().replace(/[^\p{L}\p{N}\p{M}\s_-]/gu, '').replace(/\s/g, '-');
const external = href => /^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(href);
const normal = file => file.split(path.sep).join('/');
const assert = (condition, message) => { if (!condition) throw new Error(message); };
const stats = { markdownFiles: 0, markdownLinks: 0, htmlFiles: 0, htmlLinksAndAssets: 0, checkedAnchors: 0, diagrams: 0 };
const htmlCache = new Map();

function splitLink(href) {
  const hashAt = href.indexOf('#');
  const fragment = hashAt < 0 ? '' : href.slice(hashAt + 1);
  return { pathname: decodeURIComponent((hashAt < 0 ? href : href.slice(0, hashAt)).split('?')[0]), fragment: decodeURIComponent(fragment) };
}
function targetFor(source, href) {
  const { pathname, fragment } = splitLink(href);
  const target = pathname ? normal(path.posix.normalize(path.posix.join(path.posix.dirname(source), pathname))) : source;
  assert(!target.startsWith('../') && !path.isAbsolute(target), 'Out-of-package link: ' + source + ': ' + href);
  return { target, fragment };
}
function rewrite(source, href) {
  if (!href || external(href) || href.startsWith('#')) return href;
  const { target, fragment } = targetFor(source, href);
  const suffix = fragment ? '#' + encodeURI(fragment) : '';
  if (pages.has(target)) return pages.get(target) + suffix;
  if (target === 'index.html' || target.startsWith('docs/assets/')) return normal(path.posix.relative('docs/pages', target)) + suffix;
  assert(fs.existsSync(path.join(root, target)), 'Missing source link: ' + source + ' -> ' + href);
  const kind = fs.statSync(path.join(root, target)).isDirectory() ? 'tree' : 'blob';
  return github + '/' + kind + '/main/' + target.split('/').map(encodeURIComponent).join('/') + suffix;
}
function render(source) {
  if (htmlCache.has(source)) return htmlCache.get(source);
  const used = new Map();
  const parser = new Marked({ gfm: true });
  parser.use({ renderer: {
    heading({ tokens, depth }) {
      const text = this.parser.parseInline(tokens);
      const base = slug(text);
      const count = used.get(base) || 0;
      used.set(base, count + 1);
      return '<h' + depth + ' id="' + escape(base + (count ? '-' + count : '')) + '">' + text + '</h' + depth + '>\n';
    },
    code({ text, lang }) {
      if (lang === 'mermaid' && source.startsWith('README')) {
        const zh = source.includes('zh-CN');
        const stem = zh ? 'research-workflow.zh-CN' : 'research-workflow';
        return '<figure class="document-workflow"><img src="../assets/' + stem + '.svg" alt="' +
          (zh ? '总体研究流程：输入、LLM 辅助分析、人工验证与反馈；含补证据及模型更新回路。' :
            'Overall workflow: inputs, LLM-assisted analysis, human validation and feedback, with evidence and model-update loops.') +
          '"><figcaption><a href="docs/assets/' + stem + '.svg">' +
          (zh ? '打开完整 SVG' : 'Open full SVG') + '</a></figcaption></figure>\n';
      }
      return '<pre><code' + (lang ? ' class="language-' + escape(lang) + '"' : '') + '>' + escape(text) + '</code></pre>\n';
    },
  }});
  const html = parser.parse(read(source)).replace(/\bhref="([^"]+)"/g, (_, href) => 'href="' + escape(rewrite(source, href.replace(/&amp;/g, '&'))) + '"');
  htmlCache.set(source, html);
  return html;
}
function idsFor(file) {
  const text = file.endsWith('.md') ? render(file) : read(file);
  return new Set([...text.matchAll(/\bid=["']([^"']+)["']/g)].map(match => match[1]));
}
function checkLink(source, href, countKey) {
  if (!href || external(href)) return;
  const { target, fragment } = targetFor(source, href.replace(/&amp;/g, '&'));
  assert(fs.existsSync(path.join(root, target)), 'Broken link: ' + source + ' -> ' + href);
  stats[countKey]++;
  if (fragment && /\.(?:md|html)$/.test(target)) {
    assert(idsFor(target).has(fragment), 'Missing anchor: ' + source + ' -> ' + href);
    stats.checkedAnchors++;
  }
}
function checkMarkdown(source) {
  const parser = new Marked();
  const tokens = parser.lexer(read(source));
  parser.walkTokens(tokens, token => {
    if (token.type === 'link' || token.type === 'image') checkLink(source, token.href, 'markdownLinks');
  });
  stats.markdownFiles++;
}
function checkDiagram(language, source) {
  const stem = language === 'en' ? 'research-workflow' : 'research-workflow.zh-CN';
  const bytes = fs.readFileSync(path.join(root, 'docs/assets/' + stem + '.mmd'));
  const mmd = bytes.toString('utf8').trim();
  const svg = read('docs/assets/' + stem + '.svg');
  const content = read(source).split('<!-- workflow:' + language + ':start -->')[1]?.split('<!-- workflow:' + language + ':end -->')[0]?.trim();
  assert(content === '\x60\x60\x60mermaid\n' + mmd + '\n\x60\x60\x60', 'README/Mermaid source mismatch: ' + language);
  assert(svg.includes('data-source-sha256="' + sha256(bytes) + '"'), 'Stale SVG source hash: ' + language);
  assert(svg.includes('<title') && svg.includes('<desc') && svg.includes('viewBox='), 'Missing SVG accessibility/responsiveness: ' + language);
  assert(!/<foreignObject|(?:href|src)=["']https?:/i.test(svg), 'SVG must be self-contained: ' + language);
  for (const edge of ['B --> C --> D --> E --> F --> G', 'F -->|', 'H --> I --> J', 'A --> B', 'G -.-> H', 'J --> D']) {
    assert(mmd.includes(edge), 'Missing workflow edge: ' + language + ' ' + edge);
  }
  stats.diagrams++;
}
function checkHtml(file) {
  const text = read(file);
  const ids = [...text.matchAll(/\bid=["']([^"']+)["']/g)].map(match => match[1]);
  assert(new Set(ids).size === ids.length, 'Duplicate HTML id: ' + file);
  for (const match of text.matchAll(/\b(?:href|src)=["']([^"']+)["']/g)) checkLink(file, match[1], 'htmlLinksAndAssets');
  const allowedVersions = new Set(['v1.1.2', 'v' + read('VERSION').trim()]);
  for (const match of text.matchAll(/releases\/(?:download|tag)\/(v[\d.]+)/g)) {
    assert(allowedVersions.has(match[1]), 'Unexpected release version link: ' + file);
  }
  stats.htmlFiles++;
}

checkDiagram('en', 'README.md');
checkDiagram('zh-CN', 'README.zh-CN.md');
for (const source of [...pages.keys(), 'SKILL.md']) checkMarkdown(source);

{
  fs.mkdirSync(path.join(root, 'docs/pages'), { recursive: true });
  for (const [source, destination] of pages) {
    const zh = source === 'README.zh-CN.md';
    const title = plain(read(source).match(/^# (.+)$/m)?.[1] || 'Axiom Research');
    const html = '<!doctype html>\n<html lang="' + (zh ? 'zh-CN' : 'en') + '"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">' +
      '<title>' + escape(title) + '</title><link rel="stylesheet" href="../assets/docs.css"></head><body>' +
      '<nav aria-label="Documentation"><a href="../../index.html">Axiom Research</a><a href="overview.html">Overview</a><a href="overview.zh-CN.html">中文总览</a><a href="start.html">Start</a><a href="package.html">Package</a></nav>' +
      '<main><p class="export-note">' + (zh ? '本地文档预览 · 来自 ' : 'Offline document · generated from ') + escape(source) +
      '</p>' + render(source) + '</main><footer>Documentation version 1.1.3. Technical GitHub links require a network connection; the Markdown source files remain in this package.</footer></body></html>\n';
    if (process.argv.includes('--check')) {
      assert(read('docs/pages/' + destination) === html, 'Stale HTML export: ' + destination);
    } else {
      fs.writeFileSync(path.join(root, 'docs/pages', destination), html);
    }
  }
}
for (const destination of pages.values()) checkHtml('docs/pages/' + destination);
checkHtml('index.html');
const home = read('index.html');
const enCount = [...home.matchAll(/data-lang="en"/g)].length;
const zhCount = [...home.matchAll(/data-lang="zh-CN"/g)].length;
assert(enCount === zhCount && enCount > 0, 'Unequal bilingual HTML field count');
assert(!/\bhref=["'][^"']*\.md(?:#|["'])/.test(home.replace(/href=["']https:[^"']+["']/g, '')), 'Local Markdown link in home');
assert(!/<(?:script|link|img)[^>]+(?:src|href)=["']https?:/i.test(home), 'Online asset dependency in home');
for (const file of ['README.md', 'README.zh-CN.md']) assert(read(file).includes(file === 'README.md' ? 'README.zh-CN.md' : 'README.md'), 'Missing language switch: ' + file);
console.log(JSON.stringify({ status: 'passed', mode: process.argv.includes('--check') ? 'check' : 'build-and-check', ...stats, bilingualHtmlFieldsPerLanguage: enCount }, null, 2));
