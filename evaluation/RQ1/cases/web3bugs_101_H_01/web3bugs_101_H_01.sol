pragma solidity 0.7.6;
pragma abicoder v2;

contract LenderPool is ERC1155Upgradeable, ReentrancyGuardUpgradeable, IPooledCreditLineEnums, ILenderPool {
    using SafeMath for uint256;
    using SafeERC20 for IERC20;

    ISavingsAccount public immutable SAVINGS_ACCOUNT;
    IPooledCreditLine public immutable POOLED_CREDIT_LINE;
    IVerification public immutable VERIFICATION;
    uint256 constant SCALING_FACTOR = 1e18;

    struct LenderInfo {
        uint256 borrowerInterestSharesWithdrawn;
        uint256 yieldInterestWithdrawnShares;
    }

    struct LenderPoolConstants {
        uint256 startTime;
        address borrowAsset;
        address collateralAsset;
        uint256 borrowLimit;
        uint256 minBorrowAmount;
        address lenderVerifier;
        address borrowAssetStrategy;
        bool areTokensTransferable;
    }

    struct LenderPoolVariables {
        mapping(address => LenderInfo) lenders;
        uint256 sharesHeld;
        uint256 borrowerInterestShares;
        uint256 borrowerInterestSharesWithdrawn;
        uint256 yieldInterestWithdrawnShares;
        uint256 collateralHeld;
    }

    mapping(uint256 => LenderPoolConstants) public pooledCLConstants;
    mapping(uint256 => LenderPoolVariables) public pooledCLVariables;
    mapping(uint256 => uint256) public totalSupply;

    function _calculatePrincipalWithdrawable(uint256 _id, address _lender) private view returns (uint256) {       
        uint256 _borrowedTokens = pooledCLConstants[_id].borrowLimit;
        uint256 _totalLiquidityWithdrawable = _borrowedTokens.sub(POOLED_CREDIT_LINE.getPrincipal(_id));       
        uint256 _principalWithdrawable = _totalLiquidityWithdrawable.mul(balanceOf(_lender, _id)).div(_borrowedTokens);
        return _principalWithdrawable;
    }
}
