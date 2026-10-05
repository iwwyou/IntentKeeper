pragma solidity 0.8.9;

contract Preparable is IPreparable {
    uint256 private constant _MIN_DELAY = 3 days;

    mapping(bytes32 => address) public pendingAddresses;
    mapping(bytes32 => uint256) public pendingUInts256;

    mapping(bytes32 => address) public currentAddresses;
    mapping(bytes32 => uint256) public currentUInts256;

    mapping(bytes32 => uint256) public deadlines;

    function _prepareDeadline(bytes32 key, uint256 delay) internal {
        require(deadlines[key] == 0, Error.DEADLINE_NOT_ZERO);
        require(delay >= _MIN_DELAY, Error.DELAY_TOO_SHORT);
        deadlines[key] = block.timestamp + delay;
    }

    function _prepare(
        bytes32 key,
        uint256 value,
        uint256 delay
    ) internal returns (bool) {
        _prepareDeadline(key, delay);
        pendingUInts256[key] = value;
        emit ConfigPreparedNumber(key, value, delay);
        return true;
    }

    function _prepare(bytes32 key, uint256 value) internal returns (bool) {
        return _prepare(key, value, _MIN_DELAY);
    }

    function _prepare(
        bytes32 key,
        address value,
        uint256 delay
    ) internal returns (bool) {
        _prepareDeadline(key, delay);
        pendingAddresses[key] = value;
        emit ConfigPreparedAddress(key, value, delay);
        return true;
    }

    function _prepare(bytes32 key, address value) internal returns (bool) {
        return _prepare(key, value, _MIN_DELAY);
    }

    function _resetUInt256Config(bytes32 key) internal returns (bool) {
        require(deadlines[key] != 0, Error.DEADLINE_NOT_ZERO);
        deadlines[key] = 0;
        pendingUInts256[key] = 0;
        emit ConfigReset(key);
        return true;
    }

    function _resetAddressConfig(bytes32 key) internal returns (bool) {
        require(deadlines[key] != 0, Error.DEADLINE_NOT_ZERO);
        deadlines[key] = 0;
        pendingAddresses[key] = address(0);
        emit ConfigReset(key);
        return true;
    }

    function _executeDeadline(bytes32 key) internal {
        uint256 deadline = deadlines[key];
        require(block.timestamp >= deadline, Error.DEADLINE_NOT_REACHED);
        require(deadline != 0, Error.DEADLINE_NOT_SET);
        deadlines[key] = 0;
    }

    function _executeUInt256(bytes32 key) internal returns (uint256) {
        _executeDeadline(key);
        uint256 newValue = pendingUInts256[key];
        _setConfig(key, newValue);
        return newValue;
    }

    function _executeAddress(bytes32 key) internal returns (address) {
        _executeDeadline(key);
        address newValue = pendingAddresses[key];
        _setConfig(key, newValue);
        return newValue;
    }

    function _setConfig(bytes32 key, address value) internal returns (address) {
        address oldValue = currentAddresses[key];
        currentAddresses[key] = value;
        pendingAddresses[key] = address(0);
        deadlines[key] = 0;
        emit ConfigUpdatedAddress(key, oldValue, value);
        return value;
    }

    function _setConfig(bytes32 key, uint256 value) internal returns (uint256) {
        uint256 oldValue = currentUInts256[key];
        currentUInts256[key] = value;
        pendingUInts256[key] = 0;
        deadlines[key] = 0;
        emit ConfigUpdatedNumber(key, oldValue, value);
        return value;
    }
}
