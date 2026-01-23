# H-02: The expiry of the parent node can be smaller than the one of a child node

**Contest**: 145
**Reference**: violating the guarantee policy"

## Bug Report

## [[H-02] The expiry of the parent node can be smaller than the one of a child node, violating the guarantee policy](https://github.com/code-423n4/2022-07-ens-findings/issues/187)
*Submitted by PwnedNoMore*

[NameWrapper.sol#L504](https://github.com/code-423n4/2022-07-ens/blob/ff6e59b9415d0ead7daf31c2ed06e86d9061ae22/contracts/wrapper/NameWrapper.sol#L504)<br>
[NameWrapper.sol#L356](https://github.com/code-423n4/2022-07-ens/blob/ff6e59b9415d0ead7daf31c2ed06e86d9061ae22/contracts/wrapper/NameWrapper.sol#L356)<br>

By design, the child node's expiry can only be extended up to the parent's current one. Adding these restrictions means that the ENS users only have to look at the name itself's fuses and expiry (without traversing the hierarchy) to understand what guarantees the users have.

When a parent node tries to `setSubnodeOwner` / `setSubnodeRecord`, the following code is used to guarantee that the new expiry can only be extended up to the current one.

```solidity
function _getDataAndNormaliseExpiry(
    bytes32 parentNode,
    bytes32 node,
    uint64 expiry
)
    internal
    view
    returns (
        address owner,
        uint32 fuses,
        uint64
    )
{
    uint64 oldExpiry;
    (owner, fuses, oldExpiry) = getData(uint256(node));
    (, , uint64 maxExpiry) = getData(uint256(parentNode));
    expiry = _normaliseExpiry(expiry, oldExpiry, maxExpiry);
    return (owner, fuses, expiry);
}
```

However, the problem shows when

*   The sub-domain (e.g., `sub1.base.eth`) has its own sub-sub-domain (e.g., `sub2.sub1.base.eth`)
*   The sub-domain is unwrapped later, and thus its `oldExpiry` becomes zero.
*   When `base.eth` calls `NameWrapper.setSubnodeOwner`, there is not constraint of `sub1.base.eth`'s expiry, since `oldExpiry == 0`. As a result, the new expiry of `sub1.base.eth` can be arbitrary and smaller than the one of `sub2.sub1.base.eth`

The point here is that the `oldExpiry` will be set as 0 when unwrapping the node even it holds child nodes, relaxing the constraint.

Specifically, considering the following scenario

*   The hacker owns a domain (or a 2LD), e.g., `base.eth`
*   The hacker assigns a sub-domain to himself, e.g., `sub1.base.eth`
    *   The expiry should be as large as possible
*   Hacker assigns a sub-sub-domain, e.g., `sub2.sub1.base.eth`
    *   The expiry should be as large as possible
*   The hacker unwraps his sub-domain, i.e., `sub1.base.eth`
*   The hacker re-wraps his sub-domain via `NameWrapper.setSubnodeOwner`
    *   The expiry can be small than the one of sub2.sub1.base.eth

The root cause *seems* that we should not zero out the expiry when burning a node if the node holds any subnode.

##
