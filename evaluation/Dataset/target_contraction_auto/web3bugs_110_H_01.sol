pragma solidity 0.8.12;

contract StakedCitadel is ERC20Upgradeable, SettAccessControl, PausableUpgradeable, ReentrancyGuardUpgradeable {
    using SafeERC20Upgradeable for IERC20Upgradeable;
    using AddressUpgradeable for address;

    uint256 constant ONE_ETH = 1e18;

    IERC20Upgradeable public token;
    IBadgerGuestlist public guestList;

    bool public pausedDeposit;

    address public strategy;
    address public guardian;
    address public treasury;

    address public badgerTree;
    address public vesting;

    string internal constant _defaultNamePrefix = "Staked ";
    string internal constant _symbolSymbolPrefix = "x";

    uint256 public lifeTimeEarned;
    uint256 public lastHarvestedAt;
    uint256 public lastHarvestAmount;
    uint256 public assetsAtLastHarvest;

    mapping(address => uint256) public additionalTokensEarned;
    mapping(address => uint256) public lastAdditionalTokenAmount;

    uint256 public performanceFeeGovernance;
    uint256 public performanceFeeStrategist;
    uint256 public withdrawalFee;
    uint256 public managementFee;

    uint256 public maxPerformanceFee;
    uint256 public maxWithdrawalFee;
    uint256 public maxManagementFee;

    uint256 public toEarnBps;

    uint256 public constant MAX_BPS = 10_000;
    uint256 public constant SECS_PER_YEAR = 31_556_952;

    uint256 public constant WITHDRAWAL_FEE_HARD_CAP = 200;
    uint256 public constant PERFORMANCE_FEE_HARD_CAP = 3_000;
    uint256 public constant MANAGEMENT_FEE_HARD_CAP = 200;

    function balance() public view returns (uint256) {
        return token.balanceOf(address(this));
    }

}
