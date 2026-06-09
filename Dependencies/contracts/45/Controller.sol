pragma solidity ^0.8.4;

abstract contract Controller is Initializable, UUPSUpgradeable, AccessControlUpgradeable {
    bytes32 public constant ROLE_ADMIN = keccak256("ROLE_ADMIN");

    mapping(address => address) private _admins;
    bool private _paused;
    address public pauseGuardian;

    event Paused(address account);

    event Unpaused(address account);

    modifier whenNotPaused() {
        require(!_paused, "Controller: paused");
        _;
    }

    modifier whenPaused() {
        require(_paused, "Controller: not paused");
        _;
    }

    modifier onlyAdmin() {
        require(hasRole(ROLE_ADMIN, msg.sender), "Controller: not admin");
        _;
    }

    modifier onlyGuardian() {
        require(pauseGuardian == msg.sender, "Controller: caller does not have the guardian role");
        _;
    }

    function __Controller_init(address admin_) public initializer {
        require(admin_ != address(0), "Controller: address zero");
        _paused = false;
        _admins[admin_] = admin_;
        __UUPSUpgradeable_init();
        _setupRole(ROLE_ADMIN, admin_);
        pauseGuardian = admin_;
    }

    function _authorizeUpgrade(address) internal view override onlyAdmin {}

    function isAdmin(address account) public view returns (bool) {
        return hasRole(ROLE_ADMIN, account);
    }

    function addAdmin(address account) public onlyAdmin {
        require(account != address(0), "Controller: address zero");
        require(_admins[account] == address(0), "Controller: admin already existed");

        _admins[account] = account;
        _setupRole(ROLE_ADMIN, account);
    }

    function setGuardian(address account) public onlyAdmin {
        pauseGuardian = account;
    }

    function renounceAdmin() public {
        renounceRole(ROLE_ADMIN, msg.sender);
        delete _admins[msg.sender];
    }

    function paused() public view returns (bool) {
        return _paused;
    }

    function pause() public onlyGuardian whenNotPaused {
        _paused = true;
        emit Paused(msg.sender);
    }

    function unpause() public onlyGuardian whenPaused {
        _paused = false;
        emit Unpaused(msg.sender);
    }

    uint256[50] private ______gap;
}
