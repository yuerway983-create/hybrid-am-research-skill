"""Exact algebra/calculus checks for the explicit Gaussian initial-profile extension."""
from __future__ import annotations
import argparse
import platform
from pathlib import Path
from _core import write_json


def verify() -> dict:
    import sympy as s
    # Fixed real centre; free diffusion in an unbounded 1D domain with constant positive D.
    x=s.symbols('x',real=True)
    D,t,sigma0=s.symbols('D t sigma0',positive=True)
    V=sigma0**2+2*D*t
    c=s.exp(-x**2/(2*V))/s.sqrt(2*s.pi*V)  # Unit-area concentration profile.
    residual=s.simplify(s.diff(c,t)-D*s.diff(c,x,2))
    mass=s.simplify(s.integrate(c,(x,-s.oo,s.oo)))
    mean=s.simplify(s.integrate(x*c,(x,-s.oo,s.oo)))
    second=s.simplify(s.integrate(x*x*c,(x,-s.oo,s.oo)))
    L,T=s.symbols('L T',positive=True)
    units_ok=s.simplify((L**2/T)*T-L**2)==0
    tests={'diffusion_pde_residual_zero':residual==0,
           'unit_mass':mass==1,'centre_preserved':mean==0,
           'second_moment_matches':s.simplify(second-V)==0,
           'initial_variance':s.simplify(V.subs(t,0)-sigma0**2)==0,
           'line_source_limit':s.simplify(s.limit(V,sigma0,0)-2*D*t)==0,
           'variance_growth':s.diff(V,t)==2*D,
           'dimension_consistency':units_ok}
    return {'status':'passed' if all(v for v in tests.values()) else 'failed','checks':tests,
            'sympy_version':s.__version__,'python_version':platform.python_version(),
            'model_extension':'finite Gaussian initial profile added explicitly by this project',
            'source_form':'S1 Eq.(2), sigma^2=2Dt for line-source variance',
            'scientific_scope':'mathematical verification, not material calibration or physical validation',
            'physical_validation_performed':False,'dedicated_simulation_software_called':False}


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():p.error('Output exists; choose new path')
    try:r=verify()
    except ImportError:r={'status':'dependency_missing','required':'sympy','physical_validation_performed':False}
    write_json(a.out,r);print(r['status'])
    return 0 if r['status']=='passed' else 2

if __name__=='__main__':raise SystemExit(main())
