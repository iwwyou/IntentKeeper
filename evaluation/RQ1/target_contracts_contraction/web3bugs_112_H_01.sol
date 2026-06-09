pragma solidity 0.8.9;

contract StakerVault is IStakerVault, Authorization, Pausable, Initializable, Preparable {
    using AddressProviderHelpers for IAddressProvider;
    using SafeERC20 for IERC20;
    using ScaledMath for uint256;

    bytes32 internal constant _LP_GAUGE = "lpGauge";

    IController public immutable controller;

    address public token;

    mapping(address => uint256) public balances;
    mapping(address => uint256) public actionLockedBalances;

    mapping(address => mapping(address => uint256)) internal _allowances;

    uint256 private _poolTotalStaked;

    mapping(address => bool) public strategies;
    uint256 public strategiesTotalStaked;   

    function transfer(address account, uint256 amount) external override notPaused returns (bool) {
        require(msg.sender != account, Error.SELF_TRANSFER_NOT_ALLOWED);
        require(balances[msg.sender] >= amount, Error.INSUFFICIENT_BALANCE);

        ILiquidityPool pool = controller.addressProvider().getPoolForToken(token);
        pool.handleLpTokenTransfer(msg.sender, account, amount);

        balances[msg.sender] -= amount;
        balances[account] += amount;

        address lpGauge = currentAddresses[_LP_GAUGE];
        if (lpGauge != address(0)) {
            ILpGauge(lpGauge).userCheckpoint(msg.sender);
            ILpGauge(lpGauge).userCheckpoint(account);
        }

        emit Transfer(msg.sender, account, amount);
        return true;
    }    
}
