pragma solidity ^0.6.11;
pragma experimental ABIEncoderV2;

contract MyStrategy is BaseStrategy {
    using SafeERC20Upgradeable for IERC20Upgradeable;
    using AddressUpgradeable for address;
    using SafeMathUpgradeable for uint256;

    uint256 MAX_BPS = 10_000;

    address public lpComponent;
    address public reward;
    address public constant WETH = 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2;
    address public constant CVX = 0x4e3FBD56CD56c3e72c1403e103b45Db9da5B9D2B;

    address public constant SUSHI_ROUTER = 0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F;

    IDelegateRegistry public constant SNAPSHOT = IDelegateRegistry(0x469788fE6E9E9681C6ebF3bF78e7Fd26Fc015446);

    address public constant DELEGATE = 0xB65cef03b9B89f99517643226d76e286ee999e77;

    bytes32 public constant DELEGATED_SPACE = 0x6376782e65746800000000000000000000000000000000000000000000000000;

    ICvxLocker public LOCKER;

    ISettV3 public CVX_VAULT = ISettV3(0x53C8E199eb2Cb7c01543C137078a038937a68E40);

    bool public withdrawalSafetyCheck = true;
    bool public harvestOnRebalance = true;
    bool public processLocksOnReinvest = true;
    bool public processLocksOnRebalance = true;

    function wantToCVX(uint256 _want) public view returns (uint256) {
        uint256 bCVXToCVX = CVX_VAULT.getPricePerFullShare();
        return _want.mul(bCVXToCVX).div(10**18);
    }

    function harvest() public whenNotPaused returns (uint256 harvested) {
        _onlyAuthorizedActors();

        uint256 _before = IERC20Upgradeable(want).balanceOf(address(this));

        uint256 _beforeCVX = IERC20Upgradeable(reward).balanceOf(address(this));

        LOCKER.getReward(address(this), false);

        uint256 earnedReward = IERC20Upgradeable(reward).balanceOf(address(this)).sub(_beforeCVX);

        (uint256 governancePerformanceFee, uint256 strategistPerformanceFee) = _processRewardsFees(earnedReward, reward);

        _swapcvxCRVToWant();

        uint256 earned = IERC20Upgradeable(want).balanceOf(address(this)).sub(_before);

        emit Harvest(earned, block.number);

        return earned;
    }

    function _swapcvxCRVToWant() internal {
        uint256 toSwap = IERC20Upgradeable(reward).balanceOf(address(this));

        if (toSwap == 0) {
            return;
        }

        address[] memory path = new address[](3);
        path[0] = reward;
        path[1] = WETH;
        path[2] = CVX;
        IUniswapRouterV2(SUSHI_ROUTER).swapExactTokensForTokens(toSwap, 0, path, address(this), now);

        uint256 toDeposit = IERC20Upgradeable(CVX).balanceOf(address(this));
        if (toDeposit > 0) {
            CVX_VAULT.deposit(toDeposit);
        }
    }

    function _processRewardsFees(uint256 _amount, address _token) internal returns (uint256 governanceRewardsFee, uint256 strategistRewardsFee) {
        governanceRewardsFee = _processFee(_token, _amount, performanceFeeGovernance, IController(controller).rewards());

        strategistRewardsFee = _processFee(_token, _amount, performanceFeeStrategist, strategist);
    }

    function manualRebalance(uint256 toLock) external whenNotPaused {
        _onlyGovernance();
        require(toLock <= MAX_BPS, "Max is 100%");

        if (processLocksOnRebalance) {
            LOCKER.processExpiredLocks(false);
        }

        if (harvestOnRebalance) {
            harvest();
        }

        uint256 balanceOfWant = IERC20Upgradeable(want).balanceOf(address(this));
        uint256 balanceOfCVX = IERC20Upgradeable(CVX).balanceOf(address(this));
        uint256 balanceInLock = LOCKER.balanceOf(address(this));
        uint256 totalCVXBalance = balanceOfCVX.add(balanceInLock).add(wantToCVX(balanceOfWant));

        uint256 currentLockRatio = balanceInLock.mul(10**18).div(totalCVXBalance);
        uint256 newLockRatio = totalCVXBalance.mul(toLock).div(MAX_BPS);
        uint256 toWantRatio = totalCVXBalance.mul(MAX_BPS.sub(toLock)).div(MAX_BPS);

        if (newLockRatio <= currentLockRatio) {
            uint256 toDeposit = IERC20Upgradeable(CVX).balanceOf(address(this));
            if (toDeposit > 0) {
                CVX_VAULT.deposit(toDeposit);
            }

            return;
        }

        uint256 cvxToLock = newLockRatio.sub(currentLockRatio);

        uint256 maxCVX = IERC20Upgradeable(CVX).balanceOf(address(this));
        if (cvxToLock > maxCVX) {
            LOCKER.lock(address(this), maxCVX, LOCKER.maximumBoostPayment());
        } else {
            LOCKER.lock(address(this), cvxToLock, LOCKER.maximumBoostPayment());
        }

        uint256 cvxLeft = IERC20Upgradeable(CVX).balanceOf(address(this));
        if (cvxLeft > 0) {
            CVX_VAULT.deposit(cvxLeft);
        }
    }
}
