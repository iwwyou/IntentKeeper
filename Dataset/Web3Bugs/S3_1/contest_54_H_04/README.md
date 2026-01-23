# H-04: Approvals not cleared after key transfer

**Contest**: 54
**Reference**: https://code4rena.com/reports/2021-11-unlock#h-04-approvals-not-cleared-after-key-transfer

## Bug Report

## [[H-04] Approvals not cleared after key transfer](https://github.com/code-423n4/2021-11-unlock-findings/issues/160)
_Submitted by cmichel_

The locks implement three different approval types, see `onlyKeyManagerOrApproved` for an overview:

*   key manager (map `keyManagerOf`)
*   single-person approvals (map `approved`). Cleared by `_clearApproval` or `_setKeyManagerOf`
*   operator approvals (map `managerToOperatorApproved`)

The `MixinTransfer.transferFrom` requires any of the three approval types in the `onlyKeyManagerOrApproved` modifier on the tokenId to authenticate transfers from `from`.

Notice that if the `to` address previously had a key but it expired only the `_setKeyManagerOf` call is performed, which does not clear `approved` if the key manager was already set to 0:

```solidity
function transferFrom(
  address _from,
  address _recipient,
  uint _tokenId
)
  public
  onlyIfAlive
  hasValidKey(_from)
  onlyKeyManagerOrApproved(_tokenId)
{
  // @audit this is skipped if user had a key that expired
  if (toKey.tokenId == 0) {
    toKey.tokenId = _tokenId;
    _recordOwner(_recipient, _tokenId);
    // Clear any previous approvals
    _clearApproval(_tokenId);
  }

  if (previousExpiration <= block.timestamp) {
    // The recipient did not have a key, or had a key but it expired. The new expiration is the sender's key expiration
    // An expired key is no longer a valid key, so the new tokenID is the sender's tokenID
    toKey.expirationTimestamp = fromKey.expirationTimestamp;
    toKey.tokenId = _tokenId;

    // Reset the key Manager to the key owner
    // @audit  doesn't clear approval if key manager already was 0
    _setKeyManagerOf(_tokenId, address(0));

    _recordOwner(_recipient, _tokenId);
  }
  // ...
}

// 
function _setKeyManagerOf(
  uint _tokenId,
  address _keyManager
) internal
{
  // @audit-ok only clears approved if key manager updated
  if(keyManagerOf[_tokenId] != _keyManager) {
    keyManagerOf[_tokenId] = _keyManager;
    _clearApproval(_tokenId);
    emit KeyManagerChanged(_tokenId, address(0));
  }
}
```

###
