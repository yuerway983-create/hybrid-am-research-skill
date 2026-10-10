# Research workflow assets / 研究流程图资源

Added in the v1.1.3 documentation revision. These diagrams describe the overall research workflow; the project's capability status table defines what each current module actually supports.

本目录为 v1.1.3 文档改版新增内容。图示描述总体研究工作流，具体模块实际支持范围以项目能力状态表为准。

| Language / 语言 | Editable source / 可编辑源文件 | Offline SVG / 离线 SVG |
| --- | --- | --- |
| English | [research-workflow.mmd](research-workflow.mmd) | [research-workflow.svg](research-workflow.svg) |
| 简体中文 | [research-workflow.zh-CN.mmd](research-workflow.zh-CN.mmd) | [research-workflow.zh-CN.svg](research-workflow.zh-CN.svg) |

The README Mermaid blocks are copied from these sources. The static page uses the corresponding exported SVGs. Keep source files, README blocks and exports synchronized when changing the workflow.

README 的 Mermaid 代码块与本目录源文件保持一致；静态展示页使用对应 SVG。修改流程图时须同步源文件、README 代码块和导出图。

## Export method / 导出方法

The checked-in SVGs were rendered from the `.mmd` files with **Mermaid 11.17.2**, **Playwright 1.62.1** and local headless Microsoft Edge. The browser was used only as a local renderer; no project service or online diagram service was involved. Dependencies were installed outside the repository and are not required to view the exported files.

本版 SVG 使用 **Mermaid 11.17.2**、**Playwright 1.62.1** 和本机无界面 Microsoft Edge 从 `.mmd` 文件真实渲染。浏览器仅用于本地导出；未启动项目服务，也未使用在线绘图服务。导出依赖安装在仓库外，阅读 SVG 无需安装这些依赖。

The export procedure is:

1. Read the UTF-8 `.mmd` source and compute SHA-256 over its exact file bytes.
2. Load the locally installed `mermaid/dist/mermaid.js` in the browser.
3. Parse the first-line `init` JSON and pass it to `mermaid.initialize`, together with `startOnLoad: false`, `securityLevel: "strict"`, `deterministicIds: true` and the file stem as `deterministicIDSeed`.
4. Call `mermaid.render` with the source; parse the returned SVG as XML and reject XML errors.
5. Add `data-source-file` and `data-source-sha256` to the SVG root, set a white background, and serialize the SVG with one final newline.
6. Render the exported files and check labels, arrow directions, group headings and offline loading.

导出步骤为：读取源文件并计算精确字节哈希 → 加载本地 Mermaid → 使用源文件中的配置初始化渲染器 → 调用 `mermaid.render` 并检查 SVG XML → 写入来源文件和哈希属性 → 检查实际显示效果。

The configuration uses plain SVG text (`htmlLabels: false`), built-in system fonts and embedded styles. Source-owned `themeCSS` moves the workflow and feedback region headings to the left, with line breaks in the longer English headings, so incoming arrows do not cross heading text. The exports include accessible `title` / `desc` text and a responsive `viewBox`; there are no `foreignObject` elements, external images or runtime network dependencies. The source hash is provenance information, not a claim that the scientific workflow is validated for every module.

配置使用纯 SVG 文本、系统字体和内嵌样式；源文件中的 `themeCSS` 将工作流与反馈区标题左移，较长英文标题分行，避免入箭头穿过标题。导出图含 `title` / `desc` 文本与响应式 `viewBox`，无 `foreignObject`、外部图片或运行时网络依赖。源文件哈希用于追溯来源，不代表图中科学流程已在每个模块中得到验证。

## Source SHA-256 / 源文件校验值

| File | SHA-256 |
| --- | --- |
| `research-workflow.mmd` | `e93444c5def9fc2c99013a79c94b3b444101dee00f32e68c8a582b92ce9ced8f` |
| `research-workflow.zh-CN.mmd` | `0cd63ecf22e5b2028d8a4fa9342c90a7e1b6750258fea275f81f5e21fc30fffc` |

Preserve UTF-8 encoding and LF line endings, or regenerate the SVG and recorded source hash after changing file bytes.

请保留 UTF-8 编码及 LF 换行；源文件字节改变后，应重新导出 SVG 并更新来源哈希。
