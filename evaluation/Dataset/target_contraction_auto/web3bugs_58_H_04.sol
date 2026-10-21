pragma solidity 0.8.9;

contract AaveVault is Vault {
    address[] internal _aTokens;
    uint256[] internal _tvls;

    function tvl() public view override returns (uint256[] memory tokenAmounts) {
        return _tvls;
    }

}
