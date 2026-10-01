# 轻量预测模型接口（待实现）

模型可以是已核对的简化公式、真实数据拟合，或经检验的物理+残差组合；不强制ML。
只允许Python轻量数值计算，不调用专用模拟软件。不存在没有依据的“想象模拟”模式。

输入：模型卡、命名工艺参数、固定条件、单位、训练/标定数据标识。
输出：预测值与单位、适用性状态、诊断、可支持的不确定性、输入与版本哈希。

模型卡字段：model_id、kind、equation_or_estimator、assumptions、parameter_sources、
training_data、calibration_method、valid_domain、holdout_strategy、error_metrics、
uncertainty_method、unsupported_outputs、approval_status。

当前包没有模型实现，也不会给示例CSV拟合一个假物理模型。
当实际模型具备时，先用已知解/数值性质做单元测试，再用独立数据做外部验证。
不能在同一张响应面上优化后，再拿这张响应面“证明”真实打印改善。
