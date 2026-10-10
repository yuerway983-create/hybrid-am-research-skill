"""生成确定性的合成夹具；公式刻意含已知修正项，不能用来证明 LLM 优势。"""
from __future__ import annotations

import csv
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent / "foam-refinement-demo"
COLUMNS = [
    "record_id", "sample_id", "condition_id", "batch_id", "material_id", "context_id",
    "data_kind", "source_ref", "partition", "scale", "temperature_C", "flow_ratio",
    "total_relative_density", "microscale_porosity_fraction", "wall_thickness_um",
    "mean_pore_diameter_um", "response_MPa",
]


def micro_density(temperature: float, flow: float) -> float:
    logit = 0.8 - 0.07 * (temperature - 210) + 2 * (flow - 0.7)
    return 1 / (1 + math.exp(-logit))


def generate() -> Path:
    """显式重建派生 CSV；不修改任务配置或其他文件。"""
    records = []

    def condition(partition: str, scale: str, temperature: float, flow: float,
                  macro: float, micro: float, index: int) -> None:
        total = macro * micro
        eta = (1 - micro) * macro / (1 - total)
        if scale == "micro":
            response = 1000 * 0.95 * micro ** 2.5
        elif scale == "macro":
            response = 1000 * macro ** 1.7
        else:
            baseline = 1000 * 0.95 * micro ** 2.5 * macro ** 1.7
            response = baseline * math.exp(0.6 * eta * (1 - eta))
        identity = f"{partition}-{scale}-{index:03d}"
        # 两个样品各有两个技术重复；对称微扰用于检查合并和条件等权。
        for sample, sample_factor in enumerate((0.995, 1.005), 1):
            for repeat, repeat_factor in enumerate((0.998, 1.002), 1):
                row = dict(zip(COLUMNS[:10], (
                    f"{identity}-s{sample}-r{repeat}", f"{identity}-s{sample}", identity,
                    f"batch-{identity}", "synthetic-foaming-polymer-A", "synthetic-fixed-fdm-context",
                    "synthetic_demo", "examples/generate_foam_fixtures.py", partition, scale,
                )))
                row.update(temperature_C=temperature, flow_ratio=flow,
                           total_relative_density=total, microscale_porosity_fraction=eta,
                           wall_thickness_um=250.0, mean_pore_diameter_um=20.0 if micro < 1 else 0.0,
                           response_MPa=response * sample_factor * repeat_factor)
                records.append(row)

    for partition, temperatures, flows, macro_densities in (
        ("train", (200., 210., 220.), (0.5, 0.7, 0.9), (0.35, 0.55, 0.75)),
        ("holdout", (205., 215.), (0.6, 0.8), (0.45, 0.65)),
    ):
        index = 0
        for temperature in temperatures:
            for flow in flows:
                index += 1
                micro = micro_density(temperature, flow)
                condition(partition, "micro", temperature, flow, 1.0, micro, index)
                for macro_index, macro in enumerate(macro_densities, 1):
                    condition(partition, "hierarchical", temperature, flow, macro, micro,
                              index * 10 + macro_index)
        densities = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8) if partition == "train" else (0.25, 0.45, 0.65)
        for index, macro in enumerate(densities, 1):
            condition(partition, "macro", 210., 0.7, macro, 1.0, index)
    ROOT.mkdir(parents=True, exist_ok=True)
    target = ROOT / "measurements.csv"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(records)
    return target


if __name__ == "__main__":
    print(generate())
