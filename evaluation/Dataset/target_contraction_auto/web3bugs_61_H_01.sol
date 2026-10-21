pragma solidity 0.7.6;

contract CreditLine is ReentrancyGuard, OwnableUpgradeable {
    using SafeERC20 for IERC20;
    using SafeMath for uint256;

    enum CreditLineStatus {
        NOT_CREATED, REQUESTED, ACTIVE, CLOSED, CANCELLED, LIQUIDATED
    }

    uint256 public creditLineCounter;

    uint256 constant YEAR_IN_SECONDS = 365 days;

    struct CreditLineVariables {
        CreditLineStatus status;
        uint256 principal;
        uint256 totalInterestRepaid;
        uint256 lastPrincipalUpdateTime;
        uint256 interestAccruedTillLastPrincipalUpdate;
    }

    struct CreditLineConstants {
        address lender;
        address borrower;
        uint256 borrowLimit;
        uint256 idealCollateralRatio;
        uint256 borrowRate;
        address borrowAsset;
        address collateralAsset;
        bool autoLiquidation;
        bool requestByLender;
    }
    mapping(uint256 => mapping(address => uint256)) public collateralShareInStrategy;

    mapping(uint256 => CreditLineVariables) public creditLineVariables;

    mapping(uint256 => CreditLineConstants) public creditLineConstants;

    address public savingsAccount;

    address public priceOracle;

    address public strategyRegistry;

    address public defaultStrategy;

    uint256 public protocolFeeFraction;

    address public protocolFeeCollector;

    uint256 public liquidatorRewardFraction;

    function _borrowTokensToLiquidate(address _borrowAsset, address _collateralAsset, uint256 _totalCollateralTokens) internal view returns (uint256) {
        (uint256 _ratioOfPrices, uint256 _decimals) = IPriceOracle(priceOracle).getLatestPrice(_borrowAsset, _collateralAsset);
        uint256 _borrowTokens = (_totalCollateralTokens.mul(uint256(10**30).sub(liquidatorRewardFraction)).div(10**30).mul(_ratioOfPrices).div(10**_decimals));

        return _borrowTokens;
    }

}
