pragma solidity ^0.8.0;

interface IDiscountProfile {
    function discount(address _user) external view returns (FloatStruct memory);
}
