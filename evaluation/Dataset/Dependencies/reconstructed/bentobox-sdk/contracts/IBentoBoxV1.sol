// SPDX-License-Identifier: MIT
// RECONSTRUCTED (IQDebug evaluation): `@sushiswap/bentobox-sdk` publishes no Solidity on npm (every version
// checked) and the 2022-04-abranft snapshot omits it. The members below are exactly those used by the
// target (NFTPairWithOracle.sol); signatures are copied from sushiswap/bentobox master
// (contracts/BentoBox.sol, contracts/MasterContractManager.sol; `balanceOf` is a public mapping there).
// Interfaces emit no bytecode; selectors depend only on these signatures.
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

import "@boringcrypto/boring-solidity/contracts/interfaces/IERC20.sol";

interface IBentoBoxV1 {
    function balanceOf(IERC20, address) external view returns (uint256);

    function deposit(
        IERC20 token_,
        address from,
        address to,
        uint256 amount,
        uint256 share
    ) external payable returns (uint256 amountOut, uint256 shareOut);

    function withdraw(
        IERC20 token_,
        address from,
        address to,
        uint256 amount,
        uint256 share
    ) external returns (uint256 amountOut, uint256 shareOut);

    function transfer(IERC20 token, address from, address to, uint256 share) external;

    function transferMultiple(
        IERC20 token,
        address from,
        address[] calldata tos,
        uint256[] calldata shares
    ) external;

    function toShare(IERC20 token, uint256 amount, bool roundUp) external view returns (uint256 share);

    function setMasterContractApproval(
        address user,
        address masterContract,
        bool approved,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external;
}
