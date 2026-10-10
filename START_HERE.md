# Axiom Research · v1.0：没有真实数据也可以完成软件演示

## 1. 先直接看结果
打开 `reports/campaign-steady/index.html`：完整三轮合成验收。
打开 `reports/campaign-shifted/index.html`：模型失效时不硬预测，而是继续标定计划。
它们是静态文件，没有外部脚本、网络资源、付费调用或设备指令。

## 2. 本地重新运行
建议Python 3.11+，先在项目根目录创建虚拟环境：

```text
python -m venv .venv
```

Windows PowerShell后续用 `.venv\Scripts\python.exe`；macOS/Linux用 `.venv/bin/python`。
下面的python均替换成所选虚拟环境路径：

```text
python -m pip install -r requirements-agent.txt
python scripts/preflight.py
python scripts/campaign_demo.py --out runs/demo-1
python -m unittest discover -s tests -v
```

首次安装依赖可能联网，演示与数值分析无需联网或API密钥。输出目录必须是新的。

## 3. 正常演示发生什么
第一轮：冻结输入和原模型 → 推荐试验 → 测试程序附加独立合成回传 → 原模型评分与同批基准比较。
然后：导出新增训练数据 → 冻结重拟合候选 → 测试程序附加新合成确认数据 → 验收 → 创建第二轮。
第二轮重复上述过程并创建第三轮；第三轮输出新实验表，停在等待外部结果处。
确认数据来自预先定义的人工响应函数，不是把模型预测值复制成“测量”。

## 4. 失败案例
```text
python scripts/campaign_demo.py --out runs/demo-shift --scenario shifted --rounds 2
python scripts/stage4_demo.py --out runs/demo-sparse --sparse
```

模型变差或新确认不通过：不采用新模型、不改误差门槛，下一轮只输出标定/覆盖/基准。
数据不足：保留需要测量的内容，不填造参数响应或置信区间。
任何真实模式都禁止调用synthetic_campaign.py生成测量。

## 5. 真正的主控智能体
固定demo用于软件测试，不代表模型在自主决策。要让宿主逐步选Skill，阅读HOST_START.md。
主控可选14个明确工具；每步find_skills → activate_skill → 执行 → 查看真实返回。
下载版不会自行扫描所有GitHub并安装代码；新文献与新Skill由授权宿主查找、审核和导入。

## 6. 后续有真实数据时
从新research-mode任务开始，复制templates中的任务和回传格式，填真实来源与测量定义。
先标定原模型，推荐方案由人审核并执行。准备更新前必须先评分旧模型、报告负结果。
新候选冻结后，按confirmation_plan进行额外独立确认；在操作者附加数据后才允许数值验收。
测试默认组数仅为原型数值检查要求，不是满足论文统计功效的样本量建议。

当前主要支持sigma或几何宽度，不从它们自动推断固化程度、界面强度、疲劳寿命或器件性能。
