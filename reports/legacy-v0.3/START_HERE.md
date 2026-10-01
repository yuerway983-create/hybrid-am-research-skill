# v0.3 从哪里开始

## 1. 不安装软件也能看演示

打开 `reports/stage3-demo/index.html`。页面没有脚本、外部资源或API请求。
它展示两个合成标定案例及数据不足的分支，不是实时联网的LLM运行。

## 2. 本地运行

在解压后的项目根目录打开终端。建议用Python 3.11+的虚拟环境：

```text
python -m venv .venv
```

Windows PowerShell使用 `.venv\Scripts\python.exe`，macOS/Linux使用 `.venv/bin/python`。
下面命令中的python替换成该环境的python路径即可，无需修改系统环境或运行管理员命令。

```text
python -m pip install -r requirements-calibration.txt
python scripts/preflight.py
python scripts/stage3_demo.py --out runs/demo-03
python -m unittest discover -s tests -v
```

目录已存在时，换一个新名字，程序不会覆盖。分析阶段无需API密钥。

## 3. 独立运行某一条路线

```text
python scripts/calibration_planning.py --task examples/width-calibration-demo/task.json --out runs/width-01
python scripts/calibration_planning.py --task examples/sigma-calibration-demo/task.json --out runs/sigma-01
python scripts/calibration_planning.py --task examples/insufficient-data-demo/task.json --out runs/gap-01
```

## 4. 准备真实数据（不需要现在就有）

复制 `templates/task_geometric_v0.3.json` 或 `task_sigma_v0.3.json`，与对应CSV模板放到同一文件夹。
填写真实材料、context_id、测量定义、可调范围、可达到的步长、目标和事先确定的误差容许值。
JSON中dataset_file必须指向该文件夹内的实际CSV文件名。

每一行要求record_id、sample_id、batch_id、material_pair、context_id、data_kind、source_ref、partition、
参数列和response_um。响应单位固定μm；转换需在导入前完成并记录来源。不自动猜单位。
partition只接受fit和holdout。划分应在查看拟合结果之前确定，样品和指定独立组不能跨区。
同一样品同一条件的多次测量会先取均值，不增加独立重复数。

模板故意不能直接通过验证，不能拿合成系数填充真实材料的未知值。
真实模式检查的是记录一致性，不自动认证输入的真实性或设备参数的安全性。

## 5. 看哪些输出

- summary.md：分析与下一轮计划。
- calibration.json：实际模型、每折组别、CV/留出误差和检查失败原因。
- next_experiments.csv：待执行参数、试验目的和随机次序。
- candidate_predictions.csv：计算过的候选，训练域外预测为空。
- measurement_import_template.csv：只有表头的未来测量模板，没有编造的“新结果”。
- events.jsonl：本地适配器、执行函数、源代码哈希和执行状态。

## 6. 本版不是正式闭环实验结论

数据充分且预定误差检查通过后，程序只提出待验证参数；新参数需独立制样测量。
失败时不自动调低阈值。CV误差不等于预测区间，覆盖试验不等于最优信息增益。
如果反复根据同一留出集修改模型，这个留出集会变成开发集；必须另留最终确认数据。
下一阶段接真实智能体宿主的工具调用及可追溯的新结果回传，不必继续增加预测算法。
