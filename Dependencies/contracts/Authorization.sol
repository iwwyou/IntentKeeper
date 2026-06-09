pragma solidity 0.8.9;

contract Authorization is AuthorizationBase {
    IRoleManager internal immutable __roleManager;

    function _roleManager() internal view override returns (IRoleManager) {
        return __roleManager;
    }
}
