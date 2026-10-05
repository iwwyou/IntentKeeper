pragma solidity =0.8.7;

interface IFactory {
    function minLicenseFee() external view returns (uint256);
    function ownerSplit() external view returns (uint256);
}
