pragma solidity 0.8.9;

interface IController is IPreparable {
    function addressProvider() external view returns (IAddressProvider);

    function inflationManager() external view returns (IInflationManager);

    function addStakerVault(address stakerVault) external returns (bool);

    function removePool(address pool) external returns (bool);

    function prepareKeeperRequiredStakedBKD(uint256 amount) external;

    function executeKeeperRequiredStakedBKD() external;

    function getKeeperRequiredStakedBKD() external view returns (uint256);

    function canKeeperExecuteAction(address keeper) external view returns (bool);

    function getTotalEthRequiredForGas(address payer) external view returns (uint256);
}
