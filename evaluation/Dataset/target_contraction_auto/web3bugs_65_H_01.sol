pragma solidity =0.8.7;

contract Basket is IBasket, ERC20Upgradeable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    uint256 public constant TIMELOCK_DURATION = 1 days;
    uint256 public constant ONE_YEAR = 365.25 days;
    uint256 private constant BASE = 1e18;

    uint256 public maxSupply;

    address public publisher;
    uint256 public licenseFee;

    IFactory public override factory;
    IAuction public override auction;

    uint256 public override ibRatio;

    PendingPublisher public pendingPublisher;
    PendingLicenseFee public pendingLicenseFee;
    PendingWeights public pendingWeights;
    PendingMaxSupply public pendingMaxSupply;

    address[] public tokens;
    uint256[] public weights;

    uint256 public override lastFee;

    bool public override initialized;

    function handleFees(uint256 startSupply) private {
        if (lastFee == 0) {
            lastFee = block.timestamp;
        } else if (startSupply == 0) {
            return;
        } else {
            uint256 timeDiff = (block.timestamp - lastFee);
            uint256 feePct = timeDiff * licenseFee / ONE_YEAR;
            uint256 fee = startSupply * feePct / (BASE - feePct);

            _mint(publisher, fee * (BASE - factory.ownerSplit()) / BASE);
            _mint(Ownable(address(factory)).owner(), fee * factory.ownerSplit() / BASE);
            lastFee = block.timestamp;

            uint256 newIbRatio = ibRatio * startSupply / totalSupply();
            ibRatio = newIbRatio;

            emit NewIBRatio(ibRatio);
        }
    }

}
