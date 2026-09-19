"""
Solidity 예약어가 식별자(struct명, 변수명, 파라미터명 등)로 쓰인 경우 rename.
preprocess_contraction.py와 별도 — 예약어 충돌만 전담.

Usage:
    python rename_reserved_identifiers.py <file.sol>           # stdout 출력
    python rename_reserved_identifiers.py <file.sol> -o <out>  # 파일 저장
    python rename_reserved_identifiers.py --dir <dir>          # 디렉토리 일괄 처리 (in-place)
"""

import re, sys, argparse, pathlib

# ── 예약어 → 대체명 매핑 ──
# Solidity 예약어이지만 코드에서 식별자로 쓰인 것들
RENAME_MAP = {
    'float': 'FloatStruct',  # Float.sol의 struct float (library Float과 이름 분리)
    'from': '_from',          # ERC20 transferFrom 파라미터
    # 필요 시 추가: 'error': '_error', 'revert': '_revert', etc.
}


def rename_reserved(source: str) -> str:
    """예약어 식별자를 rename. 단어 경계(\b) 기준."""
    result = source
    for old, new in RENAME_MAP.items():
        # 해당 예약어가 식별자로 사용되는지 확인 (단순 존재 체크)
        if re.search(rf'\b{old}\b', result):
            result = re.sub(rf'\b{old}\b', new, result)
    return result


def process_file(filepath: pathlib.Path, in_place: bool = False) -> str:
    source = filepath.read_text(encoding='utf-8')
    processed = rename_reserved(source)
    if in_place:
        filepath.write_text(processed, encoding='utf-8')
    return processed


def main():
    parser = argparse.ArgumentParser(description="Solidity 예약어 식별자 rename")
    parser.add_argument("file", nargs="?", help="단일 .sol 파일")
    parser.add_argument("-o", "--output", help="출력 파일")
    parser.add_argument("--dir", help="디렉토리 일괄 처리 (in-place)")
    args = parser.parse_args()

    if args.dir:
        d = pathlib.Path(args.dir)
        count = 0
        for sol in sorted(d.glob("*.sol")):
            source = sol.read_text(encoding='utf-8')
            processed = rename_reserved(source)
            if processed != source:
                sol.write_text(processed, encoding='utf-8')
                count += 1
                print(f"  renamed: {sol.name}")
        print(f"\n{count} files modified")
    elif args.file:
        processed = process_file(pathlib.Path(args.file))
        if args.output:
            pathlib.Path(args.output).write_text(processed, encoding='utf-8')
            print(f"Saved to {args.output}")
        else:
            print(processed)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
