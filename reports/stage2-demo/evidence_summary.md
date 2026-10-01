# 文献证据包检查

这是已冻结文献记录的离线整理，不是本次重新联网检索。

结构检查：通过。原文含义仍由阅读者核查。

研究问题：Which evidence and lightweight relationships can support analysis of deposition-to-exposure delay in a single hybrid VPP-DIW track?

## 来源与读取范围

### S1 — Hybrid Multimaterial 3D Printing Using Photocuring-While-Dispensing
来源：https://onlinelibrary.wiley.com/doi/full/10.1002/smll.202302405
读取层级：`full_text_html`。
位置：Section 2.1, Eqs. (1)-(3); PDF pp. 3-4, text layer; Section 2.2: double/triple exposure; Section 4: materials, printing parameters and motion synchronization
The article describes delayed photocuring of material deposited in a resin matrix. Section 2.1 assumes one-dimensional Fickian diffusion and gives sigma^2=2Dt. Nearby laser exposure also presents nozzle-clogging considerations. Section 2.2 separates fixation from later layer bonding. These are process and model precedents, not calibrated coefficients or performance results for this project.
局限：Supporting Information request failed; Fig. S5 measurement mapping was not inspected.; PDF text accessible; requested screenshots and binary download failed. No figures were digitized.; No local numeric D or verified concentration-to-geometric-width mapping is supplied.; No speed-to-initial-profile law established for this implementation.

### S2 — Measuring UV curing parameters of commercial photopolymers used in additive manufacturing
来源：https://www.nist.gov/publications/measuring-uv-curing-parameters-commercial-photopolymers-used-additive-manufacturing
读取层级：`abstract_only`。
位置：NIST publication abstract and bibliographic record
The study measures curing parameters across resins, wavelengths and thickness measurement methods. Its abstract supports the need for material- and measurement-specific characterization. It does not supply our material calibration.
局限：Only the institutional abstract was reviewed; full text via PMC was blocked by a browser check.

### S3 — Results of an interlaboratory study on the working curve in vat photopolymerization
来源：https://pmc.ncbi.nlm.nih.gov/articles/PMC10986335/
读取层级：`full_text_html`。
位置：Section 1 Eq. (1) and parameter definitions; Discussion of model assumptions and fitting-range sensitivity; Section 4 conclusion
The working curve relates cure depth to incident radiant exposure using Dp and Ec. The study identifies material/light-source and measurement dependencies, as well as model error. This supports keeping exposure calibration separate from delay and not transferring coefficients without checking conditions.
局限：Not a hybrid VPP-DIW width model.; Working-curve fit does not give complete conversion or interface strength.; No table numbers are used to calibrate the present project.

### S4 — LLM-3D Print: Large Language Models To Monitor and Control 3D Printing
来源：https://arxiv.org/abs/2408.14307v3
读取层级：`user_provided_pdf`。
位置：pp.8-13 information planning and execution; pp.24-25 compression validation; p.31 processing latency
The uploaded version separates observation, information planning, querying, solution planning and execution; it also reports post-print compression comparisons. It provides a workflow analogy, not our diffusion or curing parameters.
局限：Different process and materials.; Not Yang Xu work.

## 对第一个模型的判断

已核查的是模型形式；真实材料的系数、初始剖面及几何观测映射仍需标定。
浓度分布的标准差不等于照片中的轨迹宽度。当前只实现固定条件下的扩散矩计算。

## 当前缺口

- G1: actual material pair and fixed speed/pressure/nozzle conditions → cannot assign diffusivity or a speed-dependent initial profile
- G2: time-resolved calibrated concentration profile or a validated geometric observation model → cannot report physical geometric track width from diffusion sigma
- G3: matching diffusivity and initial profile plus uncertainty and validation range → real-data numerical prediction must stop until calibrated
- G4: measured radiant exposure and material/light-specific working curve → no curing-depth or conversion prediction
- G5: approved nozzle/laser timing safety envelope → shorter delay is not declared automatically feasible
- G6: new independent printed samples and performance tests → no physical improvement claim
