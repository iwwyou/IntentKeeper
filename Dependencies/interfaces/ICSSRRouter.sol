pragma solidity ^0.8.0;

interface ICSSRRouter {
    function update(address _asset, bytes memory _data)
        external
        returns (FloatStruct memory);

    function getPrice(address _asset) external view returns (FloatStruct memory);

    function getLiquidity(address _asset) external view returns (uint256);
}
