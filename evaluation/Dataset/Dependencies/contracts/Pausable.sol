pragma solidity 0.8.9;

abstract contract Pausable {
    bool public isPaused;

    modifier notPaused() {
        require(!isPaused, Error.CONTRACT_PAUSED);
        _;
    }

    modifier onlyAuthorizedToPause() {
        require(_isAuthorizedToPause(msg.sender), Error.UNAUTHORIZED_PAUSE);
        _;
    }

    function pause() external onlyAuthorizedToPause returns (bool) {
        isPaused = true;
        return true;
    }

    function unpause() external onlyAuthorizedToPause returns (bool) {
        isPaused = false;
        return true;
    }

    function _isAuthorizedToPause(address account) internal view virtual returns (bool);
}
