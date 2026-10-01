"""Report local capabilities only; never install packages or contact services."""
from __future__ import annotations
import importlib.util
import importlib.metadata
import json
import platform
import sys


def main() -> int:
    required={}
    for module,dist in [('numpy','numpy'),('scipy','scipy'),('sklearn','scikit-learn')]:
        present=importlib.util.find_spec(module) is not None
        try:version=importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:version=None
        required[dist]={'discoverable':present,'installed_version':version,'numerical_health_not_tested_by_preflight':True}
    ready=sys.version_info>=(3,11) and all(v['discoverable'] for v in required.values())
    result={'python':platform.python_version(),'stage3_dependencies_ready':ready,'required_packages':required,
            'legacy_v02_standard_library_only':True,'stage3_tested_versions_file':'requirements-calibration.txt',
            'network_tested':False,'llm_runtime_tested':False,'equipment_connected':False,'automatic_installation':False,
            'dedicated_simulation_software_called':False,
            'next_step':'Run python scripts/campaign_demo.py --out <new_directory>' if ready else 'Create an isolated environment and explicitly install requirements-calibration.txt; no auto installation'}
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if ready else 2
if __name__=='__main__':raise SystemExit(main())
