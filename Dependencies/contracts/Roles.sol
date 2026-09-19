pragma solidity ^0.8.0;

contract Roles {
    mapping(address => mapping(uint256 => bool)) public roles;
    mapping(uint256 => address) public mainCharacters;

    function giveRole(uint256 role, address actor) external {
        roles[actor][role] = true;
    }

    function removeRole(uint256 role, address actor) external {
        roles[actor][role] = false;
    }

    function setMainCharacter(uint256 role, address actor) external {
        mainCharacters[role] = actor;
    }

    function getRole(uint256 role, address contr) external view returns (bool) {
        return roles[contr][role];
    }
}
