_author_ = "coffeeTonight"                  # 작성자
_date_ = "2024-12-01"                 # 작성일
_last_modified_by_ = "coffeeTonight"        # 최종 수정자
_last_modified_date_ = "2024-12-15"   # 최종 수정일
_version_ = "1.0.0"                   # 버전 정보
_description_ = "verilog AST from GPT"

import re
import os
import json
import sys
import argparse
import logging
from preprocessor import VerilogPreprocessor
import parseFilelist
import verilogParser
import elaboration


_thispath_ = os.path.dirname(__file__)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Verilog AST Parser')
    parser.add_argument('-f', '--filelist', default=f"{_thispath_}/../design/HDLforAST/filelist.f", help='Path to the filelist containing Verilog files')
    parser.add_argument('-o', '--output', default="workdir", help='Output directory for generated AST')
    parser.add_argument('-i', '--include', action='append', help='Include directory for Verilog files (can specify multiple)')
    parser.add_argument('-d', '--define', action='append', help='Define macros for Verilog files (e.g., +define+WIDTH=8)')
    parser.add_argument('-w', '--work', default="workdir_hdlAST", help='Working directory for elaboration and intermediate files')

    # 추가된 옵션들
    parser.add_argument('-s', '--suppress', action='append', help='Suppress specific warnings or errors')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('-t', '--trace', action='store_true', help='Enable signal tracing')
    parser.add_argument('-e', '--elaborate', action='store_true', help='Elaborate the design')
    parser.add_argument('-p', '--param', action='append', help='Set parameters for modules')
    parser.add_argument('-r', '--run', action='store_true', help='Automatically run the simulation after parsing')
    parser.add_argument('-m', '--mode', help='Specify simulation mode (e.g., RTL, gate level)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--no-warn', action='store_true', help='Suppress all warnings')
    parser.add_argument('--max-errors', type=int, help='Maximum number of errors before stopping')
    parser.add_argument('--top', type=str, help='Name of the top module to integrate.')
    parser.add_argument('--loglevel', type=str, default='DEBUG', help='Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).')
    parser.add_argument('--clean', '-c', action='store_true', default=True, help='Clean the output directory before starting.')
    parser.add_argument('--search', type=str, help='Instance name to search for in the hierarchy.')
    args = parser.parse_args()

    flist = parseFilelist.parseFilelist(args.filelist)

    # VerilogParser 인스턴스 생성
    verilog_parser = verilogParser.VerilogParser(flist, f"{args.output}/hdlpars", args.define)
    verilog_parser.run()

    log_level = getattr(logging, args.loglevel.upper(), logging.DEBUG)
    elaboration = elaboration.Elaboration(f'{args.output}/hdlpars', f'{_thispath_}/logs/elab',
                                          f'{args.output}/elab', top_module=args.top, clean_output=args.clean,
                                          log_level=log_level, HDLLOAD=verilog_parser.file_list.hdls)
    integrated_hierarchy = elaboration.integrate_modules()
