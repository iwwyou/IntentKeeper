# 케이스 레코드 수정 내역

원본 = `_original_backup/<case_id>.json` (수정 전 IntentChecker 판). 생성: `evaluation/intent_validation/apply_case_edits.py`.

## web3bugs_16_H_04 (2026-10-21)
- rec#37 L49-50: '} else if …' → 'else if …' + closeBefore=True

## web3bugs_36_H_02 (2026-10-21)
- rec#48 @Post startLine 58 → 52 (타깃 'auctionBurn' 닫는 줄)

## web3bugs_47_H_02 (2026-10-21)
- rec#26 @Post startLine 32 → 28 (타깃 'transferFrom' 닫는 줄)
