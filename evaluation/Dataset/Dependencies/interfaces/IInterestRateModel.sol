pragma solidity ^0.8.4;

interface IInterestRateModel {
    function isInterestRateModel() external pure returns (bool);

    function getBorrowRate() external view returns (uint256);

    function getSupplyRate(uint256 reserveFactorMantissa) external view returns (uint256);

    function setInterestRate(uint256 interestRatePerBlock_) external;
}
