"""Validate a frozen evidence packet. Offline structure checks, NOT source-truth verification."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
from _core import load_json, write_json, file_hash

FULL = {"full_text_html", "full_text_pdf", "user_provided_pdf"}
ACCESS = FULL | {"abstract_only", "not_retrieved"}


def validate_packet(packet: object) -> dict:
    errors: list[str] = []
    if not isinstance(packet, dict):
        return {"valid": False, "errors": ["packet must be an object"], "scientific_truth_verified_by_program": False}
    if packet.get("schema_version") != "0.2":
        errors.append("schema_version must be 0.2")
    for key in ("packet_id", "question", "creation_mode"):
        if not isinstance(packet.get(key), str) or not packet[key].strip():
            errors.append(f"missing {key}")
    sources = packet.get("sources")
    if not isinstance(sources, list) or not sources:
        sources = []
        errors.append("nonempty sources required")
    source_map: dict[str, dict] = {}
    identifiers: set[str] = set()
    for s in sources:
        if not isinstance(s, dict):
            errors.append("source must be an object")
            continue
        sid = s.get("source_id")
        if not isinstance(sid, str) or not sid.strip() or sid in source_map:
            errors.append("missing or duplicate source_id")
            continue
        source_map[sid] = s
        for field in ("title", "doi_or_identifier", "source_locator", "review_status", "applicability"):
            if not isinstance(s.get(field), str) or not s[field].strip():
                errors.append(f"{sid}: missing {field}")
        loc = urlparse(str(s.get("source_locator", "")))
        if loc.scheme not in {"https", "http"} or not loc.netloc:
            errors.append(f"{sid}: invalid source URL")
        identity = str(s.get("doi_or_identifier", "")).lower().strip()
        if identity in identifiers:
            errors.append(f"{sid}: duplicate source identifier; link reports rather than duplicate sources")
        identifiers.add(identity)
        level = s.get("access_level")
        if level not in ACCESS:
            errors.append(f"{sid}: unsupported access_level")
        locations = s.get("actual_read_locations")
        if level != "not_retrieved" and (not isinstance(locations, list) or not locations or not all(isinstance(x,str) and x.strip() for x in locations)):
            errors.append(f"{sid}: actual read locations required")
        if s.get("local_data_claim") is not False:
            errors.append(f"{sid}: literature is not local measured data")
        equations = s.get("equations_checked", [])
        if not isinstance(equations, list):
            errors.append(f"{sid}: equations_checked must be a list")
        elif equations and level not in FULL:
            errors.append(f"{sid}: cannot mark equations checked from abstract/inaccessible source")
        else:
            for eq in equations:
                if not isinstance(eq, dict) or not all(eq.get(k) for k in ("id", "expression", "locator", "variables")):
                    errors.append(f"{sid}: incomplete equation record")
    claims = packet.get("claims")
    if not isinstance(claims, list) or not claims:
        claims = []
        errors.append("nonempty claims required")
    seen: set[str] = set()
    for c in claims:
        if not isinstance(c,dict):
            errors.append("claim must be an object")
            continue
        cid = c.get("claim_id")
        if not isinstance(cid,str) or not cid.strip() or cid in seen:
            errors.append("missing or duplicate claim_id")
        seen.add(str(cid))
        refs = c.get("source_ids")
        if not isinstance(refs,list) or not refs or any(not isinstance(r,str) or r not in source_map for r in refs):
            errors.append(f"{cid}: unknown or missing source reference")
            refs = []
        status = c.get("status")
        if status not in {"source_supported", "project_inference", "unresolved"}:
            errors.append(f"{cid}: claim status required")
        if not c.get("statement") or not c.get("locator"):
            errors.append(f"{cid}: statement and locator required")
        if c.get("kind") == "inference" and status != "project_inference":
            errors.append(f"{cid}: project inference must not be relabelled a source result")
        if status == "source_supported":
            if any(source_map[r].get("access_level") == "not_retrieved" for r in refs):
                errors.append(f"{cid}: inaccessible source cannot support a read-based claim")
            if c.get("kind") == "equation" and not any(source_map[r].get("access_level") in FULL for r in refs):
                errors.append(f"{cid}: formula requires reviewed full-text basis")
    return {"valid": not errors, "errors": errors, "source_count": len(sources), "claim_count": len(claims),
            "access_counts": {a:sum(s.get('access_level') == a for s in sources if isinstance(s,dict)) for a in sorted(ACCESS)},
            "scientific_truth_verified_by_program": False,
            "scope": "structure and internal consistency only; host must check source content",
            "live_retrieval_performed": False}


def render_summary(packet: dict, result: dict) -> str:
    out = ["# 文献证据包检查", "", "这是已冻结文献记录的离线整理，不是本次重新联网检索。", "",
           f"结构检查：{'通过' if result['valid'] else '失败'}。原文含义仍由阅读者核查。", "",
           f"研究问题：{packet.get('question','')}", "", "## 来源与读取范围", ""]
    for s in packet.get("sources", []):
        if not isinstance(s,dict): continue
        out += [f"### {s.get('source_id')} — {s.get('title')}",
                f"来源：{s.get('source_locator')}", f"读取层级：`{s.get('access_level')}`。",
                "位置：" + "; ".join(s.get("actual_read_locations", [])), s.get("summary", ""),
                "局限：" + "; ".join(s.get("limitations", [])), ""]
    out += ["## 对第一个模型的判断", "",
            "已核查的是模型形式；真实材料的系数、初始剖面及几何观测映射仍需标定。",
            "浓度分布的标准差不等于照片中的轨迹宽度。当前只实现固定条件下的扩散矩计算。", "",
            "## 当前缺口", ""]
    for g in packet.get("unresolved_gaps", []):
        out.append(f"- {g['id']}: {g['need']} → {g['effect']}")
    return "\n".join(out) + "\n"


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--packet", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a=p.parse_args()
    if a.out.exists(): p.error("Output directory exists; use a new run directory")
    try:
        packet=load_json(a.packet)
        result=validate_packet(packet)
        result["packet_sha256"]=file_hash(a.packet)
    except (OSError, ValueError, TypeError) as exc:
        packet={}; result={"valid":False,"errors":[str(exc)],"scientific_truth_verified_by_program":False}
    a.out.mkdir(parents=True)
    write_json(a.out/"evidence_check.json",result)
    if result["valid"]:
        write_json(a.out/"evidence_matrix.json",packet["sources"])
        write_json(a.out/"claim_source_map.json",packet["claims"])
        (a.out/"summary.md").write_text(render_summary(packet,result),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result["valid"] else 2

if __name__ == "__main__": raise SystemExit(main())
