# 原 VPP–DIW 模块与历史记录

这里保留原混合增材制造的线宽／扩散研究入口。当前首页按科研建模能力组织，提供分级聚合物泡沫研究示例，见 [README](README.md) 和 [快速开始](START_HERE.md)。本页中的 14 工具、三轮更新、几何宽度与扩散结果属于旧 VPP–DIW 运行时，不代表泡沫模块具备相同能力。

## 历史结果

- [完整三轮合成验收](reports/campaign-steady/index.html)：合成回传、冻结更新、独立合成确认和下一轮。
- [模型失效分支](reports/campaign-shifted/index.html)：失败时转入标定方案。
- [宿主逐步调用记录](reports/host-session-v1/index.html)：29 次工具调用记录，外部数据仍为合成。
- [历史第二轮方案](reports/host-session-v1/next_round/index.html)。
- [v1.0 完成记录](reports/V1_REPORT_ZH.md)：当时的 274 项测试与验证范围。

历史文件保留原始名称、版本与结论。软件验收不是实际打印或材料改善证据；当前包中的完整测试数量及泡沫扩展另见 [foam-0.1 优化验证](reports/foam-0.1-optimization-validation.md)。

## 重跑原流程

在独立虚拟环境中安装旧流程依赖，从完整仓库根目录运行：

```text
python -m pip install -r requirements-agent.txt --index-url https://pypi.tuna.tsinghua.edu.cn/simple
python scripts/preflight.py
python scripts/campaign_demo.py --out runs/demo-1
```

输出目录必须不存在。失败场景可用 `--scenario shifted --rounds 2`，并另选新输出目录。演示不需要 API 密钥，也不会运行真实设备。

固定演示由脚本驱动；LLM 宿主逐步选择工具请读取 [HOST_START.md](HOST_START.md) 中“旧 VPP–DIW v1.0 主控流程”及主 [SKILL.md](SKILL.md) 的旧流程说明。

## 原因分析与数据回传

[hybrid-am-cause-analysis v0.2](skills/hybrid-am-cause-analysis/SKILL.md) 是旧工作流的宿主补充分析。它支持证据、替代原因、区分检查及参数建议，目前未自动注册到 14 工具运行时，也不会自动将诊断候选写入规划器或正式审计。

原运行时支持冻结预测评分、版本化重拟合和独立新确认。开始真实研究时需另建任务，使用真实测量与来源；旧确认数据不能重复宣称为新验证。不要用旧会话绕过代码／输入哈希检查，也不要从几何宽度直接推断界面强度、疲劳寿命或器件性能。

原可选远程 API 驱动仅有本地协议测试，未用真实账户验收。是否联网调用由用户所选宿主和凭据配置决定；新检索来源和外部代码仍需审核。
