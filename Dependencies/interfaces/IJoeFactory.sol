pragma solidity ^0.8.0;

interface IJoeFactory {
    function getPair(address tokenA, address tokenB) external view returns (address pair);
}
