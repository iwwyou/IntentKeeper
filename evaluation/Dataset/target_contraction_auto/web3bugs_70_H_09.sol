pragma solidity =0.8.9;

contract USDV is IUSDV, ProtocolConstants, ERC20, Ownable {

    using SafeERC20 for IERC20Extended;

    IERC20Extended public immutable vader;

    ILiquidityBasedTWAP public lbt;

    uint256 public exchangeFee;

    uint256 public dailyLimit = type(uint256).max;

    uint256 public cycleTimestamp;

    uint256 public cycleMints;

    mapping(address => Lock[]) public locks;

    address public guardian;

    bool private isLocked;

    function mint(uint256 vAmount) external onlyWhenNotLocked returns (uint256 uAmount) {
        uint256 vPrice = lbt.getVaderPrice();

        vader.transferFrom(msg.sender, address(this), vAmount);
        vader.burn(vAmount);

        uAmount = (vPrice * vAmount) / 1e18;

        if (cycleTimestamp <= block.timestamp) {
            cycleTimestamp = block.timestamp + 24 hours;
            cycleMints = uAmount;
        } else {
            cycleMints += uAmount;
            require(cycleMints <= dailyLimit, "USDV::mint: 24 Hour Limit Reached");
        }

        if (exchangeFee != 0) {
            uint256 fee = (uAmount * exchangeFee) / _MAX_BASIS_POINTS;
            uAmount = uAmount - fee;
            _mint(owner(), fee);
        }

        _mint(address(this), uAmount);

        _createLock(LockTypes.USDV, uAmount);
    }

    function burn(uint256 uAmount) external onlyWhenNotLocked returns (uint256 vAmount) {
        uint256 uPrice = lbt.getUSDVPrice();

        _burn(msg.sender, uAmount);

        vAmount = (uPrice * uAmount) / 1e18;

        if (exchangeFee != 0) {
            uint256 fee = (vAmount * exchangeFee) / _MAX_BASIS_POINTS;
            vAmount = vAmount - fee;
            vader.mint(owner(), fee);
        }

        vader.mint(address(this), vAmount);

        _createLock(LockTypes.VADER, vAmount);
    }

    function _createLock(LockTypes lockType, uint256 amount) private {
        uint256 release = block.timestamp + lbt.maxUpdateWindow();

        locks[msg.sender].push(Lock(lockType, amount, release));

        emit LockCreated(msg.sender, lockType, amount, release);
    }

    modifier onlyWhenNotLocked() {
        require(!isLocked);
        _;
    }
}
