# 合成扩散矩计算示例

这里的 `sigma0=50 um`、`D=40 um2/s`、时间区间和情景上下界都是任意软件测试值，
不来自论文、教师课题组或真实测量，不能作为打印参数使用。

脚本计算浓度分布的方差、标准差和高斯分布的半高全宽。它不预测几何轨迹宽度、
固化状态、界面强度或打印机安全性。假设仅用于数学演示，不是实验验证。

- `case.json`：数值流程示例。
- `missing-calibration.json`：缺少系数，应停止且不产生预测行。
- `wrong-observable.json`：要求几何宽度，应停止，而不是偷偷把 sigma 改名为 width。

```text
python scripts/diffusion_model.py --case examples/diffusion-demo/case.json --out runs/numeric-01
```

从项目根目录运行。输出目录必须未被使用。
