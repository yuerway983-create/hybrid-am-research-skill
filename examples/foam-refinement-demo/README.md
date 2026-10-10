# 合成泡沫计算案例

此目录不包含真实 PLA 或发泡实验数据。基体模量 1000 MPa、两级系数和指数、温度—出料倍率密度关系及修正项都是软件夹具预设值。

从仓库根目录运行：

```text
python scripts/foam_model.py run --task examples/foam-refinement-demo/task.json --out outputs/foam-demo-1
```

输出目录必须不存在，避免覆盖原有结果。此命令不调用 LLM API、设备、Abaqus 或 COMSOL。

如需复建派生 CSV，可显式运行 `python examples/generate_foam_fixtures.py`。该命令仅重建本目录的 `measurements.csv`，不会改任务配置。夹具真值为 `C_micro=0.95, n_micro=2.5, C_macro=1.0, n_macro=1.7`。分级响应刻意包含 `exp(0.6 × eta × (1-eta))` 修正。因此其结果只能检验拟合和数据隔离实现，不能证明修正项适用于真实材料，更不能证明 LLM 比普通建模更好。

训练及留出使用不同条件和批次标识；每个条件有两个合成样品，每个样品有两次技术重复。真实研究需要实际独立样品、来源与一致的测量定义，不可只修改 `data_kind` 把本夹具当成实验。
