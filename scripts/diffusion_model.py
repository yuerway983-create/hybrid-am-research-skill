"""Fixed-condition concentration-profile diffusion moments. No print-width prediction."""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path
from _core import load_json, write_json, file_hash, finite_number

UNITS = {"length":{"um":1.0,"mm":1000.0,"m":1e6},
         "diffusivity":{"um2/s":1.0,"mm2/s":1e6,"m2/s":1e12},
         "time":{"s":1.0,"ms":0.001}}
OBSERVABLES={"concentration_sigma_um", "concentration_variance_um2", "concentration_fwhm_um"}
ASSUMPTIONS=("homogeneous_1d", "unbounded_domain", "constant_diffusivity", "pre_gel_only", "advection_ignored")


def scalar(item: object, kind: str) -> float:
    if not isinstance(item,dict) or not finite_number(item.get("value")):
        raise ValueError(f"{kind} requires a finite numeric value (not a boolean)")
    if item.get("unit") not in UNITS[kind]:
        raise ValueError(f"Unsupported {kind} unit: {item.get('unit')}")
    value=float(item["value"])*UNITS[kind][item["unit"]]
    if not math.isfinite(value) or value<0:
        raise ValueError(f"{kind} must be finite and nonnegative after conversion")
    if not isinstance(item.get("source_ref"),str) or not item["source_ref"].strip():
        raise ValueError(f"{kind} needs source_ref; no implicit material constants")
    return value


def moments(sigma0_um: float, diffusivity_um2_s: float, time_s: float) -> dict:
    if any(not finite_number(v) or v<0 for v in (sigma0_um,diffusivity_um2_s,time_s)):
        raise ValueError("Moment inputs must be finite nonnegative numbers")
    try:
        variance=sigma0_um*sigma0_um+2.0*diffusivity_um2_s*time_s
        if not math.isfinite(variance): raise ValueError("Numerical overflow")
        sigma=math.sqrt(variance)
        fwhm=2*math.sqrt(2*math.log(2))*sigma
    except OverflowError as exc:
        raise ValueError("Numerical overflow") from exc
    return {"concentration_variance_um2":variance,"concentration_sigma_um":sigma,"concentration_fwhm_um":fwhm}


def evaluate_case(case: object, base_dir: Path | None=None) -> dict:
    result={"schema_version":"0.2","status":"blocked","prediction_performed":False,
            "physical_validation_performed":False,"geometric_width_predicted":False,
            "dedicated_simulation_software_called":False,"hardware_commands_sent":False,
            "model_id":"M1_gaussian_diffusion_moments","errors":[],"rows":[]}
    errors=result["errors"]
    if not isinstance(case,dict):
        errors.append("case must be an object");return result
    result.update(mode=case.get("mode"),data_kind=case.get("data_kind"),task_id=case.get("task_id"))
    if case.get("schema_version")!="0.2": errors.append("schema_version must be 0.2")
    if not isinstance(case.get("task_id"),str) or not case["task_id"].strip(): errors.append("task_id is required")
    if case.get("observable") not in OBSERVABLES:
        errors.append("Only concentration moments are supported. Geometric track width/strength requires a separate calibrated observation model.")
    if case.get("process")!="hybrid-vpp-diw": errors.append("process context must be hybrid-vpp-diw")
    if not isinstance(case.get("material_pair"),str) or not case["material_pair"].strip(): errors.append("material_pair is required")
    fixed=case.get("fixed_conditions")
    if not isinstance(fixed,dict) or not fixed: errors.append("Fixed process conditions required; no speed-dependent initial-profile model exists")
    if case.get("mode") not in {"offline_demo","research"}: errors.append("mode must be offline_demo or research")
    if case.get("data_kind") not in {"synthetic_demo","measured","public_measured"}: errors.append("data_kind required")
    if case.get("mode")=="offline_demo" and case.get("data_kind")!="synthetic_demo": errors.append("offline_demo must be labelled synthetic_demo")
    if case.get("mode")=="research" and case.get("data_kind")=="synthetic_demo": errors.append("Synthetic parameters cannot be research data")
    perms=case.get("allow",{})
    if not isinstance(perms,dict) or any(perms.get(k) is not False for k in ("hardware_commands","dedicated_simulation_software")):
        errors.append("hardware and dedicated simulation permissions must both be false")
    assumption=case.get("assumptions",{})
    if not isinstance(assumption,dict) or any(assumption.get(k) is not True for k in ASSUMPTIONS) or assumption.get("initial_distribution")!="gaussian":
        errors.append("Explicit Gaussian, homogeneous unbounded 1D, constant-D, pre-gel and no-advection assumptions required")
    if case.get("time_reference")!="elapsed_since_reference_profile": errors.append("time_reference must be elapsed_since_reference_profile")
    params=case.get("parameters",{})
    try:
        if not isinstance(params,dict): raise ValueError("parameters must be object")
        s0=scalar(params.get("sigma0"),"length")
        d=scalar(params.get("diffusivity"),"diffusivity")
        for name in ("sigma0","diffusivity"):
            origin=params[name].get("origin")
            expected="synthetic_demo" if case.get("mode")=="offline_demo" else "user_calibration"
            if origin!=expected: errors.append(f"{name} origin must be {expected}")
    except (ValueError,TypeError,KeyError) as exc:
        errors.append(str(exc));s0=d=None
    tm=case.get("evaluation_times",{})
    ts=[]
    if not isinstance(tm,dict) or tm.get("unit") not in UNITS["time"] or not isinstance(tm.get("values"),list) or not 1<=len(tm["values"])<=1000:
        errors.append("evaluation_times requires 1..1000 values in s or ms")
    else:
        for v in tm["values"]:
            if not finite_number(v) or v<0: errors.append("Times must be finite nonnegative numbers");continue
            vv=float(v)*UNITS["time"][tm["unit"]]
            if not math.isfinite(vv): errors.append("Converted time overflow")
            else: ts.append(vv)
    domain=case.get("time_domain_s")
    if not isinstance(domain,list) or len(domain)!=2 or not all(finite_number(v) for v in domain) or domain[0]<0 or domain[0]>=domain[1]:
        errors.append("Explicit nonnegative increasing time_domain_s required")
    elif any(not domain[0]<=t<=domain[1] for t in ts):
        errors.append("Requested time outside declared validity interval; no silent extrapolation")
    if case.get("mode")=="research":
        ref=case.get("calibration_file")
        try:
            if not isinstance(ref,str) or not ref or base_dir is None: raise ValueError("Research calculation needs a reviewed calibration_file")
            root=base_dir.resolve(); target=(root/ref).resolve()
            if Path(ref).is_absolute() or not target.is_relative_to(root): raise ValueError("calibration_file must stay within case folder")
            cal=load_json(target)
            if not isinstance(cal,dict): raise ValueError("Calibration file must be object")
            for key,expected in [("material_pair",case.get("material_pair")),("fixed_conditions",fixed),("data_kind",case.get("data_kind")),("parameters",params),("time_domain_s",domain)]:
                if cal.get(key)!=expected: raise ValueError(f"Calibration context mismatch: {key}")
            if cal.get("review_status")!="reviewed" or cal.get("observable")!="concentration_sigma_um" or not cal.get("evidence_refs"):
                raise ValueError("Calibration must identify reviewed concentration-sigma measurements and evidence refs")
            result["calibration_sha256"]=file_hash(target)
            result["calibration_note"]="A supplied review record is checked for consistency; the program does not authenticate empirical validity."
        except (ValueError,OSError,TypeError) as exc: errors.append(str(exc))
    bounds=case.get("diffusivity_scenario_bounds")
    db=None
    if bounds is not None:
        try:
            if not isinstance(bounds,dict) or bounds.get("unit") not in UNITS["diffusivity"]: raise ValueError("Scenario bounds require supported diffusivity unit")
            vals=bounds.get("values")
            if not isinstance(vals,list) or len(vals)!=2 or not all(finite_number(x) and x>=0 for x in vals): raise ValueError("Scenario bounds need two finite nonnegative values")
            db=[float(x)*UNITS["diffusivity"][bounds["unit"]] for x in vals]
            if not all(math.isfinite(x) for x in db) or db[0]>db[1] or (d is not None and not db[0]<=d<=db[1]): raise ValueError("Invalid scenario interval")
            if not bounds.get("source_ref"): raise ValueError("Scenario bounds require source_ref")
        except (ValueError,TypeError) as exc:errors.append(str(exc))
    if errors:
        result["next_action"]="Provide valid inputs and matching calibration; do not invent missing values or map geometric width to sigma."
        return result
    try:
        for t in ts:
            row={"elapsed_time_s":t,**moments(s0,d,t)}
            if db:
                row["sigma_scenario_lower_um"]=moments(s0,db[0],t)["concentration_sigma_um"]
                row["sigma_scenario_upper_um"]=moments(s0,db[1],t)["concentration_sigma_um"]
            result["rows"].append(row)
    except ValueError as exc:
        result["rows"]=[];errors.append(str(exc));return result
    result.update(status="synthetic_calculation_complete" if case["mode"]=="offline_demo" else "conditional_calculation_complete",
                  prediction_performed=True,model_form="sigma(t)^2 = sigma0^2 + 2*D*t",
                  evidence_refs=["S1 Section 2.1 Eq.(2)","C2 explicit project finite-initial-width extension"],
                  validated_physics=False,
                  uncertainty={"type":"parameter_scenario_envelope_not_confidence_interval" if db else "not_quantified",
                               "excludes":["model discrepancy","observation-map error","unprovided measurement uncertainty"],"coverage_probability":None},
                  not_predicted=["geometric_track_width","cure_depth","conversion","nozzle_clogging_probability","interface_strength","fatigue_life"],
                  next_action="Acquire actual material calibration and a geometric observation map before process optimisation.")
    return result


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--case",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():p.error("Output exists; use a new run directory")
    try:
        result=evaluate_case(load_json(a.case),a.case.parent)
        result["case_sha256"]=file_hash(a.case)
    except (OSError,ValueError,TypeError) as exc:
        result={"status":"blocked","prediction_performed":False,"errors":[str(exc)],"rows":[]}
    a.out.mkdir(parents=True)
    write_json(a.out/"result.json",result)
    if result.get("rows"):
        with (a.out/"moments.csv").open('w',encoding='utf-8',newline='') as h:
            w=csv.DictWriter(h,fieldnames=list(result['rows'][0]));w.writeheader();w.writerows(result['rows'])
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result.get("prediction_performed") else 2

if __name__ == "__main__":raise SystemExit(main())
