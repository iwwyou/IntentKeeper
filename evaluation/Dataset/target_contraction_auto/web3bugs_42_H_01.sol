pragma solidity ^0.8.0;

contract MochiVault is Initializable, IMochiVault, IERC3156FlashLender {
    using Float for uint256;
    using CheapERC20 for IERC20;

    bytes32 public constant CALLBACK_SUCCESS = keccak256("ERC3156FlashBorrower.onFlashLoan");

    IMochiEngine public immutable engine;
    IERC20 public override asset;

    uint256 public debtIndex;
    uint256 public lastAccrued;

    uint256 public override deposits;
    uint256 public override debts;
    int256 public override claimable;

    uint256 public liquidated;

    mapping(uint256 => Detail) public override details;
    mapping(uint256 => uint256) public lastDeposit;

    modifier updateDebt(uint256 _id) {
        accrueDebt(_id);
        _;
    }

    function liveDebtIndex() public view override returns (uint256 index) {
        return engine.mochiProfile().calculateFeeIndex(address(asset), debtIndex, lastAccrued);
    }

    function accrueDebt(uint256 _id) public {
        uint256 currentIndex = liveDebtIndex();
        uint256 increased = (debts * currentIndex) / debtIndex - debts;
        debts += increased;
        claimable += int256(increased);
        debtIndex = currentIndex;
        lastAccrued = block.timestamp;
        if (_id != type(uint256).max && details[_id].debtIndex < debtIndex) {
            require(details[_id].status != Status.Invalid, "invalid");
            if (details[_id].debt != 0) {
                uint256 increasedDebt = (details[_id].debt * debtIndex) / details[_id].debtIndex - details[_id].debt;
                uint256 discountedDebt = increasedDebt.multiply(engine.discountProfile().discount(engine.nft().ownerOf(_id)));
                debts -= discountedDebt;
                claimable -= int256(discountedDebt);
                details[_id].debt += (increasedDebt - discountedDebt);
            }
            details[_id].debtIndex = debtIndex;
        }
    }

    function mint(address _recipient, address _referrer) public returns (uint256 id) {
        id = engine.nft().mint(address(asset), _recipient);
        details[id].debtIndex = liveDebtIndex();
        details[id].status = Status.Idle;
        details[id].referrer = _referrer;
    }

    function borrow(uint256 _id, uint256 _amount, bytes memory _data) public override updateDebt(_id) {
        float memory price = engine.cssr().update(address(asset), _data);
        float memory cf = engine.mochiProfile().maxCollateralFactor(address(asset));
        uint256 maxMinted = details[_id].collateral.multiply(cf).multiply(price);
        require(engine.nft().ownerOf(_id) == msg.sender, "!approved");
        require(engine.nft().asset(_id) == address(asset), "!asset");
        if(details[_id].debt + _amount > maxMinted) {
            _amount = maxMinted - details[_id].debt;
        }
        if(engine.mochiProfile().creditCap(address(asset)) < debts + _amount) {
            _amount = engine.mochiProfile().creditCap(address(asset)) - debts;
        }
        uint256 increasingDebt = (_amount * 1005) / 1000;
        uint256 totalDebt = details[_id].debt + increasingDebt;
        require(details[_id].debt + _amount >= engine.mochiProfile().minimumDebt(), "<minimum");
        require(!_liquidatable(details[_id].collateral, price, totalDebt), "!healthy");
        mintFeeToPool(increasingDebt - _amount, details[_id].referrer);
        details[_id].debtIndex = (details[_id].debtIndex * (totalDebt)) / (details[_id].debt + _amount);
        details[_id].debt = totalDebt;
        details[_id].status = Status.Active;
        debts += _amount;
        engine.minter().mint(msg.sender, _amount);
    }

    function _liquidatable(uint256 _collateral, float memory _price, uint256 _debt) internal view returns (bool) {
        float memory lf = engine.mochiProfile().liquidationFactor(address(asset));
        return _collateral.multiply(lf) < _debt.divide(_price);
    }

    function mintFeeToPool(uint256 _amount, address _referrer) internal {
        claimable -= int256(_amount);
        if (address(0) != _referrer) {
            engine.minter().mint(address(engine.referralFeePool()), _amount);
            engine.referralFeePool().addReward(_referrer);
        } else {
            engine.minter().mint(address(engine.treasury()), _amount);
        }
    }

}
