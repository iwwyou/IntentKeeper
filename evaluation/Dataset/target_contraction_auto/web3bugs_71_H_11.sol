pragma solidity 0.8.7;

contract PoolTemplate is InsureDAOERC20, IPoolTemplate, IUniversalMarket {

    event MarketStatusChanged(MarketStatus statusValue);

    bool public initialized;
    bool public override paused;
    string public metadata;

    IParameters public parameters;
    IRegistry public registry;
    IVault public vault;

    uint256 public attributionDebt;
    uint256 public override lockedAmount;
    uint256 public override totalCredit;
    uint256 public rewardPerCredit;
    uint256 public pendingEnd;

    struct IndexInfo {
        uint256 credit;
        uint256 rewardDebt;
        bool exist;
    }

    mapping(address => IndexInfo) public indicies;
    address[] public indexList;

    enum MarketStatus {
        Trading, Payingout
    }
    MarketStatus public marketStatus;

    struct Withdrawal {
        uint256 timestamp;
        uint256 amount;
    }
    mapping(address => Withdrawal) public withdrawalReq;

    struct Insurance {
        uint256 id;
        uint256 startTime;
        uint256 endTime;
        uint256 amount;
        bytes32 target;
        address insured;
        bool status;
    }
    mapping(uint256 => Insurance) public insurances;
    uint256 public allInsuranceCount;

    struct Incident {
        uint256 payoutNumerator;
        uint256 payoutDenominator;
        uint256 incidentTimestamp;
        bytes32 merkleRoot;
    }
    Incident public incident;

    uint256 public constant MAGIC_SCALE_1E6 = 1e6;

    function resume() external {
        require(marketStatus == MarketStatus.Payingout && pendingEnd < block.timestamp, "ERROR: UNABLE_TO_RESUME");

        uint256 _debt = vault.debts(address(this));
        uint256 _totalCredit = totalCredit;
        uint256 _deductionFromIndex = (_debt * _totalCredit * MAGIC_SCALE_1E6) / totalLiquidity();
        uint256 _actualDeduction;
        for (uint256 i = 0; i < indexList.length; i++) {
            address _index = indexList[i];
            uint256 _credit = indicies[_index].credit;
            if (_credit > 0) {
                uint256 _shareOfIndex = (_credit * MAGIC_SCALE_1E6) / _totalCredit;
                uint256 _redeemAmount = _divCeil(_deductionFromIndex, _shareOfIndex);
                _actualDeduction += IIndexTemplate(_index).compensate(_redeemAmount);
            }
        }

        uint256 _deductionFromPool = _debt - _deductionFromIndex / MAGIC_SCALE_1E6;
        uint256 _shortage = _deductionFromIndex / MAGIC_SCALE_1E6 - _actualDeduction;

        if (_deductionFromPool > 0) {
            vault.offsetDebt(_deductionFromPool, address(this));
        }

        vault.transferDebt(_shortage);

        marketStatus = MarketStatus.Trading;
        emit MarketStatusChanged(MarketStatus.Trading);
    }

    function totalLiquidity() public view override returns (uint256 _balance) {
        return originalLiquidity() + totalCredit;
    }

    function originalLiquidity() public view returns (uint256 _balance) {
        return vault.underlyingValue(address(this)) - vault.attributionValue(attributionDebt);
    }

    function _divCeil(uint256 a, uint256 b) internal pure returns (uint256) {
        require(b > 0);
        uint256 c = a / b;
        if (a % b != 0) {
            c = c + 1;
        }
        return c;
    }

}
