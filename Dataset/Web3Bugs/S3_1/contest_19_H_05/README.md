# H-05: Approval is not reset if the call to IFulfillHelper fails

**Contest**: 19
**Reference**: https://code4rena.com/reports/2021-07-connext-findings#h-05-approval-is-not-reset-if-the-call-to-ifulfillhelper-fails

## Bug Report

## [[H-05] `Approval` is not reset if the call to `IFulfillHelper` fails](https://github.com/code-423n4/2021-07-connext-findings/issues/31)
_Submitted by pauliax, also found by 0xsanson, cmichel and shw_

The function `fulfill` first approves the `callTo` to transfer an amount of `toSend` tokens and tries to call `IFulfillHelper`, but if the call fails, it transfers these assets directly. However, in such case the approval is not reset, so a malicous `callTo` can pull these tokens later:
```solidity
// First, approve the funds to the helper if needed
    if (!LibAsset.isEther(txData.receivingAssetId) && toSend > 0) {
      require(LibERC20.approve(txData.receivingAssetId, txData.callTo, toSend), "fulfill: APPROVAL_FAILED");
    }

    // Next, call `addFunds` on the helper. Helpers should internally
    // track funds to make sure no one user is able to take all funds
    // for tx
    if (toSend > 0) {
      try
        IFulfillHelper(txData.callTo).addFunds{ value: LibAsset.isEther(txData.receivingAssetId) ? toSend : 0}(
          txData.user,
          txData.transactionId,
          txData.receivingAssetId,
          toSend
        )
      {} catch {
        // Regardless of error within the callData execution, send funds
        // to the predetermined fallback address
        require(
          LibAsset.transferAsset(txData.receivingAssetId, payable(txData.receivingAddress), toSend),
          "fulfill: TRANSFER_FAILED"
        );
      }
    }
```
[Tuesday, August 10, 2021](x-fantastical3://show/calendar/2021-08-18)
Recommend that `approval` should be placed inside the try/catch block or `approval` needs to be reset if the call fails.

**[LayneHaber (Connext) confirmed and patched](https://github.com/code-423n4/2021-07-connext-findings/issues/31#issuecomment-880098587):**
 > https://github.com/connext/nxtp/pull/39


