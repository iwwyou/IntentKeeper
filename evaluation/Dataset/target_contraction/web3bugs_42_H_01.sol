pragma solidity ^0.8.0;

contract MochiVault is Initializable, IMochiVault, IERC3156FlashLender {
    using Float for uint256;
    using CheapERC20 for IERC20;

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

    function borrow(
        uint256 _id,
        uint256 _amount,
        bytes memory _data
    ) public override updateDebt(_id) {
        FloatStruct memory price = engine.cssr().update(address(asset), _data);
        FloatStruct memory cf = engine.mochiProfile().maxCollateralFactor(address(asset));
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
        require(!_liquidatable(details[_id].collateral, price, totalDebt),"!healthy");
        mintFeeToPool(increasingDebt - _amount, details[_id].referrer);
        details[_id].debtIndex =
            (details[_id].debtIndex * (totalDebt)) /
            (details[_id].debt + _amount);
        details[_id].debt = totalDebt;
        details[_id].status = Status.Active;
        debts += _amount;
        engine.minter().mint(msg.sender, _amount);
    }    
}
