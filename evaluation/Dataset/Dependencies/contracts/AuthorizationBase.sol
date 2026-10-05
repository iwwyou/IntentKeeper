pragma solidity 0.8.9;

abstract contract AuthorizationBase {
    modifier onlyRole(bytes32 role) {
        require(_roleManager().hasRole(role, msg.sender), Error.UNAUTHORIZED_ACCESS);
        _;
    }

    modifier onlyGovernance() {
        require(_roleManager().hasRole(Roles.GOVERNANCE, msg.sender), Error.UNAUTHORIZED_ACCESS);
        _;
    }

    modifier onlyRoles2(bytes32 role1, bytes32 role2) {
        require(_roleManager().hasAnyRole(role1, role2, msg.sender), Error.UNAUTHORIZED_ACCESS);
        _;
    }

    modifier onlyRoles3(
        bytes32 role1,
        bytes32 role2,
        bytes32 role3
    ) {
        require(
            _roleManager().hasAnyRole(role1, role2, role3, msg.sender),
            Error.UNAUTHORIZED_ACCESS
        );
        _;
    }

    function roleManager() external view virtual returns (IRoleManager) {
        return _roleManager();
    }

    function _roleManager() internal view virtual returns (IRoleManager);
}
