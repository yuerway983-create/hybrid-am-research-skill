"""Portable host-LLM bridge. The HOST chooses each tool; CLI does not choose for it."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from round_tools import attach_confirmation
from agent_runtime import (TOOLS,ORIGINS,init_session,attach_feedback,attach_evidence,dispatch,load,verify_audit)


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('tools',help='Show callable function schemas')
    a=sub.add_parser('init');a.add_argument('--task',type=Path,required=True);a.add_argument('--session',type=Path,required=True)
    a.add_argument('--protocol',type=Path,required=True);a.add_argument('--evidence',type=Path);a.add_argument('--origin',choices=ORIGINS,required=True)
    a.add_argument('--update-policy',type=Path)
    a=sub.add_parser('call');a.add_argument('--session',type=Path,required=True);a.add_argument('--tool',required=True)
    a.add_argument('--call-id',required=True);a.add_argument('--origin',choices=ORIGINS,required=True)
    g=a.add_mutually_exclusive_group();g.add_argument('--args',default=None);g.add_argument('--args-file',type=Path)
    a=sub.add_parser('attach-feedback');a.add_argument('--session',type=Path,required=True);a.add_argument('--manifest',type=Path,required=True)
    a=sub.add_parser('attach-confirmation');a.add_argument('--session',type=Path,required=True);a.add_argument('--manifest',type=Path,required=True)
    a=sub.add_parser('attach-evidence');a.add_argument('--session',type=Path,required=True);a.add_argument('--packet',type=Path,required=True)
    a=sub.add_parser('audit');a.add_argument('--session',type=Path,required=True)
    args=p.parse_args()
    try:
        if args.command=='tools':result=TOOLS
        elif args.command=='init':result=init_session(args.task,args.session,protocol_path=args.protocol,origin=args.origin,evidence_path=args.evidence,update_policy_path=args.update_policy)
        elif args.command=='attach-feedback':result=attach_feedback(args.session,args.manifest)
        elif args.command=='attach-confirmation':result=attach_confirmation(args.session,args.manifest)
        elif args.command=='attach-evidence':result=attach_evidence(args.session,args.packet)
        elif args.command=='audit':result=verify_audit(args.session)
        else:
            obj=load(args.args_file) if args.args_file else json.loads(args.args or '{}')
            result=dispatch(args.session,args.tool,obj,args.call_id,origin=args.origin)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2));return 0 if not isinstance(result,dict) or result.get('ok',True) else 2
    except (ValueError,OSError,TypeError,KeyError) as e:
        print(json.dumps({'ok':False,'error':{'code':type(e).__name__,'message':str(e)}},ensure_ascii=False));return 2

if __name__=='__main__':raise SystemExit(main())
